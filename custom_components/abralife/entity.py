"""Base entity for Abralife."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AbraDevice
from .const import DOMAIN
from .coordinator import AbraCoordinator


class AbraEntity(CoordinatorEntity[AbraCoordinator]):
    """Entity bound to one Abralife device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AbraCoordinator, device_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}"
        device = self.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            manufacturer="Abra / Waterguard",
            model=device.model,
            suggested_area=device.room,
        )

    @property
    def device(self) -> AbraDevice:
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._device_id in self.coordinator.data
            and self.device.online is not False
        )
