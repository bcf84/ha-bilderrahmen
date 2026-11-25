"""Knopf „Jetzt aktualisieren“."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BilderrahmenConfigEntry
from .entity import FrameEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BilderrahmenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([RefreshButton(entry.runtime_data, "refresh")])


class RefreshButton(FrameEntity, ButtonEntity):
    _attr_icon = "mdi:refresh"

    async def async_press(self) -> None:
        await self.manager.async_refresh(force=True)
