"""Temperature, humidity and battery sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import AbraDevice
from .coordinator import AbraConfigEntry, AbraCoordinator
from .entity import AbraEntity


@dataclass(frozen=True, kw_only=True)
class AbraSensorDescription(SensorEntityDescription):
    value_fn: Callable[[AbraDevice], float | None]


DESCRIPTIONS: tuple[AbraSensorDescription, ...] = (
    AbraSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: d.temperature,
    ),
    AbraSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.humidity,
    ),
    AbraSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.battery,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: AbraConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        AbraSensor(coordinator, dev.id, desc)
        for dev in coordinator.data.values()
        for desc in DESCRIPTIONS
        if desc.value_fn(dev) is not None
    )


class AbraSensor(AbraEntity, SensorEntity):
    entity_description: AbraSensorDescription

    def __init__(self, coordinator: AbraCoordinator, device_id: str, description: AbraSensorDescription) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.device)
