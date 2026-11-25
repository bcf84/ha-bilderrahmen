"""Zeichnet das Bild für den 6-Farben-E-Paper-Rahmen (800x480).

Reines Pillow, ohne Home-Assistant-Abhängigkeiten, damit es sich auch
außerhalb von HA testen lässt.
"""

from __future__ import annotations

import io
import math
import os
from datetime import date
from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw, ImageFont

W, H = 800, 480
C = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "yellow": (255, 255, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
}
WD = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WD_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]
COND = {
    "clear-night": "Klar", "cloudy": "Bewölkt", "exceptional": "Unwetter",
    "fog": "Nebel", "hail": "Hagel", "lightning": "Gewitter",
    "lightning-rainy": "Gewitter", "partlycloudy": "Teils bewölkt",
    "pouring": "Starkregen", "rainy": "Regen", "snowy": "Schnee",
    "snowy-rainy": "Schneeregen", "sunny": "Sonnig", "windy": "Windig",
    "windy-variant": "Windig",
}

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")


@lru_cache(maxsize=32)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _tw(d: ImageDraw.ImageDraw, txt: str, f) -> int:
    l, _, r, _ = d.textbbox((0, 0), txt, font=f)
    return r - l


def _fit(d: ImageDraw.ImageDraw, txt: str, f, width: int) -> str:
    if _tw(d, txt, f) <= width:
        return txt
    while txt and _tw(d, txt + "…", f) > width:
        txt = txt[:-1]
    return txt.rstrip() + "…"


def fmt_temp(t: float | None) -> str:
    return "–" if t is None else f"{round(t)}°"


def temp_color(t: float | None):
    if t is None:
        return C["black"]
    if t <= 0:
        return C["blue"]
    if t >= 25:
        return C["red"]
    return C["black"]


# ---------------------------------------------------------------- Symbole
def _cloud(d, cx, cy, s):
    parts = [(-0.55, 0.05, 0.45), (0.0, -0.2, 0.6), (0.55, 0.1, 0.4)]
    o = max(3, int(s * 0.08))
    for grow, col in ((o, C["black"]), (0, C["white"])):
        for px, py, r in parts:
            rr = r * s + grow
            d.ellipse([cx + px * s - rr, cy + py * s - rr,
                       cx + px * s + rr, cy + py * s + rr], fill=col)
        d.rectangle([cx - 0.55 * s, cy + 0.05 * s,
                     cx + 0.55 * s, cy + 0.5 * s + grow], fill=col)


def _sun(d, cx, cy, r):
    w = max(2, int(r * 0.15))
    for i in range(8):
        a = i * math.pi / 4
        d.line([cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35,
                cx + math.cos(a) * r * 1.8, cy + math.sin(a) * r * 1.8],
               fill=C["black"], width=w)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C["yellow"],
              outline=C["black"], width=w)


def icon(d, cx, cy, s, cond):
    cond = cond or ""
    w = max(2, int(s * 0.1))
    if cond == "sunny":
        _sun(d, cx, cy, s * 0.5)
    elif cond == "clear-night":
        r = s * 0.6
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C["yellow"],
                  outline=C["black"], width=w)
        d.ellipse([cx - r * 0.3, cy - r * 1.2, cx + r * 1.5, cy + r * 0.6],
                  fill=C["white"])
    elif cond == "partlycloudy":
        _sun(d, cx + s * 0.35, cy - s * 0.3, s * 0.38)
        _cloud(d, cx - s * 0.15, cy + s * 0.15, s * 0.75)
    elif cond == "fog":
        for i in range(4):
            y = cy - s * 0.45 + i * s * 0.3
            d.line([cx - s * 0.9, y, cx + s * 0.9, y], fill=C["black"], width=w)
    elif cond in ("windy", "windy-variant"):
        for i, ln in enumerate((0.9, 0.6, 0.8)):
            y = cy - s * 0.35 + i * s * 0.35
            d.line([cx - s * 0.9, y, cx - s * 0.9 + 2 * s * ln, y],
                   fill=C["blue"], width=w + 1)
    else:
        _cloud(d, cx, cy - s * 0.15, s * 0.9)
        base = cy + s * 0.45
        if cond in ("rainy", "pouring", "lightning-rainy", "snowy-rainy"):
            n = 4 if cond == "pouring" else 3
            for i in range(n):
                x = cx - s * 0.5 + i * s / (n - 1)
                d.line([x, base, x - s * 0.15, base + s * 0.4],
                       fill=C["blue"], width=w + 1)
        if cond in ("snowy", "snowy-rainy", "hail"):
            r = s * 0.1
            for i in range(3):
                x = cx - s * 0.4 + i * s * 0.4 + (s * 0.15 if cond == "snowy-rainy" else 0)
                y = base + s * 0.25
                d.ellipse([x - r, y - r, x + r, y + r], fill=C["blue"])
        if cond in ("lightning", "lightning-rainy", "exceptional"):
            pts = [(cx + s * 0.1, base - s * 0.2), (cx - s * 0.25, base + s * 0.35),
                   (cx, base + s * 0.35), (cx - s * 0.15, base + s * 0.75),
                   (cx + s * 0.3, base + s * 0.15), (cx + s * 0.05, base + s * 0.15)]
            d.polygon(pts, fill=C["yellow"], outline=C["black"])


