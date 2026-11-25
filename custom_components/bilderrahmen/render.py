"""Zeichnet ein Widget-Layout für den 6-Farben-E-Paper-Rahmen (800x480).

Zwei Ebenen:
  1. "paint": Hintergrund, Karten, Verläufe, Schatten und illustrierte
     Wettersymbole in vollen Farben. Diese Ebene wird mit der gemessenen
     Spectra-6-Palette gedithert – so entstehen Grau, Orange, Pastell und
     weiche Übergänge aus feinen Farbpunkten.
  2. "ink": Text, Icons und Linien in den reinen Displayfarben, ohne
     Kantenglättung – gestochen scharf.

Reines Pillow ohne Home-Assistant-Abhängigkeiten.
"""

from __future__ import annotations

import io
import json
import math
import os
from datetime import date
from functools import lru_cache
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont

W, H = 800, 480

ORDER = ["black", "white", "yellow", "red", "blue", "green"]
PURE = {
    "black": (0, 0, 0), "white": (255, 255, 255), "yellow": (255, 255, 0),
    "red": (255, 0, 0), "blue": (0, 0, 255), "green": (0, 255, 0),
}
# So erscheinen die Farben auf dem Spectra-6-Panel (für Dithering und Vorschau)
SEEN = {
    "black": (25, 30, 33), "white": (232, 232, 232), "yellow": (239, 222, 68),
    "red": (178, 19, 24), "blue": (33, 87, 186), "green": (18, 95, 32),
}
ON = {"black": "white", "white": "black", "red": "white", "blue": "white",
      "green": "white", "yellow": "black"}

THEMES = {
    "light": {"bg": (255, 255, 255), "card": (255, 255, 255), "line": "black", "fg": "black"},
    "white": {"bg": (255, 255, 255), "card": (255, 255, 255), "line": "black", "fg": "black"},
    "paper": {"bg": (236, 236, 236), "card": (255, 255, 255), "line": "black", "fg": "black"},
    "dark": {"bg": (44, 46, 52), "card": (66, 69, 76), "line": "white", "fg": "white"},
}
# Weiche Kartenfarben (oben, unten)
TINTS = {
    "sky": ((198, 222, 255), (232, 241, 255)),
    "mint": ((204, 240, 214), (234, 249, 238)),
    "sun": ((255, 233, 170), (255, 246, 216)),
    "peach": ((255, 214, 186), (255, 236, 222)),
    "rose": ((255, 206, 204), (255, 232, 230)),
    "lilac": ((222, 212, 250), (240, 235, 253)),
    "sand": ((238, 233, 222), (247, 244, 238)),
}

WD = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WD_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]
MONTHS_SHORT = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
COND = {
    "clear-night": "Klar", "cloudy": "Bewölkt", "exceptional": "Unwetter",
    "fog": "Nebel", "hail": "Hagel", "lightning": "Gewitter",
    "lightning-rainy": "Gewitter", "partlycloudy": "Teils bewölkt",
    "pouring": "Starkregen", "rainy": "Regen", "snowy": "Schnee",
    "snowy-rainy": "Schneeregen", "sunny": "Sonnig", "windy": "Windig",
    "windy-variant": "Windig",
}
BIN = {  # Tonne: (Kreis-Tönung, Icon-Farbe)
    "black": ((70, 72, 78), "white"), "green": ((120, 200, 140), "black"),
    "yellow": ((255, 222, 90), "black"), "blue": ((110, 150, 230), "white"), "red": ((240, 120, 110), "white"),
}

HERE = os.path.dirname(__file__)
FONT_DIR = os.path.join(HERE, "fonts")
WEIGHTS = {"light": 300, "regular": 400, "medium": 500, "semibold": 600, "bold": 700}


@lru_cache(maxsize=200)
def font(size: float, weight: str = "regular") -> ImageFont.FreeTypeFont:
    w = WEIGHTS.get(weight, 400)
    return ImageFont.truetype(os.path.join(FONT_DIR, f"Jost-{w}.ttf"), max(6, int(size)))


@lru_cache(maxsize=64)
def icon_font(size: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, "materialdesignicons-webfont.ttf"), max(6, int(size)))


@lru_cache(maxsize=1)
def _mdi() -> dict[str, int]:
    with open(os.path.join(FONT_DIR, "mdi.json"), encoding="utf-8") as fh:
        return json.load(fh)


def icon_char(name: str | None) -> str | None:
    if not name:
        return None
    cp = _mdi().get(str(name).split(":", 1)[-1])
    return chr(cp) if cp else None


