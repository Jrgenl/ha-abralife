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
from .entity import AbraEntity


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
    async_add_entities(
        AbraBinarySensor(coordinator, dev.id, desc)
        for dev in coordinator.data.values()
        for desc in DESCRIPTIONS
        if desc.value_fn(dev) is not None
    )


class AbraBinarySensor(AbraEntity, BinarySensorEntity):
    entity_description: AbraBinaryDescription

    def __init__(self, coordinator: AbraCoordinator, device_id: str, description: AbraBinaryDescription) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        # The connectivity sensor must stay available to report "offline".
        if self.entity_description.key == "online":
            return self.coordinator.last_update_success and self._device_id in self.coordinator.data
        return super().available

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.device)
