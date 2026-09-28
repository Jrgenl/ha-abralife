"""Diagnostics: lets users download raw API data to help map new devices."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_REFRESH_TOKEN
from .coordinator import AbraConfigEntry

TO_REDACT = {CONF_REFRESH_TOKEN, CONF_USERNAME, "email", "phone", "address", "serialNumber"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: AbraConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "devices": [async_redact_data(asdict(d), TO_REDACT) for d in coordinator.data.values()],
    }