def fmt_temp(t) -> str:
    try:
        return f"{round(float(t))}°"
    except (TypeError, ValueError):
        return "–"


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ------------------------------------------------------------------ Zeichenkontext
class Ctx:
    """Jedes Widget wird zweimal aufgerufen: erst 'paint', dann 'ink'."""

    def __init__(self, paint: Image.Image, theme: dict[str, Any]) -> None:
        self.mode = "paint"
        self.paint = paint
        self.pd = ImageDraw.Draw(paint)
        self.d: ImageDraw.ImageDraw | None = None
        self.ink_img: Image.Image | None = None
        self.theme_name = theme.get("mode") if theme.get("mode") in THEMES else "light"
        self.t = THEMES[self.theme_name]
        self.dark = self.theme_name == "dark"
        self.fg = self.t["fg"]
        acc = theme.get("accent", "red")
        self.accent = acc if acc in PURE and acc != ("black" if self.dark else "white") else "red"
        self._m = ImageDraw.Draw(Image.new("1", (1, 1)))

    def start_ink(self, img: Image.Image) -> None:
        self.mode = "ink"
        self.ink_img = img
        self.d = ImageDraw.Draw(img)
        self.d.fontmode = "1"

    def col(self, name: str) -> str:
        return {"fg": self.fg, "accent": self.accent, "line": self.t["line"]}.get(name, name)

    def tw(self, txt, f) -> float:
        return self._m.textlength(str(txt), font=f) if txt else 0

    def fit(self, txt, f, width: float) -> str:
        txt = str(txt)
        if self.tw(txt, f) <= width:
            return txt
        while txt and self.tw(txt + "…", f) > width:
            txt = txt[:-1]
        return (txt.rstrip() + "…") if txt else ""

    # ---- Ebene 1 (weich)
    def grad_shape(self, box, top, bottom, shape="rect", radius=0, mask=None) -> None:
        """Füllt eine Form mit einem senkrechten Verlauf."""
        if self.mode != "paint":
            return
        x, y, w, h = (int(round(v)) for v in box)
        if w <= 0 or h <= 0:
            return
        if mask is None:
            mask = Image.new("L", (w, h), 0)
            md = ImageDraw.Draw(mask)
            if shape == "ellipse":
                md.ellipse([0, 0, w - 1, h - 1], fill=255)
            else:
                md.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
        g = Image.linear_gradient("L").resize((w, h))
        fill = Image.composite(Image.new("RGB", (w, h), bottom), Image.new("RGB", (w, h), top), g)
        self.paint.paste(fill, (x, y), mask)

    def soft(self, box, color, radius=0, shape="rect") -> None:
        if self.mode != "paint":
            return
        x, y, w, h = box
        if shape == "ellipse":
            self.pd.ellipse([x, y, x + w, y + h], fill=color)
        else:
            self.pd.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=color)

    # ---- Ebene 2 (scharf)
    def text(self, xy, txt, f, color, anchor="la") -> None:
        if self.mode == "ink":
            self.d.text(xy, str(txt), font=f, fill=PURE[self.col(color)], anchor=anchor)

    def icon(self, cx, cy, name, size, color) -> None:
        ch = icon_char(name)
        if ch and self.mode == "ink":
            self.d.text((cx, cy), ch, font=icon_font(size), fill=PURE[self.col(color)], anchor="mm")

    def outline(self, box, radius=12, color="line", width=1) -> None:
        if self.mode == "ink":
            x, y, w, h = box
            self.d.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=radius, outline=PURE[self.col(color)],
                                     width=width)

    def solid(self, box, color, radius=0, shape="rect") -> None:
        if self.mode != "ink":
            return
        x, y, w, h = box
        if shape == "ellipse":
            self.d.ellipse([x, y, x + w, y + h], fill=PURE[self.col(color)])
        else:
            self.d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=PURE[self.col(color)])

    def line(self, pts, color, width=2) -> None:
        if self.mode == "ink":
            self.d.line(pts, fill=PURE[self.col(color)], width=width, joint="curve")

    def pill(self, x1, cy, txt, f, color, pad=12, h=None) -> float:
        h = h or int(f.size * 1.55)
        w = self.tw(txt, f) + 2 * pad
        x0 = x1 - w
        if self.mode == "ink":
            c = self.col(color)
            self.d.rounded_rectangle([x0, cy - h / 2, x1, cy + h / 2], radius=h / 2, fill=PURE[c])
            self.d.text(((x0 + x1) / 2, cy + 1), txt, font=f, fill=PURE[ON[c]], anchor="mm")
        return x0


# ------------------------------------------------------------------ illustrierte Wettersymbole
SUN_T, SUN_B = (255, 196, 92), (246, 140, 62)
CLOUD_T, CLOUD_B = (232, 232, 232), (178, 178, 178)
DARK_T, DARK_B = (160, 160, 160), (105, 105, 105)


def _cloud(ctx: Ctx, cx, cy, s, dark=False) -> None:
    """Wolke mit Breite ≈ 2s, Mittelpunkt (cx, cy)."""
    if ctx.mode != "paint":
        return
    w = int(2.0 * s)
    h = int(w * 0.64)
    if w < 4 or h < 4:
        return
    m = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(m)
    for px, py, r in ((0.29, 0.64, 0.19), (0.53, 0.44, 0.27), (0.76, 0.63, 0.17)):
        md.ellipse([px * w - r * w, py * h - r * w, px * w + r * w, py * h + r * w], fill=255)
    md.rounded_rectangle([0.1 * w, 0.58 * h, 0.9 * w, 0.97 * h], radius=0.2 * h, fill=255)
    t, b = (DARK_T, DARK_B) if dark else (CLOUD_T, CLOUD_B)
    ctx.grad_shape((cx - w / 2, cy - h / 2, w, h), t, b, mask=m)


def _sun(ctx: Ctx, cx, cy, r) -> None:
    ctx.grad_shape((cx - r, cy - r, 2 * r, 2 * r), SUN_T, SUN_B, shape="ellipse")


