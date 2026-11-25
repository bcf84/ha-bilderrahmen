"""Zeichnet ein Layout aus Widgets für den 6-Farben-E-Paper-Rahmen (800x480).

Reines Pillow ohne Home-Assistant-Abhängigkeiten. Eingabe:
  layout = {"theme": {...}, "widgets": [{"id", "type", "x", "y", "w", "h", "props"}]}
  data   = {widget_id: <vom Manager vorbereitete Daten>}
"""

from __future__ import annotations

import io
import json
import os
from datetime import date
from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw, ImageFont

W, H = 800, 480
PALETTE = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "yellow": (255, 255, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
}
ON = {"black": "white", "white": "black", "red": "white", "blue": "white",
      "green": "black", "yellow": "black"}

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
# Wetter: (Icon, Farbe des runden Abzeichens)
COND_ICON = {
    "sunny": ("weather-sunny", "yellow"),
    "clear-night": ("weather-night", "black"),
    "partlycloudy": ("weather-partly-cloudy", "yellow"),
    "cloudy": ("weather-cloudy", "black"),
    "fog": ("weather-fog", "black"),
    "rainy": ("weather-rainy", "blue"),
    "pouring": ("weather-pouring", "blue"),
    "snowy": ("weather-snowy", "blue"),
    "snowy-rainy": ("weather-snowy-rainy", "blue"),
    "hail": ("weather-hail", "blue"),
    "lightning": ("weather-lightning", "red"),
    "lightning-rainy": ("weather-lightning-rainy", "red"),
    "windy": ("weather-windy", "green"),
    "windy-variant": ("weather-windy-variant", "green"),
    "exceptional": ("alert-circle-outline", "red"),
}

HERE = os.path.dirname(__file__)
FONT_DIR = os.path.join(HERE, "fonts")
FONT_FILES = {
    "regular": "Inter-Regular.ttf",
    "medium": "Inter-Medium.ttf",
    "semibold": "Inter-SemiBold.ttf",
    "bold": "Inter-Bold.ttf",
    "display": "InterDisplay-Bold.ttf",
    "display-semi": "InterDisplay-SemiBold.ttf",
}


@lru_cache(maxsize=128)
def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(
        os.path.join(FONT_DIR, FONT_FILES.get(weight, FONT_FILES["regular"])), max(6, int(size))
    )


@lru_cache(maxsize=64)
def icon_font(size: int) -> ImageFont.FreeTypeFont:
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


# ------------------------------------------------------------------ Zeichenhilfe
class Ctx:
    def __init__(self, img: Image.Image, theme: dict[str, Any]) -> None:
        self.img = img
        self.d = ImageDraw.Draw(img)
        self.d.fontmode = "1"  # E-Paper: scharfe Kanten statt gedithertem Rand
        dark = theme.get("mode") == "dark"
        self.bg_name = "black" if dark else "white"
        self.fg_name = "white" if dark else "black"
        acc = theme.get("accent", "red")
        self.accent_name = acc if acc in PALETTE and acc != self.bg_name else "red"

    def name(self, n: str) -> str:
        return {"fg": self.fg_name, "bg": self.bg_name, "accent": self.accent_name}.get(n, n)

    def c(self, n: str) -> tuple[int, int, int]:
        return PALETTE.get(self.name(n), PALETTE["black"])

    def on(self, n: str) -> str:
        return ON.get(self.name(n), "black")

    def tw(self, txt: str, f) -> float:
        return self.d.textlength(str(txt), font=f) if txt else 0

    def fit(self, txt: Any, f, width: float) -> str:
        txt = str(txt)
        if self.tw(txt, f) <= width:
            return txt
        while txt and self.tw(txt + "…", f) > width:
            txt = txt[:-1]
        return (txt.rstrip() + "…") if txt else ""

    def text(self, xy, txt, f, fill, anchor="la"):
        self.d.text(xy, str(txt), font=f, fill=self.c(fill), anchor=anchor)

    def tracked(self, x, y, txt, f, fill, tracking=1.5):
        for ch in txt:
            self.d.text((x, y), ch, font=f, fill=self.c(fill), anchor="ls")
            x += self.tw(ch, f) + tracking
        return x

    def icon(self, cx, cy, name, size, fill):
        ch = icon_char(name)
        if ch:
            self.d.text((cx, cy), ch, font=icon_font(size), fill=self.c(fill), anchor="mm")

    def badge(self, cx, cy, dia, icon, color):
        r = dia / 2
        self.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=self.c(color))
        self.icon(cx, cy, icon, dia * 0.62, self.on(color))

    def pill(self, x1, cy, txt, f, color, pad=10, h=None) -> float:
        """Rechtsbündige Pille bis x1; liefert die linke Kante."""
        h = h or int(f.size * 1.5)
        w = self.tw(txt, f) + 2 * pad
        x0 = x1 - w
        self.d.rounded_rectangle([x0, cy - h / 2, x1, cy + h / 2], radius=h / 2, fill=self.c(color))
        self.d.text(((x0 + x1) / 2, cy), txt, font=f, fill=self.c(self.on(color)), anchor="mm")
        return x0


