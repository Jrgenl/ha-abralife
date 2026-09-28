"""Button to acknowledge (resolve) an active water alarm."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import AbraError
from .const import DOMAIN
from .coordinator import AbraConfigEntry, AbraCoordinator
from .entity import AbraHomeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: AbraConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([AbraResolveWaterAlarm(entry.runtime_data)])


class AbraResolveWaterAlarm(AbraHomeEntity, ButtonEntity):
    """Resolve active water alarms.

    This never opens the valve: Abra keeps alarm reset and reopening the water
    as two separate, deliberate actions.
    """

    _attr_translation_key = "resolve_water_alarm"

    def __init__(self, coordinator: AbraCoordinator) -> None:
        super().__init__(coordinator, "resolve_water_alarm")

    async def async_press(self) -> None:
        active = [a for a in self.coordinator.data.alarms if a.kind == "WaterAlarm" and a.active]
        if not active:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_active_alarm")
        try:
            for alarm in active:
                await self.coordinator.client.resolve_alarm(alarm.id)
        except AbraError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="alarm_failed", translation_placeholders={"error": str(err)}
            ) from err
        await self.coordinator.async_request_refresh()
