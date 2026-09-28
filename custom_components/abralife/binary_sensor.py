"""Leak and connectivity binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import AbraDevice
from .coordinator import AbraConfigEntry, AbraCoordinator
from .entity import AbraEntity, AbraHomeEntity


@dataclass(frozen=True, kw_only=True)
class AbraBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[AbraDevice], bool | None]


DESCRIPTIONS: tuple[AbraBinaryDescription, ...] = (
    AbraBinaryDescription(
        key="leak",
        translation_key="leak",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=lambda d: d.leak,
    ),
    AbraBinaryDescription(
        key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.low_battery,
    ),
    AbraBinaryDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: None if d.kind == "other" else d.fault is not None,
    ),
    AbraBinaryDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.online,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: AbraConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([AbraWaterAlarm(coordinator)])
    async_add_entities(
        AbraBinarySensor(coordinator, dev.id, desc)
        for dev in coordinator.data.devices.values()
        for desc in DESCRIPTIONS
        if desc.value_fn(dev) is not None
    )


class AbraBinarySensor(AbraEntity, BinarySensorEntity):
    entity_description: AbraBinaryDescription

    def __init__(self, coordinator: AbraCoordinator, device_id: str, description: AbraBinaryDescription) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description
        # A disconnected leak sensor must not claim "dry"
        self._unavailable_when_offline = description.key == "leak"

    @property
    def extra_state_attributes(self) -> dict[str, str | None] | None:
        if self.entity_description.key == "online":
            return {"last_reported": self.device.last_reported}
        if self.entity_description.key == "problem":
            return {"fault": self.device.fault}
        return None

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.device)


class AbraWaterAlarm(AbraHomeEntity, BinarySensorEntity):
    """Home-level water alarm, as recorded by Abra (authoritative source)."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_translation_key = "water_alarm"

    def __init__(self, coordinator: AbraCoordinator) -> None:
        super().__init__(coordinator, "water_alarm")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.water_alarm

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        active = [a for a in self.coordinator.data.alarms if a.kind == "WaterAlarm" and a.active]
        return {
            "state": active[0].state if active else None,
            "triggered_at": active[0].triggered_at if active else None,
        }
