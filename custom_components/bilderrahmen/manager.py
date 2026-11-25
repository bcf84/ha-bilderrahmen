"""Sammelt Daten aus Home Assistant, zeichnet das Bild und schickt es an den Rahmen."""

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
from homeassistant.core import CALLBACK_TYPE, CoreState, Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_change,
    async_track_time_interval,
)
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
    DEFAULT_CALENDAR_DAYS,
    DEFAULT_CALENDAR_TITLE,
    DEFAULT_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_ROTATION,
    DEFAULT_VALUES_TITLE,
)
from .render import WD_SHORT, render

_LOGGER = logging.getLogger(__name__)

STATE_DE = {
    "on": "An", "off": "Aus", "open": "Offen", "closed": "Zu",
    "opening": "Öffnet", "closing": "Schließt", "locked": "Zu", "unlocked": "Offen",
    "home": "Zuhause", "not_home": "Unterwegs", "idle": "Bereit", "playing": "Spielt",
    "paused": "Pause", "docked": "In Station", "cleaning": "Reinigt",
    "heat": "Heizen", "cool": "Kühlen", "auto": "Auto", "armed_away": "Scharf",
    "armed_home": "Scharf (zuhause)", "disarmed": "Unscharf", "triggered": "Alarm!",
}


def _waste_color(name: str) -> str:
    n = name.lower()
    if "rest" in n:
        return "black"
    if "bio" in n:
        return "green"
    if "gelb" in n or "wertstoff" in n or "plastik" in n or "verpackung" in n:
        return "yellow"
    if "papier" in n or "blau" in n or "pappe" in n:
        return "blue"
    if "glas" in n:
        return "green"
    return "red"


