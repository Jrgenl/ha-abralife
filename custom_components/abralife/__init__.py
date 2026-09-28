"""The Abralife (Waterguard+) integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AbraClient
from .const import CONF_API_URL, CONF_CLIENT_ID, CONF_REFRESH_TOKEN, CONF_REGION, CONF_USER_POOL_ID
from .coordinator import AbraConfigEntry, AbraCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.VALVE]


def build_client(hass: HomeAssistant, data: dict) -> AbraClient:
    """Create an API client from config entry data."""
    return AbraClient(
        async_get_clientsession(hass),
        region=data[CONF_REGION],
        user_pool_id=data[CONF_USER_POOL_ID],
        client_id=data[CONF_CLIENT_ID],
        api_url=data[CONF_API_URL],
        refresh_token=data.get(CONF_REFRESH_TOKEN),
    )


async def async_setup_entry(hass: HomeAssistant, entry: AbraConfigEntry) -> bool:
    """Set up Abralife from a config entry."""
    coordinator = AbraCoordinator(hass, entry, build_client(hass, dict(entry.data)))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    options = dict(entry.options)

    async def _async_options_updated(hass: HomeAssistant, entry: AbraConfigEntry) -> None:
        # Data updates (e.g. a rotated refresh token) must not trigger a reload.
        if dict(entry.options) != options:
            await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AbraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
