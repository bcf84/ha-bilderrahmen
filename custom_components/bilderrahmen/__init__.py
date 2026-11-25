"""E-Paper-Bilderrahmen: zeigt ausgewählte Home-Assistant-Inhalte auf einem Waveshare-Rahmen."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .manager import FrameManager

PLATFORMS = [Platform.BUTTON, Platform.IMAGE, Platform.SENSOR]

type BilderrahmenConfigEntry = ConfigEntry[FrameManager]


async def async_setup_entry(hass: HomeAssistant, entry: BilderrahmenConfigEntry) -> bool:
    manager = FrameManager(hass, entry)
    entry.runtime_data = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await manager.async_start()
    entry.async_on_unload(manager.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BilderrahmenConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: BilderrahmenConfigEntry) -> None:
    """Nach Änderungen in den Einstellungen neu laden – das zeichnet den Rahmen sofort neu."""
    await hass.config_entries.async_reload(entry.entry_id)
