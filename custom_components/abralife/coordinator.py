"""Data update coordinator for Abralife."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AbraAuthError, AbraClient, AbraData, AbraError
from .const import CONF_HOME_ID, CONF_REFRESH_TOKEN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type AbraConfigEntry = ConfigEntry[AbraCoordinator]


class AbraCoordinator(DataUpdateCoordinator[AbraData]):
    """Polls hubs, devices and alarms in one Abralife home."""

    config_entry: AbraConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AbraConfigEntry, client: AbraClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.home_id: str = entry.data[CONF_HOME_ID]

    async def _async_update_data(self) -> AbraData:
        try:
            data = await self.client.get_data(self.home_id)
        except AbraAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AbraError as err:
            raise UpdateFailed(str(err)) from err

        # Persist a rotated refresh token so a restart doesn't need a new login.
        token = self.client.refresh_token
        if token and token != self.config_entry.data.get(CONF_REFRESH_TOKEN):
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, CONF_REFRESH_TOKEN: token}
            )
        return data
