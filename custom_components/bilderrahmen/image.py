"""Vorschau des aktuellen Rahmenbildes in Home Assistant."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BilderrahmenConfigEntry
from .entity import FrameEntity
from .manager import FrameManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BilderrahmenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([PreviewImage(hass, entry.runtime_data)])


class PreviewImage(FrameEntity, ImageEntity):
    _attr_content_type = "image/png"

    def __init__(self, hass: HomeAssistant, manager: FrameManager) -> None:
        FrameEntity.__init__(self, manager, "preview")
        ImageEntity.__init__(self, hass)
        self._attr_image_last_updated = manager.image_updated

    def _handle_update(self) -> None:
        self._attr_image_last_updated = self.manager.image_updated
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        return self.manager.image