def fmt_temp(t) -> str:
    try:
        return f"{round(float(t))}°"
    except (TypeError, ValueError):
        return "–"


# ------------------------------------------------------------------ Karte und Titel
def _frame(ctx: Ctx, box, props):
    """Zeichnet den Kartenstil; liefert Innenbereich, Textfarbe und Akzentfarbe."""
    x, y, w, h = box
    style = props.get("style", "plain")
    r = int(props.get("radius", 20))
    if style == "outline":
        ctx.d.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=r, outline=ctx.c("fg"), width=3)
        return (x + 18, y + 14, w - 36, h - 28), "fg", "accent"
    if style in ("filled", "accent"):
        col = ctx.name("fg" if style == "filled" else "accent")
        ctx.d.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=r, fill=PALETTE[col])
        on = ON[col]
        acc = ctx.accent_name if style == "filled" and ctx.accent_name not in (col, ctx.fg_name) else on
        return (x + 18, y + 14, w - 36, h - 28), on, acc
    return (x, y, w, h), "fg", "accent"


def _title(ctx: Ctx, inner, props, fg, acc, default_icon=None):
    title = str(props.get("title") or "").strip()
    if not title:
        return inner
    x, y, w, h = inner
    f = font(16, "bold")
    ic = props.get("icon") or default_icon
    tx = x
    if ic and icon_char(ic):
        ctx.icon(x + 11, y + 10, ic, 22, acc)
        tx = x + 30
    ctx.tracked(tx, y + 16, ctx.fit(title.upper(), f, w - (tx - x)), f, fg, tracking=1.4)
    return (x, y + 32, w, h - 32)


