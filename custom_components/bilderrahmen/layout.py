"""Widget-Katalog, Standard-Layout und Prüfung von Layouts aus dem Editor."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from .render import H, W, WIDGETS

def _style(default: str) -> dict[str, Any]:
    return {
        "key": "style", "label": "Hintergrund", "type": "select", "default": default,
        "options": [
            {"value": "card", "label": "Karte (weiß mit Linie)"},
            {"value": "none", "label": "Ohne"},
            {"value": "sky", "label": "Himmelblau"},
            {"value": "mint", "label": "Mint"},
            {"value": "sun", "label": "Sonnengelb"},
            {"value": "peach", "label": "Pfirsich"},
            {"value": "rose", "label": "Rosé"},
            {"value": "lilac", "label": "Flieder"},
            {"value": "sand", "label": "Sand"},
            {"value": "dark", "label": "Dunkel"},
            {"value": "accent", "label": "Akzentfarbe (kräftig)"},
        ],
    }


STYLE_FIELD = _style("card")
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


WEATHER_ENTITY = {"key": "entity", "label": "Wetter-Entität", "type": "entity", "domain": "weather"}
DETAIL_OPTIONS = [
    {"value": "sunrise", "label": "Sonnenaufgang"}, {"value": "sunset", "label": "Sonnenuntergang"},
    {"value": "wind", "label": "Wind"}, {"value": "humidity", "label": "Luftfeuchte"},
    {"value": "pressure", "label": "Luftdruck"}, {"value": "clouds", "label": "Bewölkung"},
    {"value": "uv", "label": "UV-Index"}, {"value": "visibility", "label": "Sichtweite"},
    {"value": "dew_point", "label": "Taupunkt"}, {"value": "feels", "label": "Gefühlt"},
    {"value": "gusts", "label": "Böen"},
    {"value": "indoor_temp", "label": "Innen-Temperatur"}, {"value": "indoor_humidity", "label": "Innen-Luftfeuchte"},
    {"value": "air_quality", "label": "Luftqualität"},
]

CATALOG: list[dict[str, Any]] = [
    {"type": "date", "label": "Datum / Titel", "icon": "mdi:calendar-today", "w": 420, "h": 80,
     "fields": [{"key": "title", "label": "Titel (leer = großes Datum)", "type": "text", "default": ""},
                {"key": "align", "label": "Ausrichtung", "type": "select", "default": "left",
                 "options": [{"value": "left", "label": "Links"}, {"value": "center", "label": "Mitte"},
                             {"value": "right", "label": "Rechts"}]},
                {"key": "show_year", "label": "Jahr anzeigen", "type": "bool", "default": False}, _style("none")]},
    {"type": "weather_now", "label": "Wetter jetzt", "icon": "mdi:weather-partly-cloudy", "w": 360, "h": 160,
     "fields": [WEATHER_ENTITY,
                {"key": "show_condition", "label": "Wetterlage als Text", "type": "bool", "default": False},
                _title(), _style("none")]},
    {"type": "weather_details", "label": "Wetterdetails", "icon": "mdi:weather-windy", "w": 360, "h": 140,
     "fields": [WEATHER_ENTITY,
                {"key": "items", "label": "Angaben", "type": "checks", "options": DETAIL_OPTIONS,
                 "default": ["sunrise", "sunset", "wind", "humidity", "pressure", "clouds"]},
                {"key": "columns", "label": "Spalten", "type": "number", "min": 1, "max": 4, "default": 2},
                {"key": "indoor_temp_entity", "label": "Innen-Temperatur (Sensor)", "type": "entity", "domain": "sensor"},
                {"key": "indoor_humidity_entity", "label": "Innen-Luftfeuchte (Sensor)", "type": "entity", "domain": "sensor"},
                {"key": "air_quality_entity", "label": "Luftqualität (Sensor)", "type": "entity", "domain": "sensor"},
                _title(), _style("none")]},
    {"type": "weather_forecast", "label": "Wettervorhersage", "icon": "mdi:calendar-week", "w": 412, "h": 190,
     "fields": [WEATHER_ENTITY,
                {"key": "days", "label": "Tage", "type": "number", "min": 1, "max": 7, "default": 4},
                {"key": "boxes", "label": "Tageskästen", "type": "select", "default": "outline",
                 "options": [{"value": "outline", "label": "Umrandet"}, {"value": "card", "label": "Weiß gefüllt"},
                             {"value": "none", "label": "Ohne"}]},
                {"key": "gap", "label": "Abstand", "type": "number", "min": 0, "max": 40, "default": 12, "unit": "px"},
                _title(), _style("none")]},
    {"type": "weather_chart", "label": "Temperatur\u00adverlauf", "icon": "mdi:chart-bell-curve-cumulative", "w": 756, "h": 96,
     "fields": [WEATHER_ENTITY,
                {"key": "hours", "label": "Stunden", "type": "number", "min": 6, "max": 48, "default": 24},
                {"key": "label_every", "label": "Uhrzeit alle … Stunden", "type": "number", "min": 1, "max": 12, "default": 2},
                _title(), _style("none")]},
    {"type": "status", "label": "Status (WLAN, Akku)", "icon": "mdi:wifi", "w": 230, "h": 20,
     "fields": [{"key": "show_time", "label": "Aktualisierungszeit", "type": "bool", "default": True},
                {"key": "show_wifi", "label": "WLAN-Signal", "type": "bool", "default": True},
                {"key": "show_battery", "label": "Akku", "type": "bool", "default": True},
                {"key": "align", "label": "Ausrichtung", "type": "select", "default": "right",
                 "options": [{"value": "left", "label": "Links"}, {"value": "center", "label": "Mitte"},
                             {"value": "right", "label": "Rechts"}]}]},
    {"type": "waste", "label": "Müllabfuhr", "icon": "mdi:trash-can-outline", "w": 320, "h": 214,
     "fields": [{"key": "entities", "label": "Müll-Sensoren", "type": "entity", "domain": "sensor", "multiple": True},
                _title("Müllabfuhr"), _rows(36), STYLE_FIELD]},
    {"type": "calendar", "label": "Kalender", "icon": "mdi:calendar-blank-outline", "w": 320, "h": 220,
     "fields": [{"key": "entities", "label": "Kalender", "type": "entity", "domain": "calendar", "multiple": True},
                {"key": "days", "label": "Tage im Voraus", "type": "number", "min": 1, "max": 365, "default": 30},
                _title("Termine"), _rows(50), STYLE_FIELD]},
    {"type": "entity", "label": "Einzelwert", "icon": "mdi:numeric", "w": 180, "h": 140,
     "fields": [{"key": "entity", "label": "Entität", "type": "entity"},
                {"key": "title", "label": "Beschriftung (leer = Name)", "type": "text", "default": ""},
                {"key": "icon", "label": "Icon (z. B. mdi:thermometer)", "type": "text", "default": ""},
                STYLE_FIELD]},
    {"type": "entities", "label": "Werteliste", "icon": "mdi:view-list-outline", "w": 320, "h": 200,
     "fields": [{"key": "entities", "label": "Entitäten", "type": "entity", "multiple": True},
                _title("Zuhause"), _rows(38), STYLE_FIELD]},
    {"type": "todo", "label": "To-do-Liste", "icon": "mdi:format-list-checks", "w": 320, "h": 200,
     "fields": [{"key": "entity", "label": "Liste", "type": "entity", "domain": "todo"},
                _title("Einkaufsliste"), _rows(36), STYLE_FIELD]},
    {"type": "text", "label": "Text", "icon": "mdi:format-text", "w": 300, "h": 60,
     "fields": [{"key": "text", "label": "Text", "type": "text", "default": "Hallo!"},
                {"key": "size", "label": "Schriftgröße", "type": "number", "min": 10, "max": 200, "default": 32},
                {"key": "weight", "label": "Stärke", "type": "select", "default": "medium",
                 "options": [{"value": "light", "label": "Leicht"}, {"value": "regular", "label": "Normal"},
                             {"value": "medium", "label": "Mittel"}, {"value": "semibold", "label": "Halbfett"},
                             {"value": "bold", "label": "Fett"}]},
                {"key": "align", "label": "Ausrichtung", "type": "select", "default": "left",
                 "options": [{"value": "left", "label": "Links"}, {"value": "center", "label": "Mitte"},
                             {"value": "right", "label": "Rechts"}]},
                {"key": "color", "label": "Farbe", "type": "select", "default": "fg", "options": COLOR_OPTIONS},
                _style("none")]},
    {"type": "divider", "label": "Linie", "icon": "mdi:minus", "w": 300, "h": 10,
     "fields": [{"key": "color", "label": "Farbe", "type": "select", "default": "fg", "options": COLOR_OPTIONS},
                {"key": "thickness", "label": "Stärke", "type": "number", "min": 1, "max": 12, "default": 1}]},
]
CATALOG_BY_TYPE = {c["type"]: c for c in CATALOG}

THEME_FIELDS = [
    {"key": "mode", "label": "Hintergrund", "type": "select", "default": "light",
     "options": [{"value": "light", "label": "Papier"}, {"value": "white", "label": "Weiß"},
                 {"value": "dark", "label": "Dunkel"}]},
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
    right = []
    if waste:
        right.append(("waste", {"entities": list(waste), "title": "Müllabfuhr"}))
    if calendars:
        right.append(("calendar", {"entities": list(calendars), "title": calendar_title or "Termine",
                                   "days": int(calendar_days or 30)}))
    if values:
        right.append(("entities", {"entities": list(values), "title": values_title or "Werte"}))
    ws: list[dict[str, Any]] = []
    if right:
        ws.append(widget("date", 24, 14, 420, 80))
        if weather:
            ws.append(widget("weather_now", 14, 104, 420, 150, entity=weather))
            ws.append(widget("weather_forecast", 24, 270, 412, 190, entity=weather, days=4))
        gap = 14
        h_each = (480 - 30 - gap * (len(right) - 1)) // len(right)
        y = 16
        for t, props in right:
            ws.append(widget(t, 462, y, 320, h_each, **props))
            y += h_each + gap
    else:
        ws.append(widget("date", 200, 10, 400, 62, title="Wetter", align="center"))
        if weather:
            ws.append(widget("weather_now", 22, 80, 370, 150, entity=weather))
            ws.append(widget("weather_details", 420, 84, 360, 140, entity=weather))
            ws.append(widget("weather_chart", 22, 240, 756, 96, entity=weather))
            ws.append(widget("weather_forecast", 22, 346, 756, 122, entity=weather, days=7))
    return {"version": 2, "theme": {"mode": "light", "accent": "red"}, "widgets": ws}


def station_layout(weather: str | None, title: str = "", indoor_temp: str | None = None,
                   indoor_humidity: str | None = None, air_quality: str | None = None,
                   available: list[str] | None = None) -> dict[str, Any]:
    """Nachbau des bekannten esp32-weather-epd-Designs (800 × 480)."""
    avail = available or ["sunrise", "sunset", "wind", "humidity", "pressure", "uv", "visibility", "clouds",
                          "gusts", "dew_point"]
    items = [k for k in ("sunrise", "sunset", "wind", "humidity", "pressure", "uv") if k in avail]
    extra = []
    if indoor_temp:
        extra.append("indoor_temp")
    if indoor_humidity:
        extra.append("indoor_humidity")
    if air_quality:
        extra.append("air_quality")
    for fill in ("visibility", "clouds", "gusts", "dew_point", "feels"):
        if len(items) + len(extra) >= 8:
            break
        if fill in avail and fill not in items:
            items.append(fill)
    items = items[: max(0, 8 - len(extra))]
    det = {"entity": weather, "items": items + extra, "columns": 2}
    if indoor_temp:
        det["indoor_temp_entity"] = indoor_temp
    if indoor_humidity:
        det["indoor_humidity_entity"] = indoor_humidity
    if air_quality:
        det["air_quality_entity"] = air_quality
    return {"version": 2, "theme": {"mode": "light", "accent": "red"}, "widgets": [
        widget("date", 150, 10, 500, 62, title=title or "Wetter", align="center"),
        widget("status", 572, 6, 220, 20),
        widget("weather_now", 22, 92, 368, 160, entity=weather),
        widget("weather_details", 404, 82, 386, 176, **det),
        widget("weather_chart", 8, 268, 784, 74, entity=weather, hours=24, label_every=2),
        widget("weather_forecast", 10, 352, 780, 116, entity=weather, days=7, gap=12),
    ]}


TEMPLATES = {"station": "Wetterstation (esp32-weather-epd)", "default": "Standard"}


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
        "mode": theme_in.get("mode") if theme_in.get("mode") in ("light", "white", "dark") else "light",
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
            elif t == "checks":
                allowed = [o["value"] for o in f["options"]]
                clean[k] = [i for i in (v if isinstance(v, list) else []) if i in allowed]
            elif t == "entity" and f.get("multiple"):
                clean[k] = [str(e) for e in (v if isinstance(v, list) else [v]) if e][:30]
            else:
                clean[k] = str(v)[:500] if v is not None else ""
        wid = str(wd.get("id") or new_id())[:32]
        out.append({"id": wid, "type": wd["type"], "x": x, "y": y, "w": w, "h": h, "props": clean})
    return {"version": 2, "theme": theme, "widgets": out}