def _clean_birthday(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[’']s\s+birthday$", "", s, flags=re.I)
    s = re.sub(r"\s*(birthday|geburtstag)$", "", s, flags=re.I)
    return s.strip()


def _day_label(d: date, today: date, weekday: bool = True) -> str:
    n = (d - today).days
    if n == 0:
        return "Heute"
    if n == 1:
        return "Morgen"
    return f"{WD_SHORT[d.weekday()]} {d:%d.%m.}" if weekday else f"{d:%d.%m.}"


def _fmt_number(v: float) -> str:
    if v.is_integer() or abs(v) >= 100:
        s = f"{round(v):d}"
    else:
        s = f"{v:.1f}"
    return s.replace(".", ",")


class FrameManager:
    """Hält den Zustand eines Bilderrahmens."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.image: bytes | None = None
        self.image_updated: datetime | None = None
        self.last_display: datetime | None = None
        self.status: str = "Startet"
        self._last_sent_hash: str | None = None
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []

    # ------------------------------------------------------------ Optionen
    def _opt(self, key: str, default: Any = None) -> Any:
        if key in self.entry.options:
            return self.entry.options[key]
        return self.entry.data.get(key, default)

    @property
    def base_url(self) -> str:
        return f"http://{self._opt(CONF_HOST)}:{int(self._opt(CONF_PORT, DEFAULT_PORT))}"

    # ------------------------------------------------------------ Lebenszyklus
    async def async_start(self) -> None:
        interval = timedelta(minutes=int(self._opt(CONF_INTERVAL, DEFAULT_INTERVAL)))
        self._unsubs.append(
            async_track_time_interval(self.hass, self._scheduled, interval)
        )
        # kurz nach Mitternacht für das neue Datum
        self._unsubs.append(
            async_track_time_change(self.hass, self._scheduled, hour=0, minute=0, second=30)
        )

        if self.hass.state is CoreState.running:
            self._unsubs.append(async_call_later(self.hass, 2, self._scheduled))
        else:
            @callback
            def _started(_event: Event) -> None:
                self._unsubs.append(async_call_later(self.hass, 30, self._scheduled))

            self._unsubs.append(
                self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _started)
            )

    def async_stop(self) -> None:
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:  # noqa: BLE001 – bereits abgelaufene Timer
                pass
        self._unsubs.clear()

    @callback
    def _scheduled(self, _now: Any = None) -> None:
        self.hass.async_create_background_task(
            self.async_refresh(force=False), "bilderrahmen_refresh"
        )

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
                model = await self._build_model()
                png = await self.hass.async_add_executor_job(render, model)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Bild konnte nicht erstellt werden")
                self.status = f"Fehler beim Zeichnen: {err}"
                self._notify()
                return

            self.image = png
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

    # ------------------------------------------------------------ Daten
    async def _build_model(self) -> dict[str, Any]:
        now = dt_util.now()
        today = now.date()
        errors: list[str] = []

        weather = None
        if self._opt(CONF_WEATHER):
            try:
                weather = await self._weather(self._opt(CONF_WEATHER), today)
            except Exception as err:  # noqa: BLE001
                errors.append(f"Wetter: {err}")

        sections: list[dict[str, Any]] = []

        if self._opt(CONF_WASTE):
            sections.append({"title": "Müllabfuhr", "rows": self._waste(today),
                             "empty": "keine Termine"})

        if self._opt(CONF_CALENDARS):
            days = int(self._opt(CONF_CALENDAR_DAYS, DEFAULT_CALENDAR_DAYS))
            try:
                rows = await self._calendar(now, today, days)
            except Exception as err:  # noqa: BLE001
                rows = []
                errors.append(f"Kalender: {err}")
            sections.append({
                "title": self._opt(CONF_CALENDAR_TITLE) or DEFAULT_CALENDAR_TITLE,
                "rows": rows,
                "empty": f"nichts in den nächsten {days} Tagen",
            })

        if self._opt(CONF_VALUES):
            sections.append({
                "title": self._opt(CONF_VALUES_TITLE) or DEFAULT_VALUES_TITLE,
                "rows": self._values(),
                "empty": "–",
            })

        return {
            "today": today,
            "weather": weather,
            "sections": sections,
            "rotation": int(self._opt(CONF_ROTATION, DEFAULT_ROTATION)),
            "error": ("Fehler: " + errors[0]) if errors else None,
        }

    async def _weather(self, entity_id: str, today: date) -> dict[str, Any] | None:
        st = self.hass.states.get(entity_id)
        if st is None:
            raise ValueError(f"{entity_id} nicht gefunden")
        out: dict[str, Any] = {}
        if st.state not in ("unavailable", "unknown"):
            out["now"] = {"cond": st.state, "temp": st.attributes.get("temperature")}
        try:
            resp = await self.hass.services.async_call(
                "weather", "get_forecasts",
                {"entity_id": entity_id, "type": "daily"},
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
            out["forecast"] = [x for x in days if x["date"] > today][:3]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Keine Tagesvorhersage für %s: %s", entity_id, err)
        return out or None

    def _waste(self, today: date) -> list[dict[str, Any]]:
        items = []
        for eid in self._opt(CONF_WASTE) or []:
            st = self.hass.states.get(eid)
            if st is None:
                continue
            name = re.sub(r"^waste collection schedule\s*", "", st.name or eid, flags=re.I)
            d = self._waste_date(st, today)
            if d is None:
                continue
            items.append((d, name))
        items.sort()
        return [{
            "marker": _waste_color(name),
            "text": name,
            "right": _day_label(d, today),
            "hl": (d - today).days <= 1,
        } for d, name in items]

    @staticmethod
    def _waste_date(st, today: date) -> date | None:
        dates = []
        for k in st.attributes:
            if isinstance(k, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", k):
                dates.append(date.fromisoformat(k))
        for key in ("next_date", "next_collection", "date"):
            v = st.attributes.get(key)
            if v:
                parsed = dt_util.parse_date(str(v)[:10])
                if parsed:
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
        m = re.search(r"in (\d+) (day|tag)", s)
        if m:
            return today + timedelta(days=int(m.group(1)))
        if "tomorrow" in s or "morgen" in s:
            return today + timedelta(days=1)
        if "today" in s or "heute" in s:
            return today
        return None

    async def _calendar(self, now: datetime, today: date, days: int) -> list[dict[str, Any]]:
        cals = list(self._opt(CONF_CALENDARS) or [])
        resp = await self.hass.services.async_call(
            "calendar", "get_events",
            {"entity_id": cals,
             "start_date_time": now.isoformat(),
             "end_date_time": (now + timedelta(days=days)).isoformat()},
            blocking=True, return_response=True,
        )
        events, seen = [], set()
        for cal in cals:
            for ev in (resp or {}).get(cal, {}).get("events", []):
                start = str(ev.get("start", ""))
                timed = "T" in start
                if timed:
                    sdt = dt_util.parse_datetime(start)
                    if sdt is None:
                        continue
                    sdt = dt_util.as_local(sdt)
                    d = sdt.date()
                    if d < today:  # mehrtägig, schon begonnen
                        d = today
                    sort_key = sdt.replace(tzinfo=None)
                else:
                    d = dt_util.parse_date(start[:10])
                    if d is None:
                        continue
                    if d < today:
                        d = today
                    sort_key = datetime.combine(d, datetime.min.time())
                name = _clean_birthday(ev.get("summary", ""))
                key = (d, name.lower())
                if not name or key in seen:
                    continue
                seen.add(key)
                text = f"{sdt:%H:%M} {name}" if timed and (sdt.date() >= today) else name
                events.append((sort_key, d, text))
        events.sort(key=lambda e: e[0])
        return [{
            "label": _day_label(d, today, weekday=False),
            "text": text,
            "hl": (d - today).days <= 1,
        } for _, d, text in events]

    def _values(self) -> list[dict[str, Any]]:
        rows = []
        for eid in self._opt(CONF_VALUES) or []:
            st = self.hass.states.get(eid)
            if st is None:
                continue
            rows.append({"text": st.name or eid, "right": self._fmt_state(st)})
        return rows

    @staticmethod
    def _fmt_state(st) -> str:
        s = st.state
        if s in ("unavailable", "unknown", ""):
            return "–"
        unit = st.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        try:
            val = _fmt_number(float(s))
            return f"{val} {unit}" if unit else val
        except ValueError:
            pass
        if st.domain == "climate":
            t = st.attributes.get("current_temperature")
            if t is not None:
                return f"{_fmt_number(float(t))} °C"
        return STATE_DE.get(s, s)