def _rows(ctx, inner, rows, row_h, draw_row, fg):
    x, y, w, h = inner
    fit = max(0, int((h + 6) // row_h))
    shown = rows if len(rows) <= fit else rows[: max(0, fit - 1)]
    for i, r in enumerate(shown):
        draw_row(r, y + i * row_h, row_h)
    rest = len(rows) - len(shown)
    if rest > 0:
        ctx.text((x, y + len(shown) * row_h + row_h / 2), f"+ {rest} weitere", font(15, "semibold"), fg, anchor="lm")


def _empty(ctx, inner, txt, fg):
    x, y, w, h = inner
    ctx.text((x, y + 4), ctx.fit(txt, font(17, "medium"), w), font(17, "medium"), fg)


# ------------------------------------------------------------------ Widgets
def w_date(ctx: Ctx, box, props, data, today: date):
    (x, y, w, h), fg, acc = _frame(ctx, box, props)
    top = WD[today.weekday()]
    bottom = f"{today.day}. {MONTHS[today.month - 1]}"
    if props.get("show_year"):
        bottom += f" {today.year}"
    s1 = max(12, int(h * 0.27))
    s2 = max(16, int(h * 0.58))
    while ctx.tw(bottom, font(s2, "display")) > w and s2 > 16:
        s2 -= 2
    ctx.text((x, y + s1 * 0.95), ctx.fit(top.upper(), font(s1, "bold"), w), font(s1, "bold"), acc, anchor="ls")
    ctx.text((x - 2, y + h), bottom, font(s2, "display"), fg, anchor="ld")


def w_weather_now(ctx: Ctx, box, props, data, today):
    inner, fg, acc = _frame(ctx, box, props)
    inner = _title(ctx, inner, props, fg, acc)
    x, y, w, h = inner
    now = (data or {}).get("now")
    if not now:
        _empty(ctx, inner, "Wetter nicht verfügbar", fg)
        return
    cond = now.get("cond")
    ic, col = COND_ICON.get(cond, ("weather-cloudy", "black"))
    if col in (ctx.bg_name,) or (fg != "fg" and col == ctx.name("fg")):
        col = acc
    dia = int(min(h, w * 0.4))
    ctx.badge(x + dia / 2, y + h / 2, dia, ic, col)
    tx = x + dia + max(16, int(w * 0.05))
    avail = x + w - tx
    t = fmt_temp(now.get("temp"))
    size = int(h * 0.6)
    while size > 20 and ctx.tw(t, font(size, "display")) > avail:
        size -= 2
    small = max(13, int(h * 0.13))
    cap = size * 0.73
    block = cap + 12 + small * 2.5
    base = y + (h - block) / 2 + cap
    ctx.text((tx - size * 0.04, base), t, font(size, "display"), fg, anchor="ls")
    line = base + 12 + small
    ctx.text((tx, line), ctx.fit(COND.get(cond, cond or ""), font(small, "bold"), avail),
             font(small, "bold"), fg, anchor="ls")
    td = (data or {}).get("today")
    if td:
        line += small * 1.5
        fx = font(small, "medium")
        cx = tx
        for arrow, val in (("arrow-down-thin", td.get("lo")), ("arrow-up-thin", td.get("hi"))):
            ctx.icon(cx + small * 0.45, line - small * 0.36, arrow, small * 1.25, acc)
            cx += small * 1.0
            s = fmt_temp(val)
            ctx.text((cx, line), s, fx, fg, anchor="ls")
            cx += ctx.tw(s, fx) + small * 0.9


def w_weather_forecast(ctx: Ctx, box, props, data, today):
    inner, fg, acc = _frame(ctx, box, props)
    inner = _title(ctx, inner, props, fg, acc)
    x, y, w, h = inner
    days = ((data or {}).get("forecast") or [])[: max(1, min(int(props.get("days", 3)), 7))]
    if not days:
        _empty(ctx, inner, "Keine Vorhersage", fg)
        return
    n = len(days)
    cw = w / n
    lbl = max(12, int(h * 0.15))
    tsz = max(12, int(h * 0.15))
    dia = int(max(16, min(cw * 0.6, h - lbl * 1.5 - tsz * 1.5 - 16)))
    for i, f in enumerate(days):
        cx = x + cw * i + cw / 2
        ctx.text((cx, y + lbl * 0.95), WD_SHORT[f["date"].weekday()].upper(), font(lbl, "bold"), fg, anchor="ms")
        ic, col = COND_ICON.get(f.get("cond"), ("weather-cloudy", "black"))
        if col == ctx.bg_name or (fg != "fg" and col == ctx.name("fg")):
            col = acc
        top = y + lbl * 1.3 + 4
        bottom = y + h - tsz * 1.4
        ctx.badge(cx, (top + bottom) / 2, dia, ic, col)
        hi, lo = fmt_temp(f.get("hi")), fmt_temp(f.get("lo"))
        fb, fr = font(tsz, "bold"), font(tsz, "regular")
        total = ctx.tw(hi, fb) + 7 + ctx.tw(lo, fr)
        sx = cx - total / 2
        ctx.text((sx, y + h), hi, fb, fg, anchor="ld")
        ctx.text((sx + ctx.tw(hi, fb) + 7, y + h), lo, fr, fg, anchor="ld")


def w_waste(ctx: Ctx, box, props, data, today):
    inner, fg, acc = _frame(ctx, box, props)
    inner = _title(ctx, inner, props, fg, acc, "trash-can-outline")
    x, y, w, h = inner
    rows = (data or {}).get("rows") or []
    if not rows:
        _empty(ctx, inner, props.get("empty") or "Keine Termine", fg)
        return
    row_h = int(props.get("row_height", 40))
    fs = max(13, int(row_h * 0.45))

    def draw(r, ry, rh):
        cy = ry + rh / 2
        dia = rh * 0.74
        col = r.get("color", "black")
        if col == ctx.bg_name:
            col = ctx.fg_name
        ring = col in ("yellow", "white", "green") and ctx.bg_name == "white"
        ctx.d.ellipse([x, cy - dia / 2, x + dia, cy + dia / 2], fill=PALETTE[col],
                      outline=ctx.c("fg") if ring else None, width=2)
        ctx.icon(x + dia / 2, cy, r.get("icon") or "trash-can", dia * 0.58, ON[col])
        tx = x + dia + 12
        if r.get("soon"):
            x0 = ctx.pill(x + w, cy, r["when"], font(fs - 1, "bold"), acc, pad=12, h=int(rh * 0.68))
        else:
            fr = font(fs, "medium")
            x0 = x + w - ctx.tw(r["when"], fr)
            ctx.text((x + w, cy), r["when"], fr, fg, anchor="rm")
        ctx.text((tx, cy), ctx.fit(r["name"], font(fs, "semibold"), x0 - tx - 10),
                 font(fs, "semibold"), fg, anchor="lm")

    _rows(ctx, inner, rows, row_h, draw, fg)


def w_calendar(ctx: Ctx, box, props, data, today):
    inner, fg, acc = _frame(ctx, box, props)
    inner = _title(ctx, inner, props, fg, acc, "calendar-blank-outline")
    x, y, w, h = inner
    rows = (data or {}).get("rows") or []
    if not rows:
        _empty(ctx, inner, props.get("empty") or "Keine Termine", fg)
        return
    row_h = int(props.get("row_height", 50))
    tile = int(row_h * 0.84)
    fs = max(13, int(row_h * 0.35))

    def draw(r, ry, rh):
        d: date = r["date"]
        delta = (d - today).days
        ty = ry + (rh - tile) / 2
        if delta <= 1:
            ctx.d.rounded_rectangle([x, ty, x + tile, ty + tile], radius=12, fill=ctx.c(acc))
            tc = ctx.on(acc)
        else:
            ctx.d.rounded_rectangle([x, ty, x + tile, ty + tile], radius=12, outline=ctx.c(fg), width=2)
            tc = fg
        ctx.text((x + tile / 2, ty + tile * 0.55), str(d.day), font(int(tile * 0.46), "display"), tc, anchor="ms")
        ctx.text((x + tile / 2, ty + tile * 0.84), MONTHS_SHORT[d.month - 1].upper(),
                 font(max(9, int(tile * 0.19)), "bold"), tc, anchor="ms")
        tx = x + tile + 14
        cy = ry + rh / 2
        sub = "Heute" if delta == 0 else "Morgen" if delta == 1 else WD[d.weekday()]
        if r.get("time"):
            sub += f" · {r['time']}"
        ctx.text((tx, cy - 2), ctx.fit(r.get("text", ""), font(fs, "semibold"), x + w - tx),
                 font(fs, "semibold"), fg, anchor="ls")
        ctx.text((tx, cy + 4), ctx.fit(sub, font(max(11, fs - 4), "medium"), x + w - tx),
                 font(max(11, fs - 4), "medium"), fg, anchor="lt")

    _rows(ctx, inner, rows, row_h, draw, fg)


def w_entity(ctx: Ctx, box, props, data, today):
    inner, fg, acc = _frame(ctx, box, props)
    x, y, w, h = inner
    if not data:
        _empty(ctx, inner, "Entität wählen", fg)
        return
    isz = int(min(h * 0.3, 40))
    ctx.icon(x + isz / 2, y + isz / 2, props.get("icon") or data.get("icon"), isz, acc)
    label = props.get("title") or data.get("name", "")
    lf = font(max(12, int(h * 0.12)), "semibold")
    ctx.text((x, y + h), ctx.fit(label, lf, w), lf, fg, anchor="ld")
    val, unit = str(data.get("value", "–")), str(data.get("unit") or "")
    base = y + h - lf.size * 2.0
    size = int(h * 0.44)
    while size > 14:
        uf = font(max(11, int(size * 0.36)), "semibold")
        if ctx.tw(val, font(size, "display")) + (ctx.tw(unit, uf) + 6 if unit else 0) <= w:
            break
        size -= 2
    vf = font(size, "display")
    uf = font(max(11, int(size * 0.36)), "semibold")
    ctx.text((x - size * 0.03, base), val, vf, fg, anchor="ls")
    if unit:
        ctx.text((x + ctx.tw(val, vf) + 6, base), unit, uf, fg, anchor="ls")


def w_entities(ctx: Ctx, box, props, data, today):
    inner, fg, acc = _frame(ctx, box, props)
    inner = _title(ctx, inner, props, fg, acc, "view-list-outline")
    x, y, w, h = inner
    rows = (data or {}).get("rows") or []
    if not rows:
        _empty(ctx, inner, "Entitäten wählen", fg)
        return
    row_h = int(props.get("row_height", 40))
    fs = max(13, int(row_h * 0.44))

    def draw(r, ry, rh):
        cy = ry + rh / 2
        isz = int(rh * 0.6)
        ctx.icon(x + isz / 2, cy, r.get("icon"), isz, acc)
        tx = x + isz + 10
        v = str(r.get("value", "–")) + (f" {r['unit']}" if r.get("unit") else "")
        fv = font(fs, "bold")
        ctx.text((x + w, cy), v, fv, fg, anchor="rm")
        avail = x + w - tx - ctx.tw(v, fv) - 12
        ctx.text((tx, cy), ctx.fit(r.get("name", ""), font(fs, "medium"), avail), font(fs, "medium"), fg, anchor="lm")

    _rows(ctx, inner, rows, row_h, draw, fg)


def w_todo(ctx: Ctx, box, props, data, today):
    inner, fg, acc = _frame(ctx, box, props)
    inner = _title(ctx, inner, props, fg, acc, "format-list-checks")
    x, y, w, h = inner
    rows = (data or {}).get("rows") or []
    if not rows:
        _empty(ctx, inner, props.get("empty") or "Alles erledigt", fg)
        return
    row_h = int(props.get("row_height", 36))
    fs = max(13, int(row_h * 0.47))

    def draw(r, ry, rh):
        cy = ry + rh / 2
        rr = rh * 0.25
        ctx.d.ellipse([x, cy - rr, x + 2 * rr, cy + rr], outline=ctx.c(acc), width=3)
        tx = x + 2 * rr + 12
        ctx.text((tx, cy), ctx.fit(r.get("text", ""), font(fs, "medium"), x + w - tx), font(fs, "medium"), fg, anchor="lm")

    _rows(ctx, inner, rows, row_h, draw, fg)


def w_text(ctx: Ctx, box, props, data, today):
    (x, y, w, h), fg, acc = _frame(ctx, box, props)
    txt = str(props.get("text", ""))
    size = int(props.get("size", 28))
    f = font(size, props.get("weight", "semibold"))
    color = props.get("color") or "fg"
    if fg != "fg":
        color = fg
    align = props.get("align", "left") if props.get("align") in ("left", "center", "right") else "left"
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
    lh = size * 1.22
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
    t = int(props.get("thickness", 2))
    if w >= h:
        ctx.d.line([x, y + h / 2, x + w, y + h / 2], fill=ctx.c(col), width=t)
    else:
        ctx.d.line([x + w / 2, y, x + w / 2, y + h], fill=ctx.c(col), width=t)


WIDGETS = {
    "date": w_date,
    "weather_now": w_weather_now,
    "weather_forecast": w_weather_forecast,
    "waste": w_waste,
    "calendar": w_calendar,
    "entity": w_entity,
    "entities": w_entities,
    "todo": w_todo,
    "text": w_text,
    "divider": w_divider,
}


def render_image(layout: dict[str, Any], data: dict[str, Any], today: date,
                 error: str | None = None) -> Image.Image:
    theme = layout.get("theme") or {}
    img = Image.new("RGB", (W, H), PALETTE["black" if theme.get("mode") == "dark" else "white"])
    ctx = Ctx(img, theme)
    for wd in layout.get("widgets") or []:
        fn = WIDGETS.get(wd.get("type"))
        if fn is None:
            continue
        box = (int(wd.get("x", 0)), int(wd.get("y", 0)),
               max(10, int(wd.get("w", 100))), max(10, int(wd.get("h", 50))))
        try:
            fn(ctx, box, wd.get("props") or {}, (data or {}).get(wd.get("id")), today)
        except Exception as err:  # noqa: BLE001 – ein defektes Widget soll nicht alles stoppen
            ctx.d.rectangle([box[0], box[1], box[0] + box[2], box[1] + box[3]], outline=PALETTE["red"], width=2)
            ctx.text((box[0] + 6, box[1] + 6), ctx.fit(f"Fehler: {err}", font(14, "medium"), box[2] - 12),
                     font(14, "medium"), "red")
    if error:
        f = font(14, "semibold")
        ctx.d.rectangle([0, H - 22, W, H], fill=PALETTE["red"])
        ctx.text((10, H - 11), ctx.fit(error, f, W - 20), f, "white", anchor="lm")
    return img


def to_png(img: Image.Image, rotation: int = 0) -> bytes:
    if rotation:
        img = img.rotate(rotation, expand=True)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render(layout: dict[str, Any], data: dict[str, Any], today: date,
           rotation: int = 0, error: str | None = None) -> bytes:
    return to_png(render_image(layout, data, today, error), rotation)
