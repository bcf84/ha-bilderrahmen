#!/usr/bin/env python3
"""Empfänger-Dienst auf dem Pi im Bilderrahmen.

Home Assistant schickt fertige Bilder per HTTP hierher:
  POST /display?force=0|1   (Body: PNG)  -> {"result": "queued" | "unchanged"}
  GET  /status                           -> Zustand als JSON

Das eigentliche Zeichnen läuft für jedes Bild in einem eigenen Prozess
(frame_show.py), damit ein Fehler im Display-Treiber den Dienst nicht stört.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("FRAME_PORT", "8765"))
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "last_hash")
CURRENT = os.path.join(HERE, "current.png")
SHOW = os.path.join(HERE, "frame_show.py")
MAX_BYTES = 5 * 1024 * 1024
VERSION = "1.0.0"

state = {
    "busy": False,
    "last_hash": open(STATE_FILE).read().strip() if os.path.isfile(STATE_FILE) else None,
    "last_display": None,
    "last_error": None,
}
pending = {"data": None, "hash": None}
cond = threading.Condition()


def log(msg):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


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
            res = subprocess.run([sys.executable, SHOW, path],
                                 capture_output=True, text=True, timeout=240)
            if res.returncode == 0:
                os.replace(path, CURRENT)
                state["last_hash"] = digest
                state["last_display"] = datetime.now().isoformat(timespec="seconds")
                state["last_error"] = None
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
                self._json(200, {**state, "pending": pending["data"] is not None,
                                 "version": VERSION})
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
        force = parse_qs(url.query).get("force", ["0"])[0] == "1"
        digest = hashlib.sha1(data).hexdigest()
        with cond:
            if not force and digest in (state["last_hash"], pending["hash"]):
                return self._json(200, {"result": "unchanged"})
            pending["data"], pending["hash"] = data, digest
            cond.notify()
        self._json(202, {"result": "queued"})

    def log_message(self, fmt, *args):
        pass  # keine Zugriffslogs


def main():
    threading.Thread(target=worker, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log(f"Bilderrahmen-Empfänger {VERSION} läuft auf Port {PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
