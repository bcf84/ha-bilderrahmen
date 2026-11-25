"""Status-Sensoren des Rahmens."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BilderrahmenConfigEntry
from .entity import FrameEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BilderrahmenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    m = entry.runtime_data
    async_add_entities([LastDisplaySensor(m, "last_display"), StatusSensor(m, "status")])


class LastDisplaySensor(FrameEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> datetime | None:
        return self.manager.last_display


class StatusSensor(FrameEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:image-frame"

    @property
    def native_value(self) -> str:
        return self.manager.status
