"""Fixtures for Abralife tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from custom_components.abralife.api import AbraHome, parse_device

pytest_plugins = ["pytest_homeassistant_custom_component"]

RAW_DEVICES = [
    {"id": "v1", "name": "Hovedkran", "type": "VALVE", "model": "Linkbox+", "online": True,
     "room": {"name": "Teknisk rom"}, "state": '{"valveOpen": true}'},
    {"id": "s1", "name": "Kjøkken", "type": "WATER_SENSOR", "model": "WaterSensor+", "online": True,
     "state": {"leak": False, "temperature": 21.5, "humidity": 40, "batteryLevel": 88}},
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_api() -> Generator[dict[str, AsyncMock]]:
    base = "custom_components.abralife.api.AbraClient"
    with (
        patch(f"{base}.login", new_callable=AsyncMock) as login,
        patch(f"{base}.get_homes", new_callable=AsyncMock, return_value=[AbraHome("h1", "Hjemme")]) as homes,
        patch(f"{base}.get_devices", new_callable=AsyncMock,
              side_effect=lambda _h: {d.id: d for d in map(parse_device, RAW_DEVICES)}) as devices,
        patch(f"{base}.set_valve", new_callable=AsyncMock) as set_valve,
        patch(f"{base}.refresh_token", new_callable=PropertyMock, return_value="rt-1"),
    ):
        yield {"login": login, "get_homes": homes, "get_devices": devices, "set_valve": set_valve}
