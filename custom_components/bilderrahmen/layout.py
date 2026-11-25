"""Widget-Katalog, Standard-Layout und Prüfung von Layouts aus dem Editor."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from .render import H, W, WIDGETS

STYLE_FIELD = {
    "key": "style", "label": "Kartenstil", "type": "select", "default": "plain",
    "options": [
        {"value": "plain", "label": "Ohne Rahmen"},
        {"value": "outline", "label": "Umrandet"},
        {"value": "filled", "label": "Gefüllt (invertiert)"},
        {"value": "accent", "label": "Akzentfarbe"},
    ],
}
COLOR_OPTIONS = [
    {"value": "fg", "label": "Text (Schwarz/Weiß)"},
    {"value": "accent", "label": "Akzentfarbe"},
    {"value": "red", "label": "Rot"},
    {"value": "blue", "label": "Blau"},
    {"value": "green", "label": "Grün"},
    {"value": "yellow", "label": "Gelb"},
]


def _title(default: str = "") -> dict[str, Any]:
    return {"key": "title", "label": "Überschrift", "type": "text", "default": default}


def _rows(default: int) -> dict[str, Any]:
    return {"key": "row_height", "label": "Zeilenhöhe", "type": "number", "min": 24, "max": 90,
            "default": default, "unit": "px"}


CATALOG: list[dict[str, Any]] = [
    {"type": "date", "label": "Datum", "icon": "mdi:calendar-today", "w": 400, "h": 92,
     "fields": [{"key": "show_year", "label": "Jahr anzeigen", "type": "bool", "default": False}, STYLE_FIELD]},
    {"type": "weather_now", "label": "Wetter jetzt", "icon": "mdi:weather-partly-cloudy", "w": 400, "h": 150,
     "fields": [{"key": "entity", "label": "Wetter-Entität", "type": "entity", "domain": "weather"},
                _title(), STYLE_FIELD]},
    {"type": "weather_forecast", "label": "Wettervorhersage", "icon": "mdi:calendar-week", "w": 400, "h": 146,
     "fields": [{"key": "entity", "label": "Wetter-Entität", "type": "entity", "domain": "weather"},
                {"key": "days", "label": "Tage", "type": "number", "min": 1, "max": 7, "default": 4},
                _title(), STYLE_FIELD]},
    {"type": "waste", "label": "Müllabfuhr", "icon": "mdi:trash-can-outline", "w": 330, "h": 226,
     "fields": [{"key": "entities", "label": "Müll-Sensoren", "type": "entity", "domain": "sensor", "multiple": True},
                _title("Müllabfuhr"), _rows(40), STYLE_FIELD]},
    {"type": "calendar", "label": "Kalender", "icon": "mdi:calendar-blank-outline", "w": 330, "h": 210,
     "fields": [{"key": "entities", "label": "Kalender", "type": "entity", "domain": "calendar", "multiple": True},
                {"key": "days", "label": "Tage im Voraus", "type": "number", "min": 1, "max": 365, "default": 30},
                _title("Termine"), _rows(50), STYLE_FIELD]},
    {"type": "entity", "label": "Einzelwert", "icon": "mdi:numeric", "w": 180, "h": 150,
     "fields": [{"key": "entity", "label": "Entität", "type": "entity"},
                {"key": "title", "label": "Beschriftung (leer = Name)", "type": "text", "default": ""},
                {"key": "icon", "label": "Icon (z. B. mdi:thermometer)", "type": "text", "default": ""},
                STYLE_FIELD]},
    {"type": "entities", "label": "Werteliste", "icon": "mdi:view-list-outline", "w": 330, "h": 200,
     "fields": [{"key": "entities", "label": "Entitäten", "type": "entity", "multiple": True},
                _title("Zuhause"), _rows(40), STYLE_FIELD]},
    {"type": "todo", "label": "To-do-Liste", "icon": "mdi:format-list-checks", "w": 330, "h": 200,
     "fields": [{"key": "entity", "label": "Liste", "type": "entity", "domain": "todo"},
                _title("Einkaufsliste"), _rows(36), STYLE_FIELD]},
    {"type": "text", "label": "Text", "icon": "mdi:format-text", "w": 300, "h": 60,
     "fields": [{"key": "text", "label": "Text", "type": "text", "default": "Hallo!"},
                {"key": "size", "label": "Schriftgröße", "type": "number", "min": 10, "max": 160, "default": 32},
                {"key": "weight", "label": "Stärke", "type": "select", "default": "semibold",
                 "options": [{"value": "regular", "label": "Normal"}, {"value": "medium", "label": "Mittel"},
                             {"value": "semibold", "label": "Halbfett"}, {"value": "bold", "label": "Fett"},
                             {"value": "display", "label": "Groß & fett"}]},
                {"key": "align", "label": "Ausrichtung", "type": "select", "default": "left",
                 "options": [{"value": "left", "label": "Links"}, {"value": "center", "label": "Mitte"},
                             {"value": "right", "label": "Rechts"}]},
                {"key": "color", "label": "Farbe", "type": "select", "default": "fg", "options": COLOR_OPTIONS},
                STYLE_FIELD]},
    {"type": "divider", "label": "Linie", "icon": "mdi:minus", "w": 300, "h": 10,
     "fields": [{"key": "color", "label": "Farbe", "type": "select", "default": "fg", "options": COLOR_OPTIONS},
                {"key": "thickness", "label": "Stärke", "type": "number", "min": 1, "max": 12, "default": 2}]},
]
CATALOG_BY_TYPE = {c["type"]: c for c in CATALOG}

THEME_FIELDS = [
    {"key": "mode", "label": "Hintergrund", "type": "select", "default": "light",
     "options": [{"value": "light", "label": "Hell"}, {"value": "dark", "label": "Dunkel"}]},
    {"key": "accent", "label": "Akzentfarbe", "type": "select", "default": "red",
     "options": [{"value": "red", "label": "Rot"}, {"value": "blue", "label": "Blau"},
                 {"value": "green", "label": "Grün"}, {"value": "yellow", "label": "Gelb"},
                 {"value": "black", "label": "Schwarz"}, {"value": "white", "label": "Weiß"}]},
]


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def widget(type_: str, x: int, y: int, w: int | None = None, h: int | None = None, **props) -> dict[str, Any]:
    cat = CATALOG_BY_TYPE[type_]
    p = {f["key"]: f["default"] for f in cat["fields"] if "default" in f}
    p.update(props)
    return {"id": new_id(), "type": type_, "x": x, "y": y, "w": w or cat["w"], "h": h or cat["h"], "props": p}


def default_layout(weather: str | None = None, waste: list[str] | None = None,
                   calendars: list[str] | None = None, calendar_title: str | None = None,
                   calendar_days: int | None = None, values: list[str] | None = None,
                   values_title: str | None = None) -> dict[str, Any]:
    ws: list[dict[str, Any]] = [widget("date", 28, 22, 400, 92)]
    if weather:
        ws.append(widget("weather_now", 28, 138, 400, 150, entity=weather))
        ws.append(widget("weather_forecast", 28, 312, 400, 146, entity=weather, days=4))
    right = []
    if waste:
        right.append(("waste", {"entities": list(waste), "title": "Müllabfuhr", "style": "outline"}))
    if calendars:
        right.append(("calendar", {"entities": list(calendars), "title": calendar_title or "Termine",
                                   "days": int(calendar_days or 30), "style": "filled"}))
    if values:
        right.append(("entities", {"entities": list(values), "title": values_title or "Werte",
                                   "style": "outline"}))
    if right:
        gap = 12
        h_each = (480 - 32 - gap * (len(right) - 1)) // len(right)
        y = 16
        for t, props in right:
            ws.append(widget(t, 452, y, 332, h_each, **props))
            y += h_each + gap
    return {"version": 1, "theme": {"mode": "light", "accent": "red"}, "widgets": ws}


def _num(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def sanitize(layout: Any) -> dict[str, Any]:
    """Nimmt ein Layout aus dem Editor entgegen und bringt es in eine sichere Form."""
    if not isinstance(layout, dict):
        raise ValueError("Layout muss ein Objekt sein")
    theme_in = layout.get("theme") if isinstance(layout.get("theme"), dict) else {}
    theme = {
        "mode": "dark" if theme_in.get("mode") == "dark" else "light",
        "accent": theme_in.get("accent") if theme_in.get("accent") in
        ("red", "blue", "green", "yellow", "black", "white") else "red",
    }
    out = []
    for wd in (layout.get("widgets") or [])[:60]:
        if not isinstance(wd, dict) or wd.get("type") not in WIDGETS:
            continue
        w = _num(wd.get("w"), 4, W, 100)
        h = _num(wd.get("h"), 4, H, 50)
        x = _num(wd.get("x"), -w + 10, W - 10, 0)
        y = _num(wd.get("y"), -h + 10, H - 10, 0)
        props = wd.get("props") if isinstance(wd.get("props"), dict) else {}
        clean: dict[str, Any] = {}
        for f in CATALOG_BY_TYPE[wd["type"]]["fields"]:
            k = f["key"]
            if k not in props:
                if "default" in f:
                    clean[k] = copy.deepcopy(f["default"])
                continue
            v = props[k]
            t = f["type"]
            if t == "number":
                clean[k] = _num(v, int(f.get("min", -9999)), int(f.get("max", 9999)), f.get("default", 0))
            elif t == "bool":
                clean[k] = bool(v)
            elif t == "select":
                allowed = [o["value"] for o in f["options"]]
                clean[k] = v if v in allowed else f.get("default", allowed[0])
            elif t == "entity" and f.get("multiple"):
                clean[k] = [str(e) for e in (v if isinstance(v, list) else [v]) if e][:30]
            else:
                clean[k] = str(v)[:500] if v is not None else ""
        wid = str(wd.get("id") or new_id())[:32]
        out.append({"id": wid, "type": wd["type"], "x": x, "y": y, "w": w, "h": h, "props": clean})
    return {"version": 1, "theme": theme, "widgets": out}
