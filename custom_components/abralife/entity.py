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
    # Abra keeps the last reported values for disconnected devices. Readings
    # such as temperature stay visible; states that would be unsafe to trust
    # when stale (leak, valve) set this to True.
    _unavailable_when_offline = False

    def __init__(self, coordinator: AbraCoordinator, device_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}"
        device = self.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            manufacturer="Abra / Waterguard",
            model=(device.device_type or "").replace("_", " ").title() or None,
            serial_number=device.serial,
            sw_version=device.firmware,
            suggested_area=device.room,
            via_device=(DOMAIN, device.via_hub) if device.via_hub else (DOMAIN, coordinator.home_id),
        )

    @property
    def device(self) -> AbraDevice:
        return self.coordinator.data.devices[self._device_id]

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._device_id in self.coordinator.data.devices
            and not (self._unavailable_when_offline and self.device.online is False)
        )


class AbraHomeEntity(CoordinatorEntity[AbraCoordinator]):
    """Entity for the home itself (home-level alarms)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AbraCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.home_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.home_id)},
            name=coordinator.config_entry.title,
            manufacturer="Abra / Waterguard",
            model="Abralife-hjem",
        )