def _moon(ctx: Ctx, cx, cy, r) -> None:
    if ctx.mode != "paint":
        return
    size = int(2 * r)
    m = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(m)
    md.ellipse([0, 0, size - 1, size - 1], fill=255)
    md.ellipse([size * 0.32, -size * 0.18, size * 1.25, size * 0.75], fill=0)
    ctx.grad_shape((cx - r, cy - r, size, size), (255, 236, 160), (240, 200, 100), mask=m)


def wx_icon(ctx: Ctx, cx, cy, size, cond) -> None:
    """Illustriertes Wettersymbol, ungefähr size × size."""
    s = size / 2
    c = cond or "cloudy"
    if c == "sunny":
        _sun(ctx, cx, cy, s * 0.72)
    elif c == "clear-night":
        _moon(ctx, cx, cy, s * 0.7)
    elif c == "partlycloudy":
        _sun(ctx, cx + s * 0.28, cy - s * 0.22, s * 0.52)
        _cloud(ctx, cx - s * 0.08, cy + s * 0.18, s * 0.72)
    elif c in ("cloudy", "fog", "windy", "windy-variant"):
        _cloud(ctx, cx + s * 0.22, cy - s * 0.2, s * 0.55, dark=True)
        _cloud(ctx, cx - s * 0.05, cy + s * 0.12, s * 0.78)
        if c == "fog" and ctx.mode == "paint":
            for i in range(3):
                yy = cy + s * (0.5 + i * 0.17)
                ctx.soft((cx - s * 0.8, yy, s * 1.6, s * 0.08), (150, 156, 170), radius=4)
        if c.startswith("windy"):
            for i, ln in enumerate((0.9, 0.6)):
                yy = cy + s * (0.62 + i * 0.2)
                ctx.line([cx - s * 0.7, yy, cx - s * 0.7 + s * 1.4 * ln, yy], "blue", max(2, int(s * 0.06)))
    else:
        dark = c in ("pouring", "lightning", "lightning-rainy", "hail", "exceptional")
        _cloud(ctx, cx, cy - s * 0.18, s * 0.8, dark=dark)
        base = cy + s * 0.42
        lw = max(2, int(s * 0.07))
        if c in ("rainy", "pouring", "lightning-rainy", "snowy-rainy"):
            n = 4 if c == "pouring" else 3
            for i in range(n):
                xx = cx - s * 0.42 + i * (s * 0.84 / (n - 1))
                ctx.line([xx + s * 0.06, base, xx - s * 0.06, base + s * 0.32], "blue", lw)
        if c in ("snowy", "snowy-rainy", "hail"):
            for i in range(3 if c != "snowy-rainy" else 2):
                xx = cx - s * 0.35 + i * s * 0.35 + (s * 0.17 if c == "snowy-rainy" else 0)
                ctx.icon(xx, base + s * 0.2, "snowflake" if c != "hail" else "circle", s * 0.3, "blue")
        if c in ("lightning", "lightning-rainy", "exceptional"):
            pts = [(cx + s * 0.08, base - s * 0.22), (cx - s * 0.2, base + s * 0.22), (cx, base + s * 0.22),
                   (cx - s * 0.12, base + s * 0.55), (cx + s * 0.25, base + s * 0.05), (cx + s * 0.04, base + s * 0.05)]
            if ctx.mode == "paint":
                ctx.pd.polygon(pts, fill=(255, 214, 40))
            else:
                ctx.d.polygon(pts, outline=PURE["black"])


# ------------------------------------------------------------------ Karten
def _card(ctx: Ctx, box, props, default="card"):
    """Zeichnet die Karte; liefert Innenbereich und Textfarbe."""
    x, y, w, h = box
    style = props.get("style") or default
    r = int(props.get("radius", 14))
    pad = int(props.get("padding", 16))
    if style == "none" or style == "plain":
        return (x, y, w, h), "fg"
    if style == "accent":
        ctx.solid((x, y, w - 1, h - 1), "accent", radius=r)
        return (x + pad, y + pad - 2, w - 2 * pad, h - 2 * pad + 4), ON[ctx.accent]
    if style == "dark":
        ctx.grad_shape(box, (62, 66, 74), (40, 43, 49), radius=r)
        return (x + pad, y + pad - 2, w - 2 * pad, h - 2 * pad + 4), "white"
    if style in TINTS:
        top, bottom = TINTS[style]
        ctx.grad_shape(box, top, bottom, radius=r)
        if not ctx.dark:
            ctx.outline(box, radius=r)
        return (x + pad, y + pad - 2, w - 2 * pad, h - 2 * pad + 4), "black"
    # "card": helle Karte mit feiner Linie
    ctx.soft(box, ctx.t["card"], radius=r)
    ctx.outline(box, radius=r)
    return (x + pad, y + pad - 2, w - 2 * pad, h - 2 * pad + 4), "fg"


def _title(ctx: Ctx, inner, props, fg, default_icon=None):
    title = str(props.get("title") or "").strip()
    if not title:
        return inner
    x, y, w, h = inner
    f = font(19, "medium")
    ic = props.get("icon") if props.get("icon") and icon_char(props.get("icon")) else default_icon
    tx = x
    if ic:
        ctx.icon(x + 11, y + 12, ic, 22, "accent" if fg == ctx.fg and not ctx.dark else fg)
        tx = x + 30
    ctx.text((tx, y + 20), ctx.fit(title, f, w - (tx - x)), f, fg, anchor="ls")
    return (x, y + 34, w, h - 34)


