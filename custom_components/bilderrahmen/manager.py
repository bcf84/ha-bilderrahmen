"""Sammelt Daten aus Home Assistant, zeichnet das Layout und schickt es an den Rahmen."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, CoreState, Event, HomeAssistant, State, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CALENDAR_DAYS,
    CONF_CALENDAR_TITLE,
    CONF_CALENDARS,
    CONF_HOST,
    CONF_INTERVAL,
    CONF_PORT,
    CONF_ROTATION,
    CONF_VALUES,
    CONF_VALUES_TITLE,
    CONF_WASTE,
    CONF_WEATHER,
    DEFAULT_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_ROTATION,
    DOMAIN,
)
from .layout import default_layout, sanitize
from .render import WD_SHORT, render_image, to_png

_LOGGER = logging.getLogger(__name__)

STATE_DE = {
    "on": "An", "off": "Aus", "open": "Offen", "closed": "Zu",
    "opening": "Öffnet", "closing": "Schließt", "locked": "Zu", "unlocked": "Offen",
    "home": "Zuhause", "not_home": "Weg", "idle": "Bereit", "playing": "Spielt",
    "paused": "Pause", "docked": "Station", "cleaning": "Reinigt", "returning": "Kehrt zurück",
    "heat": "Heizen", "cool": "Kühlen", "auto": "Auto", "armed_away": "Scharf",
    "armed_home": "Scharf", "armed_night": "Nacht", "disarmed": "Unscharf", "triggered": "Alarm!",
    "standby": "Standby", "charging": "Lädt", "discharging": "Entlädt",
}

DOMAIN_ICON = {
    "light": "mdi:lightbulb-outline", "switch": "mdi:toggle-switch-outline", "lock": "mdi:lock-outline",
    "cover": "mdi:window-shutter", "climate": "mdi:thermostat", "person": "mdi:account-outline",
    "device_tracker": "mdi:map-marker-outline", "binary_sensor": "mdi:checkbox-blank-circle-outline",
    "media_player": "mdi:speaker", "vacuum": "mdi:robot-vacuum", "fan": "mdi:fan",
    "alarm_control_panel": "mdi:shield-home-outline", "weather": "mdi:weather-partly-cloudy",
    "input_boolean": "mdi:toggle-switch-outline", "input_number": "mdi:ray-vertex",
    "todo": "mdi:format-list-checks", "calendar": "mdi:calendar", "sun": "mdi:white-balance-sunny",
    "counter": "mdi:counter", "timer": "mdi:timer-outline",
}
DEVICE_CLASS_ICON = {
    "temperature": "mdi:thermometer", "humidity": "mdi:water-percent", "battery": "mdi:battery-medium",
    "power": "mdi:flash-outline", "energy": "mdi:lightning-bolt-outline", "illuminance": "mdi:brightness-6",
    "pressure": "mdi:gauge", "co2": "mdi:molecule-co2", "carbon_dioxide": "mdi:molecule-co2",
    "pm25": "mdi:air-filter", "monetary": "mdi:cash", "door": "mdi:door", "window": "mdi:window-closed-variant",
    "motion": "mdi:motion-sensor", "occupancy": "mdi:home-account", "moisture": "mdi:water-alert",
    "smoke": "mdi:smoke-detector", "voltage": "mdi:sine-wave", "current": "mdi:current-ac",
    "timestamp": "mdi:clock-outline", "duration": "mdi:timer-outline", "precipitation": "mdi:weather-rainy",
    "wind_speed": "mdi:weather-windy", "gas": "mdi:meter-gas", "water": "mdi:water",
}


def _waste_color(name: str) -> str:
    n = name.lower()
    if "rest" in n:
        return "black"
    if "bio" in n:
        return "green"
    if any(k in n for k in ("gelb", "wertstoff", "plastik", "verpackung")):
        return "yellow"
    if any(k in n for k in ("papier", "blau", "pappe")):
        return "blue"
    if "glas" in n:
        return "green"
    return "red"


def _clean_name(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[’']s\s+birthday$", "", s, flags=re.I)
    s = re.sub(r"\s*(birthday|geburtstag)$", "", s, flags=re.I)
    return s.strip()


def _when(d: date, today: date) -> str:
    n = (d - today).days
    if n == 0:
        return "Heute"
    if n == 1:
        return "Morgen"
    return f"{WD_SHORT[d.weekday()]} {d:%d.%m.}"


def _fmt_number(v: float) -> str:
    s = f"{round(v):d}" if v.is_integer() or abs(v) >= 100 else f"{v:.1f}"
    return s.replace(".", ",")


class FrameManager:
    """Zustand und Ablauf eines Bilderrahmens."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.layout: dict[str, Any] = {}
        self.image: bytes | None = None  # unrotiert, für Vorschau
        self.image_updated: datetime | None = None
        self.last_display: datetime | None = None
        self.status: str = "Startet"
        self._last_sent_hash: str | None = None
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._store: Store = Store(hass, 1, f"{DOMAIN}.layout.{entry.entry_id}")

    # ------------------------------------------------------------ Optionen
    def _opt(self, key: str, default: Any = None) -> Any:
        if key in self.entry.options:
            return self.entry.options[key]
        return self.entry.data.get(key, default)

    @property
    def base_url(self) -> str:
        return f"http://{self._opt(CONF_HOST)}:{int(self._opt(CONF_PORT, DEFAULT_PORT))}"

    @property
    def rotation(self) -> int:
        return int(self._opt(CONF_ROTATION, DEFAULT_ROTATION))

    # ------------------------------------------------------------ Layout
    async def async_load_layout(self) -> None:
        stored = await self._store.async_load()
        if stored:
            try:
                self.layout = sanitize(stored)
                return
            except ValueError:
                _LOGGER.warning("Gespeichertes Layout ungültig, nutze Standard")
        weather = self._opt(CONF_WEATHER)
        if not weather and CONF_WEATHER not in self.entry.options:
            weather = next(iter(self.hass.states.async_entity_ids("weather")), None)
        self.layout = default_layout(
            weather=weather,
            waste=self._opt(CONF_WASTE) or [],
            calendars=self._opt(CONF_CALENDARS) or [],
            calendar_title=self._opt(CONF_CALENDAR_TITLE),
            calendar_days=self._opt(CONF_CALENDAR_DAYS),
            values=self._opt(CONF_VALUES) or [],
            values_title=self._opt(CONF_VALUES_TITLE),
        )
        await self._store.async_save(self.layout)

    async def async_save_layout(self, layout: dict[str, Any]) -> dict[str, Any]:
        self.layout = sanitize(layout)
        await self._store.async_save(self.layout)
        self.hass.async_create_background_task(self.async_refresh(force=True), "bilderrahmen_save")
        return self.layout

    async def async_preview(self, layout: dict[str, Any]) -> bytes:
        lay = sanitize(layout)
        data, errors = await self._collect(lay)
        img = await self.hass.async_add_executor_job(
            render_image, lay, data, dt_util.now().date(), errors[0] if errors else None
        )
        return await self.hass.async_add_executor_job(to_png, img, 0)

    # ------------------------------------------------------------ Lebenszyklus
    async def async_start(self) -> None:
        interval = timedelta(minutes=int(self._opt(CONF_INTERVAL, DEFAULT_INTERVAL)))
        self._unsubs.append(async_track_time_interval(self.hass, self._scheduled, interval))
        self._unsubs.append(
            async_track_time_change(self.hass, self._scheduled, hour=0, minute=0, second=30)
        )
        if self.hass.state is CoreState.running:
            self._unsubs.append(async_call_later(self.hass, 2, self._scheduled))
        else:
            @callback
            def _started(_event: Event) -> None:
                self._unsubs.append(async_call_later(self.hass, 30, self._scheduled))

            self._unsubs.append(self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _started))

    def async_stop(self) -> None:
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:  # noqa: BLE001 – Timer schon abgelaufen
                pass
        self._unsubs.clear()

    @callback
    def _scheduled(self, _now: Any = None) -> None:
        self.hass.async_create_background_task(self.async_refresh(force=False), "bilderrahmen_refresh")

    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    # ------------------------------------------------------------ Ablauf
    async def async_refresh(self, force: bool = False) -> None:
        async with self._lock:
            try:
                data, errors = await self._collect(self.layout)
                img = await self.hass.async_add_executor_job(
                    render_image, self.layout, data, dt_util.now().date(), errors[0] if errors else None
                )
                preview = await self.hass.async_add_executor_job(to_png, img, 0)
                png = preview if not self.rotation else await self.hass.async_add_executor_job(
                    to_png, img, self.rotation
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Bild konnte nicht erstellt werden")
                self.status = f"Fehler beim Zeichnen: {err}"
                self._notify()
                return

            self.image = preview
            self.image_updated = dt_util.utcnow()
            digest = hashlib.sha1(png).hexdigest()
            if not force and digest == self._last_sent_hash:
                self.status = "Unverändert"
                self._notify()
                return
            try:
                result = await self._send(png, force)
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.warning("Rahmen %s nicht erreichbar: %s", self.base_url, err)
                self.status = "Rahmen nicht erreichbar"
                self._notify()
                return
            self._last_sent_hash = digest
            if result == "unchanged":
                self.status = "Unverändert"
            else:
                self.status = "Aktualisiert"
                self.last_display = dt_util.utcnow()
            self._notify()

    async def _send(self, png: bytes, force: bool) -> str:
        session = async_get_clientsession(self.hass)
        async with asyncio.timeout(20):
            resp = await session.post(
                f"{self.base_url}/display",
                params={"force": "1" if force else "0"},
                data=png,
                headers={"Content-Type": "image/png"},
            )
            resp.raise_for_status()
            try:
                data = await resp.json(content_type=None)
            except ValueError:
                data = {}
        return str(data.get("result", "queued"))

    # ------------------------------------------------------------ Daten je Widget
    async def _collect(self, layout: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        now = dt_util.now()
        today = now.date()
        data: dict[str, Any] = {}
        errors: list[str] = []
        weather_cache: dict[str, Any] = {}

        for wd in layout.get("widgets", []):
            t, p, wid = wd["type"], wd.get("props", {}), wd["id"]
            try:
                if t in ("weather_now", "weather_forecast"):
                    ent = p.get("entity") or next(iter(self.hass.states.async_entity_ids("weather")), None)
                    if ent:
                        if ent not in weather_cache:
                            weather_cache[ent] = await self._weather(ent, today)
                        data[wid] = weather_cache[ent]
                elif t == "waste":
                    data[wid] = {"rows": self._waste(p.get("entities") or [], today)}
                elif t == "calendar":
                    if p.get("entities"):
                        data[wid] = {"rows": await self._calendar(p["entities"], now, today,
                                                                  int(p.get("days", 30)))}
                elif t == "entity":
                    st = self.hass.states.get(p.get("entity") or "")
                    if st:
                        data[wid] = self._entity_row(st)
                elif t == "entities":
                    rows = [self._entity_row(st) for e in (p.get("entities") or [])
                            if (st := self.hass.states.get(e))]
                    data[wid] = {"rows": rows}
                elif t == "todo":
                    if p.get("entity"):
                        data[wid] = {"rows": await self._todo(p["entity"])}
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Daten für %s (%s) fehlgeschlagen: %s", wid, t, err)
                errors.append(f"{t}: {err}")
        return data, errors

    async def _weather(self, entity_id: str, today: date) -> dict[str, Any]:
        st = self.hass.states.get(entity_id)
        if st is None:
            raise ValueError(f"{entity_id} nicht gefunden")
        out: dict[str, Any] = {}
        if st.state not in ("unavailable", "unknown"):
            out["now"] = {"cond": st.state, "temp": st.attributes.get("temperature")}
        try:
            resp = await self.hass.services.async_call(
                "weather", "get_forecasts", {"entity_id": entity_id, "type": "daily"},
                blocking=True, return_response=True,
            )
            days = []
            for f in (resp or {}).get(entity_id, {}).get("forecast", []):
                dt_ = dt_util.parse_datetime(str(f.get("datetime")))
                if dt_ is None:
                    continue
                d = dt_util.as_local(dt_).date() if dt_.tzinfo else dt_.date()
                days.append({"date": d, "cond": f.get("condition"),
                             "hi": f.get("temperature"), "lo": f.get("templow")})
            out["today"] = next((x for x in days if x["date"] == today), None)
            out["forecast"] = [x for x in days if x["date"] > today]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Keine Tagesvorhersage für %s: %s", entity_id, err)
        return out

    def _waste(self, entities: list[str], today: date) -> list[dict[str, Any]]:
        items = []
        for eid in entities:
            st = self.hass.states.get(eid)
            if st is None:
                continue
            name = re.sub(r"^waste collection schedule\s*", "", st.name or eid, flags=re.I)
            d = self._waste_date(st, today)
            if d is not None:
                items.append((d, name))
        items.sort()
        return [{"name": n, "color": _waste_color(n), "when": _when(d, today),
                 "soon": (d - today).days <= 1} for d, n in items]

    @staticmethod
    def _waste_date(st: State, today: date) -> date | None:
        dates = [date.fromisoformat(k) for k in st.attributes
                 if isinstance(k, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", k)]
        for key in ("next_date", "next_collection", "date"):
            v = st.attributes.get(key)
            if v and (parsed := dt_util.parse_date(str(v)[:10])):
                dates.append(parsed)
        dates = [x for x in dates if x >= today]
        if dates:
            return min(dates)
        s = str(st.state).strip().lower()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", s):
            parsed = dt_util.parse_date(s[:10])
            return parsed if parsed and parsed >= today else None
        if re.fullmatch(r"-?\d+", s):
            return today + timedelta(days=int(s))
        if m := re.search(r"in (\d+) (day|tag)", s):
            return today + timedelta(days=int(m.group(1)))
        if "tomorrow" in s or "morgen" in s:
            return today + timedelta(days=1)
        if "today" in s or "heute" in s:
            return today
        return None

    async def _calendar(self, cals: list[str], now: datetime, today: date, days: int) -> list[dict[str, Any]]:
        resp = await self.hass.services.async_call(
            "calendar", "get_events",
            {"entity_id": list(cals), "start_date_time": now.isoformat(),
             "end_date_time": (now + timedelta(days=days)).isoformat()},
            blocking=True, return_response=True,
        )
        events, seen = [], set()
        for cal in cals:
            for ev in (resp or {}).get(cal, {}).get("events", []):
                start = str(ev.get("start", ""))
                time_s = None
                if "T" in start:
                    sdt = dt_util.parse_datetime(start)
                    if sdt is None:
                        continue
                    sdt = dt_util.as_local(sdt)
                    d = max(sdt.date(), today)
                    if sdt.date() >= today:
                        time_s = f"{sdt:%H:%M}"
                    key_t = sdt.replace(tzinfo=None)
                else:
                    d0 = dt_util.parse_date(start[:10])
                    if d0 is None:
                        continue
                    d = max(d0, today)
                    key_t = datetime.combine(d, datetime.min.time())
                name = _clean_name(ev.get("summary", ""))
                key = (d, name.lower())
                if not name or key in seen:
                    continue
                seen.add(key)
                events.append((key_t, {"date": d, "text": name, "time": time_s}))
        events.sort(key=lambda e: e[0])
        return [e[1] for e in events]

    async def _todo(self, entity_id: str) -> list[dict[str, Any]]:
        resp = await self.hass.services.async_call(
            "todo", "get_items", {"entity_id": entity_id, "status": ["needs_action"]},
            blocking=True, return_response=True,
        )
        items = (resp or {}).get(entity_id, {}).get("items", [])
        return [{"text": i.get("summary", "")} for i in items]

    def _entity_row(self, st: State) -> dict[str, Any]:
        icon = st.attributes.get("icon") or DEVICE_CLASS_ICON.get(st.attributes.get("device_class", "")) \
            or DOMAIN_ICON.get(st.domain, "mdi:circle-medium")
        if st.domain == "lock":
            icon = "mdi:lock-outline" if st.state == "locked" else "mdi:lock-open-variant-outline"
        value, unit = self._fmt_state(st)
        return {"name": st.name or st.entity_id, "value": value, "unit": unit, "icon": icon}

    @staticmethod
    def _fmt_state(st: State) -> tuple[str, str]:
        s = st.state
        if s in ("unavailable", "unknown", ""):
            return "–", ""
        unit = st.attributes.get(ATTR_UNIT_OF_MEASUREMENT) or ""
        try:
            return _fmt_number(float(s)), unit
        except ValueError:
            pass
        if st.domain == "climate" and st.attributes.get("current_temperature") is not None:
            return _fmt_number(float(st.attributes["current_temperature"])), "°C"
        if st.domain == "weather" and st.attributes.get("temperature") is not None:
            return _fmt_number(float(st.attributes["temperature"])), "°C"
        return STATE_DE.get(s, s), ""
