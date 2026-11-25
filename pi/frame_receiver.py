#!/usr/bin/env python3
"""Empfänger-Dienst auf dem Pi im Bilderrahmen.

Home Assistant schickt fertige Bilder per HTTP hierher:
  POST /display?force=0|1   (Body: PNG)  -> {"result": "queued" | "unchanged"}
  GET  /status                           -> Zustand, WLAN, Akku, System als JSON
  GET  /current.png                      -> zuletzt angezeigtes Bild

Zusätzlich:
  * Akku-Schutz: Ist der Akku fast leer (≤ 3,3 V beim Entladen), zeigt der
    Rahmen einen Hinweis und fährt den Pi sicher herunter.
  * Verbindungs-Wächter: Kommt lange kein Bild von Home Assistant, zeigt der
    Rahmen einen Fehlerbildschirm (WLAN weg oder Home Assistant nicht erreichbar).

Das Zeichnen läuft für jedes Bild in einem eigenen Prozess (frame_show.py).
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

VERSION = "1.1.0"
PORT = int(os.environ.get("FRAME_PORT", "8765"))
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "last_hash")
CURRENT = os.path.join(HERE, "current.png")
SHOW = os.path.join(HERE, "frame_show.py")
SCREENS = os.path.join(HERE, "frame_screens.py")
UPS_DIR = os.path.expanduser(os.environ.get("UPS_DIR", "~/RPi_Zero_PhotoPainter/UPS"))
MAX_BYTES = 5 * 1024 * 1024
LOW_VOLT = float(os.environ.get("LOW_BATTERY_VOLT", "3.3"))

state = {
    "busy": False,
    "last_hash": open(STATE_FILE).read().strip() if os.path.isfile(STATE_FILE) else None,
    "last_display": None,
    "last_received": time.time(),
    "interval_min": 60,
    "last_error": None,
    "screen": "image",  # image | offline | low_battery
    "rotation": 0,
}
pending = {"data": None, "hash": None}
cond = threading.Condition()


def log(msg):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


# ------------------------------------------------------------------ Akku (INA219 im Rahmen)
class Battery:
    def __init__(self):
        self.ina = None
        self.err = None
        path = os.path.join(UPS_DIR, "INA219.py")
        if not os.path.isfile(path):
            self.err = "kein UPS-Treiber gefunden"
            return
        try:
            src = open(path, encoding="utf-8", errors="ignore").read()
            addrs = [int(a, 16) for a in re.findall(r"addr\s*=\s*(0x[0-9a-fA-F]+)", src)] + [0x43, 0x41, 0x40, 0x42]
            spec = importlib.util.spec_from_file_location("waveshare_ina219", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for a in dict.fromkeys(addrs):
                try:
                    ina = mod.INA219(addr=a)
                    v = ina.getBusVoltage_V()
                    if 2.0 < v < 5.5:
                        self.ina = ina
                        log(f"Akku-Messung gefunden (INA219 an 0x{a:02x}, {v:.2f} V)")
                        return
                except Exception:  # noqa: BLE001
                    continue
            self.err = "kein Akku erkannt"
        except Exception as e:  # noqa: BLE001
            self.err = str(e)

    def read(self):
        if self.ina is None:
            return {"present": False, "percent": None, "error": self.err}
        try:
            v = float(self.ina.getBusVoltage_V())
            i = float(self.ina.getCurrent_mA())
            pct = max(0.0, min(100.0, (v - 3.0) / 1.2 * 100))
            return {"present": True, "voltage": round(v, 2), "current_ma": round(i),
                    "percent": round(pct), "charging": i > 20}
        except Exception as e:  # noqa: BLE001
            return {"present": False, "percent": None, "error": str(e)}


battery = Battery()


# ------------------------------------------------------------------ WLAN und System
def wifi():
    out = {"ssid": None, "dbm": None, "quality": None, "label": None, "connected": False}
    try:
        for line in open("/proc/net/wireless"):
            if ":" in line and line.strip().startswith("wl"):
                parts = line.split()
                out["quality"] = round(float(parts[2].rstrip(".")) / 70 * 100)
                out["dbm"] = int(float(parts[3].rstrip(".")))
                break
    except (OSError, ValueError, IndexError):
        pass
    try:
        ssid = subprocess.run(["iwgetid", "-r"], capture_output=True, text=True, timeout=3).stdout.strip()
        out["ssid"] = ssid or None
    except (OSError, subprocess.SubprocessError):
        pass
    out["connected"] = bool(out["ssid"]) or out["dbm"] is not None
    d = out["dbm"]
    if d is not None:
        out["label"] = "Sehr gut" if d >= -55 else "Gut" if d >= -65 else "Mäßig" if d >= -75 else "Schwach"
    return out


def system():
    s = {}
    try:
        s["cpu_temp"] = round(int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000, 1)
    except (OSError, ValueError):
        s["cpu_temp"] = None
    try:
        s["uptime_h"] = round(float(open("/proc/uptime").read().split()[0]) / 3600, 1)
    except (OSError, ValueError):
        pass
    return s


# ------------------------------------------------------------------ Anzeige
def run_show(args, timeout=240):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=timeout)


def show_screen(kind, detail=""):
    """Zeigt einen der eingebauten Hinweis-Bildschirme."""
    try:
        res = run_show([SCREENS, kind, detail, str(state["rotation"])])
        if res.returncode == 0:
            state["screen"] = kind
            state["last_hash"] = None  # nächstes Bild von HA wieder anzeigen
            log(f"Hinweis angezeigt: {kind}")
        else:
            log("Hinweis fehlgeschlagen: " + (res.stderr or res.stdout))
    except Exception as e:  # noqa: BLE001
        log(f"Hinweis fehlgeschlagen: {e}")


def worker():
    while True:
        with cond:
            while pending["data"] is None:
                cond.wait()
            data, digest = pending["data"], pending["hash"]
            pending["data"] = pending["hash"] = None
            state["busy"] = True
        try:
            fd, path = tempfile.mkstemp(suffix=".png", dir=HERE)
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            log("Zeichne neues Bild ...")
            t0 = time.time()
            res = run_show([SHOW, path])
            if res.returncode == 0:
                os.replace(path, CURRENT)
                state.update(last_hash=digest, last_display=datetime.now().isoformat(timespec="seconds"),
                             last_error=None, screen="image")
                with open(STATE_FILE, "w") as fh:
                    fh.write(digest)
                log(f"Fertig nach {time.time() - t0:.0f} s")
            else:
                os.unlink(path)
                err = (res.stderr or res.stdout).strip().splitlines()
                state["last_error"] = err[-1] if err else f"Exit {res.returncode}"
                log("Fehler: " + (res.stderr or res.stdout))
        except Exception as e:  # noqa: BLE001
            state["last_error"] = str(e)
            log(f"Fehler: {e}")
        finally:
            with cond:
                state["busy"] = False


def guard():
    """Akku-Schutz und Verbindungs-Wächter, läuft jede Minute."""
    low_count = 0
    while True:
        time.sleep(60)
        try:
            b = battery.read()
            if b.get("present") and not b.get("charging") and b.get("voltage", 9) <= LOW_VOLT:
                low_count += 1
            else:
                low_count = 0
            if low_count >= 3 and state["screen"] != "low_battery":
                with cond:
                    busy = state["busy"]
                if not busy:
                    show_screen("low_battery", f"{b.get('voltage', 0):.2f} V")
                    log("Akku fast leer – fahre herunter")
                    subprocess.run(["sudo", "-n", "shutdown", "-h", "now"], check=False)
            silent = time.time() - state["last_received"]
            limit = max(3 * state["interval_min"] * 60, 3 * 3600 if state["interval_min"] >= 60 else 3600)
            if silent > limit and state["screen"] == "image":
                w = wifi()
                show_screen("offline", "wifi" if not w["connected"] else "ha")
        except Exception as e:  # noqa: BLE001
            log(f"Wächter: {e}")


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "Bilderrahmen/" + VERSION

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/status"):
            with cond:
                st = {**state, "pending": pending["data"] is not None}
            st.pop("last_received", None)
            self._json(200, {**st, "version": VERSION, "wifi": wifi(), "battery": battery.read(),
                             "system": system()})
        elif path == "/current.png" and os.path.isfile(CURRENT):
            data = open(CURRENT, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/display":
            return self._json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BYTES:
            return self._json(400, {"error": "Bild fehlt oder zu groß"})
        data = self.rfile.read(length)
        if not data.startswith(b"\x89PNG"):
            return self._json(400, {"error": "nur PNG"})
        try:
            state["interval_min"] = max(1, int(self.headers.get("X-Refresh-Interval") or state["interval_min"]))
        except ValueError:
            pass
        try:
            state["rotation"] = int(self.headers.get("X-Rotation") or state["rotation"]) % 360
        except ValueError:
            pass
        state["last_received"] = time.time()
        force = parse_qs(url.query).get("force", ["0"])[0] == "1"
        digest = hashlib.sha1(data).hexdigest()
        with cond:
            if not force and state["screen"] == "image" and digest in (state["last_hash"], pending["hash"]):
                return self._json(200, {"result": "unchanged"})
            pending["data"], pending["hash"] = data, digest
            cond.notify()
        self._json(202, {"result": "queued"})

    def log_message(self, fmt, *args):
        pass


def main():
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=guard, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log(f"Bilderrahmen-Empfänger {VERSION} läuft auf Port {PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