# ---------------------------------------------------------------- Bereiche
def _draw_weather(d, wx: dict[str, Any]) -> None:
    now = wx.get("now") or {}
    if now:
        icon(d, 95, 175, 62, now.get("cond"))
        t = now.get("temp")
        d.text((185, 100), fmt_temp(t), font=font(92, True), fill=temp_color(t))
        d.text((190, 205), COND.get(now.get("cond"), now.get("cond") or ""),
               font=font(28), fill=C["black"])
    td = wx.get("today")
    if td:
        d.text((190, 242), f"{fmt_temp(td.get('lo'))} / {fmt_temp(td.get('hi'))}",
               font=font(26), fill=C["black"])

    fc = wx.get("forecast") or []
    if fc:
        d.line([24, 292, 420, 292], fill=C["black"], width=2)
    for i, f in enumerate(fc[:3]):
        cx = 24 + i * 136 + 62
        lbl = WD_SHORT[f["date"].weekday()]
        fb = font(28, True)
        d.text((cx - _tw(d, lbl, fb) / 2, 304), lbl, font=fb, fill=C["black"])
        icon(d, cx, 380, 34, f.get("cond"))
        t = f"{fmt_temp(f.get('lo'))}/{fmt_temp(f.get('hi'))}"
        d.text((cx - _tw(d, t, font(24)) / 2, 425), t, font=font(24), fill=C["black"])


def _draw_section(d, sec: dict[str, Any], x0: int, x1: int, y: int, ymax: int) -> int:
    """Zeichnet einen Abschnitt, gibt die nächste freie y-Position zurück."""
    if y + 80 > ymax:
        return y
    d.text((x0, y), _fit(d, sec["title"], font(30, True), x1 - x0),
           font=font(30, True), fill=C["black"])
    y += 44
    rows = sec.get("rows") or []
    if not rows:
        d.text((x0, y), sec.get("empty", "–"), font=font(20), fill=C["black"])
        return y + 34

    fr = font(22)
    fb = font(22, True)
    has_marker = any(r.get("marker") for r in rows)
    labels = [r.get("label") for r in rows if r.get("label")]
    label_w = max((_tw(d, lb, fb) for lb in labels), default=0)

    for r in rows:
        if y + 30 > ymax:
            break
        hl = bool(r.get("hl"))
        f = fb if hl else fr
        col = C["red"] if hl else C["black"]
        x = x0
        if has_marker:
            m = r.get("marker")
            if m:
                d.rectangle([x, y + 3, x + 22, y + 25], fill=C.get(m, C["red"]),
                            outline=C["black"], width=2)
            x += 32
        if label_w:
            if r.get("label"):
                d.text((x, y), r["label"], font=f, fill=col)
            x += label_w + 12
        right = r.get("right")
        rw = 0
        if right:
            right = _fit(d, right, f, (x1 - x) // 2)
            rw = _tw(d, right, f)
            d.text((x1 - rw, y), right, font=f, fill=col)
            rw += 12
        txt = _fit(d, r.get("text", ""), f, max(10, x1 - x - rw))
        d.text((x, y), txt, font=f, fill=col)
        y += 34
    return y


def render(model: dict[str, Any]) -> bytes:
    """model: today, weather (oder None), sections, rotation, error."""
    today: date = model["today"]
    img = Image.new("RGB", (W, H), C["white"])
    d = ImageDraw.Draw(img)
    d.fontmode = "1"  # ohne Kantenglättung -> scharfe Schrift auf E-Paper

    d.rectangle([0, 0, W, 74], fill=C["blue"])
    d.text((24, 12), f"{WD[today.weekday()]}, {today.day}. {MONTHS[today.month - 1]}",
           font=font(42, True), fill=C["white"])

    sections = model.get("sections") or []
    ymax = H - (30 if model.get("error") else 8)

    if model.get("weather"):
        _draw_weather(d, model["weather"])
        if sections:
            d.line([440, 96, 440, 456], fill=C["black"], width=3)
        y = 92
        for sec in sections:
            y = _draw_section(d, sec, 462, W - 20, y, ymax) + 14
    elif sections:
        cols = [(24, 384), (416, W - 20)] if len(sections) > 1 else [(24, W - 24)]
        if len(cols) > 1:
            d.line([400, 96, 400, 456], fill=C["black"], width=3)
        ys = [92] * len(cols)
        for sec in sections:
            ci = ys.index(min(ys))
            ys[ci] = _draw_section(d, sec, cols[ci][0], cols[ci][1], ys[ci], ymax) + 14
    else:
        d.text((24, 220), "Noch keine Inhalte gewählt –", font=font(30), fill=C["black"])
        d.text((24, 260), "Einstellungen in Home Assistant öffnen.", font=font(30), fill=C["black"])

    if model.get("error"):
        d.text((24, H - 24), _fit(d, model["error"], font(16), W - 48),
               font=font(16), fill=C["red"])

    rot = int(model.get("rotation") or 0)
    if rot:
        img = img.rotate(rot, expand=True)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
