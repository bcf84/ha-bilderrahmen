"""Status-Sensoren des Rahmens."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricPotential, UnitOfTemperature
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
    async_add_entities([
        LastDisplaySensor(m, "last_display"), StatusSensor(m, "status"),
        DeviceSensor(m, "wifi_signal", ("wifi", "dbm"), "dBm", SensorDeviceClass.SIGNAL_STRENGTH, "mdi:wifi"),
        DeviceSensor(m, "battery", ("battery", "percent"), PERCENTAGE, SensorDeviceClass.BATTERY, None),
        DeviceSensor(m, "battery_voltage", ("battery", "voltage"), UnitOfElectricPotential.VOLT,
                     SensorDeviceClass.VOLTAGE, None),
        DeviceSensor(m, "cpu_temperature", ("system", "cpu_temp"), UnitOfTemperature.CELSIUS,
                     SensorDeviceClass.TEMPERATURE, None),
    ])


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


class DeviceSensor(FrameEntity, SensorEntity):
    """Werte, die der Pi im Rahmen meldet (WLAN, Akku, CPU)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, key, path, unit, device_class, icon) -> None:
        super().__init__(manager, key)
        self._path = path
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if icon:
            self._attr_icon = icon

    def _val(self):
        d = self.manager.device or {}
        for k in self._path:
            d = d.get(k) if isinstance(d, dict) else None
        return d

    @property
    def available(self) -> bool:
        return self._val() is not None

    @property
    def native_value(self):
        return self._val()

    @property
    def extra_state_attributes(self):
        if self._path[0] == "battery":
            b = (self.manager.device or {}).get("battery") or {}
            return {"charging": b.get("charging"), "current_ma": b.get("current_ma")}
        if self._path[0] == "wifi":
            w = (self.manager.device or {}).get("wifi") or {}
            return {"ssid": w.get("ssid"), "quality": w.get("label")}
        return None
