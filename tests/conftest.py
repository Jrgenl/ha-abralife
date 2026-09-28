"""Fixtures for Abralife tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from custom_components.abralife.api import AbraAlarm, AbraData, AbraHome, parse_home


def _trait(trait_type: str, *attributes: dict, commands: tuple[str, ...] = ()) -> dict:
    return {"traitType": trait_type, "commands": list(commands), "attributes": list(attributes)}


# Shaped like the response to queries.HOMES_QUERY (official Abralife schema)
RAW_HOME = {
    "id": "h1",
    "homeInfo": {"nickname": "Hjemme"},
    "hubs": [
        {
            "id": "hub1",
            "name": "Linkbox+",
            "serialNumber": "LB-1",
            "firmwareVersion": "3.1",
            "productType": "LINKBOX_PLUS",
            "area": {"areaName": "Teknisk rom"},
            "waterGuard": {"mode": "NORMAL", "showLevel1Warning": False, "showLevel2Warning": False},
            "traits": [_trait("CONNECTION", {"__typename": "TraitAttributeIsConnected", "isConnected": True})],
            "devices": [
                {
                    "id": "v1",
                    "deviceType": "WATER_VALVE",
                    "name": "Hovedkran",
                    "serialNumber": "V-1",
                    "area": None,
                    "traits": [
                        _trait("CONNECTION", {"__typename": "TraitAttributeIsConnected", "isConnected": True}),
                        _trait(
                            "WATER",
                            {"__typename": "TraitAttributeIsUnlocked", "isUnlocked": True},
                            {"__typename": "TraitAttributeWaterValvesConnected", "waterValvesConnected": 1},
                            commands=("UNLOCK",),
                        ),
                    ],
                },
                {
                    "id": "s1",
                    "deviceType": "WATER_LEAK_DETECTOR",
                    "name": "Kjøkken",
                    "serialNumber": "S-1",
                    "area": {"areaName": "Kjøkken"},
                    "traits": [
                        _trait("CONNECTION", {"__typename": "TraitAttributeIsConnected", "isConnected": True}),
                        _trait(
                            "SENSOR",
                            {"__typename": "TraitAttributeAlarm", "alarm": "NO_ALARM", "snoozed": False},
                            {"__typename": "TraitAttributeTemperature", "temperature": 21.5},
                            {"__typename": "TraitAttributeHumidity", "humidity": 40},
                        ),
                        _trait(
                            "POWER",
                            {"__typename": "TraitAttributeCurrentPowerSourceLevel", "currentPowerSourceLevel": 88},
                            {"__typename": "TraitAttributeLowBatteryWarning", "lowBatteryWarning": False},
                        ),
                        _trait("STATUS", {"__typename": "TraitAttributeFault", "fault": None}),
                    ],
                },
                {
                    "id": "lock1",
                    "deviceType": "DOOR_LOCK",
                    "name": "Ytterdør",
                    "serialNumber": "L-1",
                    "traits": [_trait("SMARTLOCK", {"__typename": "TraitAttributeIsUnlocked", "isUnlocked": False})],
                },
            ],
        }
    ],
}


def make_data(alarms: list[AbraAlarm] | None = None) -> AbraData:
    return AbraData(devices=parse_home(RAW_HOME), alarms=alarms or [])


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_api() -> Generator[dict[str, AsyncMock]]:
    base = "custom_components.abralife.api.AbraClient"
    with (
        patch(f"{base}.login", new_callable=AsyncMock) as login,
        patch(f"{base}.get_homes", new_callable=AsyncMock, return_value=[AbraHome("h1", "Hjemme")]) as homes,
        patch(f"{base}.get_data", new_callable=AsyncMock, side_effect=lambda _h: make_data()) as get_data,
        patch(f"{base}.set_valve", new_callable=AsyncMock) as set_valve,
        patch(f"{base}.resolve_alarm", new_callable=AsyncMock) as resolve_alarm,
        patch(f"{base}.refresh_token", new_callable=PropertyMock, return_value="rt-1"),
    ):
        yield {
            "login": login,
            "get_homes": homes,
            "get_data": get_data,
            "set_valve": set_valve,
            "resolve_alarm": resolve_alarm,
        }
