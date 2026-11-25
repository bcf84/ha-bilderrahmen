"""Websocket-Befehle für den Layout-Editor."""

from __future__ import annotations

import base64
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .layout import CATALOG, TEMPLATES, THEME_FIELDS
from .render import H, W


def _manager(hass: HomeAssistant, entry_id: str):
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or not hasattr(entry, "runtime_data"):
        return None
    return entry.runtime_data


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_frames)
    websocket_api.async_register_command(hass, ws_get)
    websocket_api.async_register_command(hass, ws_preview)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_push)
    websocket_api.async_register_command(hass, ws_template)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/frames"})
@callback
def ws_frames(hass, connection, msg) -> None:
    frames = []
    for e in hass.config_entries.async_entries(DOMAIN):
        m = getattr(e, "runtime_data", None)
        frames.append({"entry_id": e.entry_id, "title": e.title, "loaded": m is not None,
                       "status": getattr(m, "status", None)})
    connection.send_result(msg["id"], {"frames": frames})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get", vol.Required("entry_id"): str})
@callback
def ws_get(hass, connection, msg) -> None:
    m = _manager(hass, msg["entry_id"])
    if m is None:
        connection.send_error(msg["id"], "not_found", "Rahmen nicht gefunden oder nicht geladen")
        return
    connection.send_result(msg["id"], {
        "layout": m.layout, "catalog": CATALOG, "theme_fields": THEME_FIELDS,
        "size": [W, H], "status": m.status,
        "templates": [{"id": k, "label": v} for k, v in TEMPLATES.items()],
    })


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/preview",
    vol.Required("entry_id"): str,
    vol.Required("layout"): dict,
})
@websocket_api.async_response
async def ws_preview(hass, connection, msg) -> None:
    m = _manager(hass, msg["entry_id"])
    if m is None:
        connection.send_error(msg["id"], "not_found", "Rahmen nicht gefunden")
        return
    try:
        png = await m.async_preview(msg["layout"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_layout", str(err))
        return
    connection.send_result(msg["id"], {"image": base64.b64encode(png).decode()})


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/save",
    vol.Required("entry_id"): str,
    vol.Required("layout"): dict,
})
@websocket_api.async_response
async def ws_save(hass, connection, msg) -> None:
    m = _manager(hass, msg["entry_id"])
    if m is None:
        connection.send_error(msg["id"], "not_found", "Rahmen nicht gefunden")
        return
    try:
        layout = await m.async_save_layout(msg["layout"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_layout", str(err))
        return
    connection.send_result(msg["id"], {"layout": layout})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/push", vol.Required("entry_id"): str})
@websocket_api.async_response
async def ws_push(hass, connection, msg) -> None:
    m = _manager(hass, msg["entry_id"])
    if m is None:
        connection.send_error(msg["id"], "not_found", "Rahmen nicht gefunden")
        return
    await m.async_refresh(force=True)
    connection.send_result(msg["id"], {"status": m.status})



@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/template",
    vol.Required("entry_id"): str,
    vol.Required("name"): str,
})
@callback
def ws_template(hass, connection, msg) -> None:
    m = _manager(hass, msg["entry_id"])
    if m is None:
        connection.send_error(msg["id"], "not_found", "Rahmen nicht gefunden")
        return
    connection.send_result(msg["id"], {"layout": m.template(msg["name"])})