def _rows(ctx, inner, rows, row_h, draw_row, fg):
    x, y, w, h = inner
    fit = max(0, int((h + 6) // row_h))
    shown = rows if len(rows) <= fit else rows[: max(0, fit - 1)]
    for i, r in enumerate(shown):
        draw_row(r, y + i * row_h, row_h)
    rest = len(rows) - len(shown)
    if rest > 0:
        ctx.text((x, y + len(shown) * row_h + row_h / 2), f"+ {rest} weitere", font(15, "medium"), fg, anchor="lm")


def _empty(ctx, inner, txt, fg):
    x, y, w, h = inner
    ctx.text((x, y + 2), ctx.fit(txt, font(17, "regular"), w), font(17, "regular"), fg)


# ------------------------------------------------------------------ Widgets
def w_date(ctx: Ctx, box, props, data, today: date):
    (x, y, w, h), fg = _card(ctx, box, props, "none")
    title = str(props.get("title") or "").strip()
    date_s = f"{WD[today.weekday()]}, {today.day}. {MONTHS[today.month - 1]}"
    if props.get("show_year"):
        date_s += f" {today.year}"
    align = props.get("align") if props.get("align") in ("left", "center", "right") else "left"
    ax = {"left": x, "center": x + w / 2, "right": x + w}[align]
    a1 = {"left": "ls", "center": "ms", "right": "rs"}[align]
    if title:
        s1 = int(h * 0.56)
        while s1 > 14 and ctx.tw(title, font(s1, "medium")) > w:
            s1 -= 2
        s2 = max(12, int(h * 0.3))
        ctx.text((ax, y + s1 * 0.82), title, font(s1, "medium"), fg, anchor=a1)
        ctx.text((ax, y + s1 * 0.82 + s2 * 1.15), ctx.fit(date_s, font(s2, "regular"), w), font(s2, "regular"), fg,
                 anchor=a1)
    else:
        top = WD[today.weekday()]
        bottom = f"{today.day}. {MONTHS[today.month - 1]}" + (f" {today.year}" if props.get("show_year") else "")
        s1 = max(12, int(h * 0.26))
        s2 = max(16, int(h * 0.64))
        while ctx.tw(bottom, font(s2, "medium")) > w and s2 > 16:
            s2 -= 2
        ctx.text((ax, y + s1 * 0.95), top, font(s1, "regular"), "accent" if fg == ctx.fg else fg, anchor=a1)
        ctx.text((ax - (s2 * 0.04 if align == "left" else 0), y + h - s2 * 0.08), bottom, font(s2, "medium"), fg,
                 anchor=a1)


def w_weather_now(ctx: Ctx, box, props, data, today):
    inner, fg = _card(ctx, box, props, "none")
    inner = _title(ctx, inner, props, fg)
    x, y, w, h = inner
    now = (data or {}).get("now")
    if not now:
        ctx.icon(x + h / 2, y + h / 2, "weather-cloudy-alert", h * 0.6, "fg")
        ctx.text((x + h + 10, y + h / 2), "Wetterdaten nicht verfügbar", font(18, "regular"), fg, anchor="lm")
        return
    isz = min(h, w * 0.44)
    wx_icon(ctx, x + isz / 2, y + h / 2, isz, now.get("cond"))
    tx0 = x + isz + 8
    cx = (tx0 + x + w) / 2
    avail = x + w - tx0
    t = fmt_temp(now.get("temp")).rstrip("°")
    size = int(h * 0.56)
    uf = font(max(14, size * 0.36), "regular")
    while size > 20 and ctx.tw(t, font(size, "regular")) + ctx.tw("°C", uf) + 4 > avail:
        size -= 2
        uf = font(max(14, size * 0.36), "regular")
    tf = font(size, "regular")
    total = ctx.tw(t, tf) + 3 + ctx.tw("°C", uf)
    sub = []
    if props.get("show_condition"):
        sub.append(COND.get(now.get("cond"), now.get("cond") or ""))
    if now.get("feels") is not None:
        sub.append(f"Gefühlt {fmt_temp(now['feels'])}")
    elif not sub:
        sub.append(COND.get(now.get("cond"), now.get("cond") or ""))
    small = max(13, int(h * 0.12))
    cap = size * 0.7
    block = cap + 14 + small
    base = y + (h - block) / 2 + cap
    sx = cx - total / 2
    ctx.text((sx, base), t, tf, fg, anchor="ls")
    ctx.text((sx + ctx.tw(t, tf) + 3, base - cap + uf.size * 0.72), "°C", uf, fg, anchor="ls")
    ctx.text((cx, base + 14 + small * 0.85), ctx.fit(" · ".join(sub), font(small, "regular"), avail),
             font(small, "regular"), fg, anchor="ms")


def w_weather_details(ctx: Ctx, box, props, data, today):
    inner, fg = _card(ctx, box, props, "none")
    inner = _title(ctx, inner, props, fg)
    x, y, w, h = inner
    items = (data or {}).get("items") or []
    if not items:
        _empty(ctx, inner, "Angaben wählen", fg)
        return
    cols = max(1, int(props.get("columns", 2)))
    rows = math.ceil(len(items) / cols)
    cw, rh = w / cols, h / rows
    isz = min(rh * 0.78, 34)
    lf = font(max(11, min(15, rh * 0.3)), "regular")
    vf = font(max(13, min(22, rh * 0.46)), "medium")
    uf = font(max(10, min(13, rh * 0.27)), "regular")
    for i, it in enumerate(items):
        c0 = x + (i % cols) * cw
        cy = y + (i // cols) * rh + rh / 2
        col = it.get("color", "fg") if fg == ctx.fg else fg
        ctx.icon(c0 + isz / 2 + 4, cy, it.get("icon"), isz, col)
        tx0 = c0 + isz + 12
        mid = (tx0 + c0 + cw) / 2
        tw_ = c0 + cw - tx0
        ctx.text((mid, cy - 1), ctx.fit(it.get("label", ""), lf, tw_), lf, fg, anchor="ms")
        v = str(it.get("value", "–"))
        u = str(it.get("unit") or "")
        total = ctx.tw(v, vf) + (ctx.tw(u, uf) + 2 if u else 0)
        vx = mid - total / 2
        ctx.text((vx, cy + vf.size * 0.95), v, vf, fg, anchor="ls")
        if u:
            ctx.text((vx + ctx.tw(v, vf) + 2, cy + vf.size * 0.95), u, uf, fg, anchor="ls")


def w_weather_forecast(ctx: Ctx, box, props, data, today):
    inner, fg = _card(ctx, box, props, "none")
    inner = _title(ctx, inner, props, fg)
    x, y, w, h = inner
    days = ((data or {}).get("forecast") or [])[: max(1, min(int(props.get("days", 5)), 7))]
    if not days:
        _empty(ctx, inner, "Keine Vorhersage", fg)
        return
    n = len(days)
    gap = int(props.get("gap", 12))
    cw = (w - gap * (n - 1)) / n
    lbl = max(13, min(20, h * 0.16))
    tsz = max(11, min(16, h * 0.12))
    filled = props.get("boxes", "outline") == "card"
    for i, f in enumerate(days):
        bx = (int(x + i * (cw + gap)), int(y), int(cw), int(h))
        if filled:
            ctx.soft(bx, ctx.t["card"], radius=8)
        if props.get("boxes", "outline") != "none":
            ctx.outline(bx, radius=8, color="fg")
        cx = bx[0] + cw / 2
        ctx.text((cx, y + 6 + lbl), WD_SHORT[f["date"].weekday()], font(lbl, "medium"), "fg", anchor="ms")
        top = y + lbl + 12
        bottom = y + h - tsz - 12
        isz = max(16, min(cw * 0.74, (bottom - top) * 1.15))
        wx_icon(ctx, cx, (top + bottom) / 2, isz, f.get("cond"))
        s = f"{fmt_temp(f.get('hi'))} / {fmt_temp(f.get('lo'))}"
        ctx.text((cx, y + h - 8), ctx.fit(s, font(tsz, "regular"), cw - 6), font(tsz, "regular"), "fg", anchor="md")


LINE_ORANGE = (244, 150, 66)


def w_weather_chart(ctx: Ctx, box, props, data, today):
    inner, fg = _card(ctx, box, props, "none")
    inner = _title(ctx, inner, props, fg)
    x, y, w, h = inner
    pts = ((data or {}).get("hourly") or [])[: int(props.get("hours", 24))]
    if len(pts) < 2:
        _empty(ctx, inner, "Keine stündliche Vorhersage", fg)
        return
    lf = font(12, "regular")
    left, right, bottom = 34, 38, 18
    gx, gy, gw, gh = x + left, y + 2, w - left - right, h - bottom - 4
    temps = [p["temp"] for p in pts if p.get("temp") is not None]
    tmin, tmax = math.floor(min(temps)), math.ceil(max(temps))
    if tmax - tmin < 4:
        mid = (tmax + tmin) / 2
        tmin, tmax = math.floor(mid - 2), math.ceil(mid + 2)
    n = len(pts)
    X = [gx + i * gw / (n - 1) for i in range(n)]
    Y = [gy + gh - (p.get("temp", tmin) - tmin) / (tmax - tmin) * gh for p in pts]
    bw = max(2, gw / n * 0.62)
    for i, p in enumerate(pts):
        pr = p.get("rain")
        if pr:
            bh = gh * min(1, pr / 100)
            ctx.soft((X[i] - bw / 2, gy + gh - bh, bw, bh), (150, 160, 190))
    if ctx.mode == "paint":
        poly = list(zip(X, Y, strict=True)) + [(X[-1], gy + gh), (X[0], gy + gh)]
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).polygon(poly, fill=255)
        ctx.paint.paste(Image.new("RGB", (W, H), (255, 228, 200)), (0, 0), m)
        ctx.pd.line(list(zip(X, Y, strict=True)), fill=LINE_ORANGE, width=4, joint="curve")
    ctx.text((x + left - 6, gy), fmt_temp(tmax), lf, fg, anchor="rt")
    ctx.text((x + left - 6, gy + gh), fmt_temp(tmin), lf, fg, anchor="rs")
    ctx.text((x + w, gy), "100%", lf, fg, anchor="rt")
    ctx.text((x + w, gy + gh), "0%", lf, fg, anchor="rs")
    every = int(props.get("label_every", 2))
    for i in range(0, n, max(1, every)):
        ctx.text((X[i], y + h), pts[i].get("label", ""), lf, fg, anchor="md")


def w_status(ctx: Ctx, box, props, data, today):
    """Statuszeile: Aktualisierungszeit, WLAN und Akku des Rahmens."""
    (x, y, w, h), fg = _card(ctx, box, props, "none")
    d = data or {}
    f = font(max(11, min(16, h * 0.62)), "regular")
    isz = f.size * 1.35
    cy = y + h / 2
    parts = []
    if props.get("show_time", True) and d.get("time"):
        parts.append(("refresh", d["time"], "fg"))
    wifi = d.get("wifi")
    if props.get("show_wifi", True):
        if wifi and wifi.get("dbm") is not None:
            dbm = wifi["dbm"]
            lvl = 4 if dbm >= -55 else 3 if dbm >= -65 else 2 if dbm >= -75 else 1
            parts.append((f"wifi-strength-{lvl}", wifi.get("label", ""), "fg"))
        elif wifi is not None:
            parts.append(("wifi-strength-off-outline", "Kein WLAN", "red"))
    bat = d.get("battery")
    if props.get("show_battery", True) and bat:
        pct = bat.get("percent")
        if pct is None:
            parts.append(("power-plug-outline", "Netz", "fg"))
        else:
            step = max(10, min(100, int(round(pct / 10.0)) * 10))
            name = "battery" if step == 100 else f"battery-{step}"
            if bat.get("charging"):
                name = "battery-charging-" + str(max(10, step)) if step < 100 else "battery-charging-100"
            parts.append((name, f"{round(pct)} %", "red" if pct < 20 and not bat.get("charging") else "fg"))
    widths = [isz + 4 + ctx.tw(t, f) for _, t, _ in parts]
    total = sum(widths) + 16 * max(0, len(parts) - 1)
    align = props.get("align", "right")
    cx = x if align == "left" else (x + (w - total) / 2 if align == "center" else x + w - total)
    for (ic, t, c), wd in zip(parts, widths, strict=True):
        ctx.icon(cx + isz / 2, cy, ic, isz, c)
        ctx.text((cx + isz + 4, cy + 1), t, f, c if c == "red" else fg, anchor="lm")
        cx += wd + 16


def w_waste(ctx: Ctx, box, props, data, today):
    inner, fg = _card(ctx, box, props, "card")
    inner = _title(ctx, inner, props, fg, "trash-can-outline")
    x, y, w, h = inner
    rows = (data or {}).get("rows") or []
    if not rows:
        _empty(ctx, inner, props.get("empty") or "Keine Termine", fg)
        return
    row_h = int(props.get("row_height", 36))
    fs = max(14, int(row_h * 0.5))

    def draw(r, ry, rh):
        cy = ry + rh / 2
        dia = rh * 0.78
        bc = r.get("color", "black")
        bc = bc if bc in PURE else "black"
        if bc == "white" or (bc == "black" and ctx.dark):
            bc = "fg"
        ctx.solid((x, cy - dia / 2, dia, dia), bc, shape="ellipse")
        ctx.icon(x + dia / 2, cy, r.get("icon") or "trash-can", dia * 0.56, ON[ctx.col(bc)])
        tx = x + dia + 12
        if r.get("soon"):
            x0 = ctx.pill(x + w, cy, r["when"], font(fs - 1, "medium"), "accent", pad=12, h=int(rh * 0.7))
        else:
            fr = font(fs, "regular")
            x0 = x + w - ctx.tw(r["when"], fr)
            ctx.text((x + w, cy + 1), r["when"], fr, fg, anchor="rm")
        ctx.text((tx, cy + 1), ctx.fit(r["name"], font(fs, "medium"), x0 - tx - 10), font(fs, "medium"), fg, anchor="lm")

    _rows(ctx, inner, rows, row_h, draw, fg)


def w_calendar(ctx: Ctx, box, props, data, today):
    inner, fg = _card(ctx, box, props, "card")
    inner = _title(ctx, inner, props, fg, "calendar-blank-outline")
    x, y, w, h = inner
    rows = (data or {}).get("rows") or []
    if not rows:
        _empty(ctx, inner, props.get("empty") or "Keine Termine", fg)
        return
    row_h = int(props.get("row_height", 50))
    tile = int(row_h * 0.84)
    fs = max(14, int(row_h * 0.36))

    def draw(r, ry, rh):
        d: date = r["date"]
        delta = (d - today).days
        ty = ry + (rh - tile) / 2
        if delta <= 1:
            ctx.solid((x, ty, tile, tile), "accent", radius=10)
            tc = ON[ctx.accent]
        else:
            ctx.outline((x, ty, tile, tile), radius=10, color="fg", width=2)
            tc = "fg"
        ctx.text((x + tile / 2, ty + tile * 0.56), str(d.day), font(tile * 0.48, "medium"), tc, anchor="ms")
        ctx.text((x + tile / 2, ty + tile * 0.86), MONTHS_SHORT[d.month - 1], font(max(10, tile * 0.22), "regular"),
                 tc, anchor="ms")
        tx = x + tile + 14
        cy = ry + rh / 2
        sub = "Heute" if delta == 0 else "Morgen" if delta == 1 else WD[d.weekday()]
        if r.get("time"):
            sub += f", {r['time']} Uhr"
        ctx.text((tx, cy + 1), ctx.fit(r.get("text", ""), font(fs, "medium"), x + w - tx), font(fs, "medium"), fg,
                 anchor="ls")
        ctx.text((tx, cy + 4), ctx.fit(sub, font(max(11, fs - 3), "regular"), x + w - tx),
                 font(max(11, fs - 3), "regular"), fg, anchor="lt")

    _rows(ctx, inner, rows, row_h, draw, fg)


def w_entity(ctx: Ctx, box, props, data, today):
    inner, fg = _card(ctx, box, props, "card")
    x, y, w, h = inner
    if not data:
        _empty(ctx, inner, "Entität wählen", fg)
        return
    isz = int(min(h * 0.3, 40))
    ctx.icon(x + isz / 2, y + isz / 2, props.get("icon") or data.get("icon"), isz,
             "accent" if fg == ctx.fg and not ctx.dark else fg)
    label = props.get("title") or data.get("name", "")
    lf = font(max(13, int(h * 0.13)), "regular")
    ctx.text((x, y + h), ctx.fit(label, lf, w), lf, fg, anchor="ld")
    val, unit = str(data.get("value", "–")), str(data.get("unit") or "")
    base = y + h - lf.size * 1.8
    size = int(h * 0.46)
    while size > 14:
        uf = font(max(11, int(size * 0.34)), "regular")
        if ctx.tw(val, font(size, "light")) + (ctx.tw(unit, uf) + 6 if unit else 0) <= w:
            break
        size -= 2
    vf = font(size, "light")
    uf = font(max(11, int(size * 0.34)), "regular")
    ctx.text((x - size * 0.03, base), val, vf, fg, anchor="ls")
    if unit:
        ctx.text((x + ctx.tw(val, vf) + 5, base), unit, uf, fg, anchor="ls")


def w_entities(ctx: Ctx, box, props, data, today):
    inner, fg = _card(ctx, box, props, "card")
    inner = _title(ctx, inner, props, fg, "view-list-outline")
    x, y, w, h = inner
    rows = (data or {}).get("rows") or []
    if not rows:
        _empty(ctx, inner, "Entitäten wählen", fg)
        return
    row_h = int(props.get("row_height", 40))
    fs = max(14, int(row_h * 0.44))

    def draw(r, ry, rh):
        cy = ry + rh / 2
        isz = rh * 0.62
        ctx.icon(x + isz / 2, cy, r.get("icon"), isz, "accent" if fg == ctx.fg and not ctx.dark else fg)
        tx = x + isz + 12
        v = str(r.get("value", "–")) + (f" {r['unit']}" if r.get("unit") else "")
        fv = font(fs, "medium")
        ctx.text((x + w, cy + 1), v, fv, fg, anchor="rm")
        avail = x + w - tx - ctx.tw(v, fv) - 12
        ctx.text((tx, cy + 1), ctx.fit(r.get("name", ""), font(fs, "regular"), avail), font(fs, "regular"), fg, anchor="lm")

    _rows(ctx, inner, rows, row_h, draw, fg)


def w_todo(ctx: Ctx, box, props, data, today):
    inner, fg = _card(ctx, box, props, "card")
    inner = _title(ctx, inner, props, fg, "format-list-checks")
    x, y, w, h = inner
    rows = (data or {}).get("rows") or []
    if not rows:
        _empty(ctx, inner, props.get("empty") or "Alles erledigt", fg)
        return
    row_h = int(props.get("row_height", 36))
    fs = max(14, int(row_h * 0.48))

    def draw(r, ry, rh):
        cy = ry + rh / 2
        rr = rh * 0.25
        ctx.outline((x, cy - rr, 2 * rr, 2 * rr), radius=int(rr), color="fg", width=2)
        tx = x + 2 * rr + 12
        ctx.text((tx, cy + 1), ctx.fit(r.get("text", ""), font(fs, "regular"), x + w - tx), font(fs, "regular"), fg,
                 anchor="lm")

    _rows(ctx, inner, rows, row_h, draw, fg)


def w_text(ctx: Ctx, box, props, data, today):
    (x, y, w, h), fg = _card(ctx, box, props, "none")
    txt = str(props.get("text", ""))
    size = int(props.get("size", 28))
    f = font(size, props.get("weight", "medium"))
    color = props.get("color") or "fg"
    if fg != "fg":
        color = fg
    align = props.get("align") if props.get("align") in ("left", "center", "right") else "left"
    lines, cur = [], ""
    for word in txt.split():
        test = (cur + " " + word).strip()
        if ctx.tw(test, f) <= w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    lh = size * 1.2
    lines = lines[: max(1, int(h // lh))]
    ty = y + (h - lh * len(lines)) / 2
    ax = {"left": x, "center": x + w / 2, "right": x + w}[align]
    anchor = {"left": "la", "center": "ma", "right": "ra"}[align]
    for ln in lines:
        ctx.text((ax, ty), ctx.fit(ln, f, w), f, color, anchor=anchor)
        ty += lh


def w_divider(ctx: Ctx, box, props, data, today):
    x, y, w, h = box
    col = props.get("color") or "fg"
    t = int(props.get("thickness", 1))
    if w >= h:
        ctx.line([x, y + h / 2, x + w, y + h / 2], col, t)
    else:
        ctx.line([x + w / 2, y, x + w / 2, y + h], col, t)


WIDGETS = {
    "date": w_date, "weather_now": w_weather_now, "weather_details": w_weather_details,
    "weather_forecast": w_weather_forecast, "weather_chart": w_weather_chart,
    "waste": w_waste, "calendar": w_calendar, "entity": w_entity, "entities": w_entities,
    "todo": w_todo, "text": w_text, "divider": w_divider, "status": w_status,
}


# ------------------------------------------------------------------ Dithering und Ausgabe
def _palette_image(colors: dict[str, tuple[int, int, int]]) -> Image.Image:
    pal = Image.new("P", (1, 1))
    flat: list[int] = []
    for n in ORDER:
        flat += colors[n]
    pal.putpalette(flat + [0, 0, 0] * (256 - len(ORDER)))
    return pal


_BAYER8 = [
    [0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21],
]


@lru_cache(maxsize=1)
def _threshold() -> Image.Image:
    tile = Image.new("L", (8, 8))
    tile.putdata([int((v + 0.5) * 4) for row in _BAYER8 for v in row])
    full = Image.new("L", (W, H))
    for yy in range(0, H, 8):
        for xx in range(0, W, 8):
            full.paste(tile, (xx, yy))
    return full


def _ordered_bw(gray: Image.Image) -> Image.Image:
    """Gleichmäßiges Raster (Bayer) für Grautöne – ohne Streifenmuster."""
    th = _threshold()
    if gray.size != th.size:
        th = th.resize(gray.size)
    diff = ImageChops.subtract(gray, th, scale=1.0, offset=128)
    return diff.point(lambda v: 255 if v >= 128 else 0).convert("RGB")


def _dither(paint: Image.Image) -> Image.Image:
    """Floyd-Steinberg auf die gemessenen Panelfarben, Ausgabe in reinen Farben.

    Neutrale Flächen (Grau, Weiß) werden nur aus Schwarz und Weiß gemischt,
    damit sie ruhig wirken und keine bunten Punkte bekommen.
    """
    lo, hi = SEEN["black"], SEEN["white"]
    lut: list[int] = []
    for c in range(3):
        lut += [int(lo[c] + v * (hi[c] - lo[c]) / 255) for v in range(256)]
    q = paint.point(lut).quantize(palette=_palette_image(SEEN), dither=Image.Dither.FLOYDSTEINBERG)
    q.putpalette(_palette_image(PURE).getpalette())
    color = q.convert("RGB")
    bw = _ordered_bw(paint.convert("L"))
    r, g, b = paint.split()
    chroma = ImageChops.subtract(ImageChops.lighter(ImageChops.lighter(r, g), b),
                                 ImageChops.darker(ImageChops.darker(r, g), b))
    neutral = chroma.point(lambda v: 255 if v < 26 else 0)
    return Image.composite(bw, color, neutral)


def render_image(layout: dict[str, Any], data: dict[str, Any], today: date,
                 error: str | None = None) -> Image.Image:
    """Bild in den reinen Panelfarben (so wird es an den Rahmen geschickt)."""
    theme = layout.get("theme") or {}
    t = THEMES.get(theme.get("mode"), THEMES["light"])
    paint = Image.new("RGB", (W, H), t["bg"])
    ctx = Ctx(paint, theme)
    items = []
    for wd in layout.get("widgets") or []:
        fn = WIDGETS.get(wd.get("type"))
        if fn:
            box = (int(wd.get("x", 0)), int(wd.get("y", 0)), max(10, int(wd.get("w", 100))), max(10, int(wd.get("h", 50))))
            items.append((fn, wd, box))
    failed: dict[int, str] = {}
    for stage in ("paint", "ink"):
        if stage == "ink":
            ctx.start_ink(_dither(paint))
        for i, (fn, wd, box) in enumerate(items):
            if i in failed:
                continue
            try:
                fn(ctx, box, wd.get("props") or {}, (data or {}).get(wd.get("id")), today)
            except Exception as err:  # noqa: BLE001 – ein defektes Widget soll nicht alles stoppen
                failed[i] = str(err)
    img = ctx.ink_img
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    for i, msg in failed.items():
        x, y, w, h = items[i][2]
        d.rectangle([x, y, x + w, y + h], outline=PURE["red"], width=2)
        d.text((x + 6, y + 6), ctx.fit(f"Fehler: {msg}", font(14, "medium"), w - 12), font=font(14, "medium"),
               fill=PURE["red"])
    if error:
        f = font(14, "medium")
        d.rectangle([0, H - 22, W, H], fill=PURE["red"])
        d.text((10, H - 11), ctx.fit(error, f, W - 20), font=f, fill=PURE["white"], anchor="lm")
    return img


def simulate(img: Image.Image) -> Image.Image:
    """Zeigt das Bild mit den Farben, die das Panel tatsächlich darstellt."""
    q = img.quantize(palette=_palette_image(PURE), dither=Image.Dither.NONE)
    q.putpalette(_palette_image(SEEN).getpalette())
    return q.convert("RGB")


def to_png(img: Image.Image, rotation: int = 0) -> bytes:
    if rotation:
        img = img.rotate(rotation, expand=True)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render(layout: dict[str, Any], data: dict[str, Any], today: date,
           rotation: int = 0, error: str | None = None) -> bytes:
    return to_png(render_image(layout, data, today, error), rotation)
