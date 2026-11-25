"""E-Paper-Bilderrahmen: zeigt ein frei gestaltbares Layout auf einem Waveshare-Rahmen."""

from __future__ import annotations

import json
import logging
import os

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .manager import FrameManager
from .websocket import async_register as async_register_ws

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.IMAGE, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
STATIC_URL = f"/{DOMAIN}_static"
PANEL_URL = "bilderrahmen"

type BilderrahmenConfigEntry = ConfigEntry[FrameManager]


def _version() -> str:
    with open(os.path.join(os.path.dirname(__file__), "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh).get("version", "0")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_register_ws(hass)
    www = os.path.join(os.path.dirname(__file__), "www")
    await hass.http.async_register_static_paths([StaticPathConfig(STATIC_URL, www, cache_headers=False)])
    version = await hass.async_add_executor_job(_version)
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name="bilderrahmen-panel",
        module_url=f"{STATIC_URL}/panel.js?v={version}",
        sidebar_title="Bilderrahmen",
        sidebar_icon="mdi:image-frame",
        require_admin=True,
        config={"static": STATIC_URL},
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BilderrahmenConfigEntry) -> bool:
    manager = FrameManager(hass, entry)
    entry.runtime_data = manager
    await manager.async_load_layout()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await manager.async_start()
    entry.async_on_unload(manager.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BilderrahmenConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: BilderrahmenConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
