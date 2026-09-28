"""Water shut-off valves (Waterguard+ Linkbox+)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.valve import ValveDeviceClass, ValveEntity, ValveEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import AbraError
from .const import CONF_ALLOW_OPEN, DOMAIN
from .coordinator import AbraConfigEntry, AbraCoordinator
from .entity import AbraEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: AbraConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    allow_open = entry.options.get(CONF_ALLOW_OPEN, False)
    async_add_entities(
        AbraValve(coordinator, dev.id, allow_open)
        for dev in coordinator.data.devices.values()
        if dev.kind == "valve"
    )


class AbraValve(AbraEntity, ValveEntity):
    """Main water valve.

    Closing is always allowed. Opening is only offered when the user has
    enabled it in the options, following Abra's guidance that reopening the
    water supply must be a deliberate action.
    """

    _attr_device_class = ValveDeviceClass.WATER
    _attr_reports_position = False
    _attr_name = None

    def __init__(self, coordinator: AbraCoordinator, device_id: str, allow_open: bool) -> None:
        super().__init__(coordinator, device_id, "valve")
        self._attr_supported_features = ValveEntityFeature.CLOSE | (
            ValveEntityFeature.OPEN if allow_open else ValveEntityFeature(0)
        )

    @property
    def is_closed(self) -> bool | None:
        is_open = self.device.valve_open
        return None if is_open is None else not is_open

    async def _set(self, open_: bool) -> None:
        try:
            await self.coordinator.client.set_valve(self._device_id, open_)
        except AbraError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="valve_failed", translation_placeholders={"error": str(err)}
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_close_valve(self, **kwargs: Any) -> None:
        await self._set(False)

    async def async_open_valve(self, **kwargs: Any) -> None:
        if not self.supported_features & ValveEntityFeature.OPEN:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="open_disabled")
        await self._set(True)
