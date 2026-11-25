"""Einrichtung und Einstellungen per Oberfläche."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

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
    DEFAULT_HOST,
    DEFAULT_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_ROTATION,
    DEFAULT_VALUES_TITLE,
    DOMAIN,
)

LIST_KEYS = (CONF_WASTE, CONF_CALENDARS, CONF_VALUES)


async def _can_connect(hass, host: str, port: int) -> bool:
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(8):
            resp = await session.get(f"http://{host}:{port}/status")
            return resp.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return False


def _connection_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_HOST, default=current.get(CONF_HOST, DEFAULT_HOST)): str,
        vol.Required(CONF_PORT, default=current.get(CONF_PORT, DEFAULT_PORT)):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    })


def _content_schema(cur: dict[str, Any]) -> vol.Schema:
    def sug(key: str, default: Any = None) -> dict[str, Any]:
        val = cur.get(key, default)
        return {"suggested_value": val} if val not in (None, []) else {}

    return vol.Schema({
        vol.Optional(CONF_WEATHER, description=sug(CONF_WEATHER)):
            EntitySelector(EntitySelectorConfig(domain="weather")),
        vol.Optional(CONF_WASTE, description=sug(CONF_WASTE)):
            EntitySelector(EntitySelectorConfig(domain="sensor", multiple=True)),
        vol.Optional(CONF_CALENDARS, description=sug(CONF_CALENDARS)):
            EntitySelector(EntitySelectorConfig(domain="calendar", multiple=True)),
        vol.Optional(CONF_CALENDAR_TITLE,
                     default=cur.get(CONF_CALENDAR_TITLE, DEFAULT_CALENDAR_TITLE)):
            TextSelector(),
        vol.Optional(CONF_CALENDAR_DAYS,
                     default=cur.get(CONF_CALENDAR_DAYS, DEFAULT_CALENDAR_DAYS)):
            NumberSelector(NumberSelectorConfig(min=1, max=365, step=1,
                                                mode=NumberSelectorMode.BOX,
                                                unit_of_measurement="Tage")),
        vol.Optional(CONF_VALUES, description=sug(CONF_VALUES)):
            EntitySelector(EntitySelectorConfig(multiple=True)),
        vol.Optional(CONF_VALUES_TITLE,
                     default=cur.get(CONF_VALUES_TITLE, DEFAULT_VALUES_TITLE)):
            TextSelector(),
        vol.Required(CONF_ROTATION, default=str(cur.get(CONF_ROTATION, DEFAULT_ROTATION))):
            SelectSelector(SelectSelectorConfig(options=["0", "180"],
                                                mode=SelectSelectorMode.DROPDOWN,
                                                translation_key="rotation")),
        vol.Required(CONF_INTERVAL, default=cur.get(CONF_INTERVAL, DEFAULT_INTERVAL)):
            NumberSelector(NumberSelectorConfig(min=5, max=1440, step=5,
                                                mode=NumberSelectorMode.BOX,
                                                unit_of_measurement="min")),
    })


def _clean_content(user_input: dict[str, Any]) -> dict[str, Any]:
    out = {
        CONF_WEATHER: user_input.get(CONF_WEATHER) or None,
        CONF_CALENDAR_TITLE: (user_input.get(CONF_CALENDAR_TITLE) or DEFAULT_CALENDAR_TITLE).strip(),
        CONF_CALENDAR_DAYS: int(user_input.get(CONF_CALENDAR_DAYS, DEFAULT_CALENDAR_DAYS)),
        CONF_VALUES_TITLE: (user_input.get(CONF_VALUES_TITLE) or DEFAULT_VALUES_TITLE).strip(),
        CONF_ROTATION: str(user_input.get(CONF_ROTATION, DEFAULT_ROTATION)),
        CONF_INTERVAL: int(user_input.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
    }
    for key in LIST_KEYS:
        out[key] = list(user_input.get(key) or [])
    return out


class BilderrahmenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._conn: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            if await _can_connect(self.hass, host, port):
                self._conn = {CONF_HOST: host, CONF_PORT: port}
                return await self.async_step_content()
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_content(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="Bilderrahmen", data=self._conn, options=_clean_content(user_input)
            )
        return self.async_show_form(step_id="content", data_schema=_content_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BilderrahmenOptionsFlow()


class BilderrahmenOptionsFlow(OptionsFlow):
    """Inhalte, Drehung, Intervall – und bei Bedarf die Adresse des Rahmens."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["content", "connection"])

    async def async_step_content(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            opts = {**self.config_entry.options, **_clean_content(user_input)}
            return self.async_create_entry(data=opts)
        return self.async_show_form(
            step_id="content", data_schema=_content_schema(dict(self.config_entry.options))
        )

    async def async_step_connection(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            if await _can_connect(self.hass, host, port):
                return self.async_create_entry(
                    data={**self.config_entry.options, CONF_HOST: host, CONF_PORT: port}
                )
            errors["base"] = "cannot_connect"
            current = user_input
        return self.async_show_form(
            step_id="connection", data_schema=_connection_schema(current), errors=errors
        )
