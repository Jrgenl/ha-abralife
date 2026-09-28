"""Tests for setup and entities."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.abralife.api import AbraAlarm, AbraAuthError
from custom_components.abralife.const import DOMAIN

from .conftest import make_data

DATA = {"username": "a@b.no", "refresh_token": "rt-1", "home_id": "h1", "region": "eu-west-1",
        "user_pool_id": "p", "client_id": "c", "api_url": "https://x/graphql"}


async def _setup(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Hjemme", unique_id="h1", data=DATA, options=options or {})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("valve.hovedkran").state == "open"
    assert hass.states.get("binary_sensor.kjokken_leak").state == "off"
    assert hass.states.get("sensor.kjokken_temperature").state == "21.5"
    assert hass.states.get("sensor.kjokken_battery").state == "88.0"
    assert hass.states.get("sensor.linkbox_waterguard_mode").state == "normal"
    assert hass.states.get("binary_sensor.hjemme_water_alarm").state == "off"
    # The door lock must not show up as a valve
    assert hass.states.get("valve.ytterdor") is None


async def test_close_allowed_open_blocked(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    await _setup(hass)
    await hass.services.async_call("valve", "close_valve", {"entity_id": "valve.hovedkran"}, blocking=True)
    mock_api["set_valve"].assert_awaited_once_with("v1", False)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("valve", "open_valve", {"entity_id": "valve.hovedkran"}, blocking=True)


async def test_open_when_enabled(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    await _setup(hass, {"allow_open_valve": True})
    await hass.services.async_call("valve", "open_valve", {"entity_id": "valve.hovedkran"}, blocking=True)
    mock_api["set_valve"].assert_awaited_once_with("v1", True)


async def test_auth_failure_starts_reauth(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    mock_api["get_data"].side_effect = AbraAuthError
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert flows and flows[0]["context"]["source"] == "reauth"


async def test_water_alarm_and_resolve(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    mock_api["get_data"].side_effect = lambda _h: make_data([AbraAlarm("a1", "WaterAlarm", "ALARM")])
    await _setup(hass)
    assert hass.states.get("binary_sensor.hjemme_water_alarm").state == "on"
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.hjemme_resolve_water_alarm"}, blocking=True
    )
    mock_api["resolve_alarm"].assert_awaited_once_with("a1")
    mock_api["set_valve"].assert_not_awaited()  # resolving never reopens the water


async def test_diagnostics(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    from unittest.mock import patch

    from custom_components.abralife.diagnostics import async_get_config_entry_diagnostics

    entry = await _setup(hass)
    dump = {"home": {"id": "h1", "hubs": [{"id": "hub1", "devices": [{"id": "v1", "serialNumber": "X"}]}]}, "errors": []}
    with patch("custom_components.abralife.api.AbraClient.diagnostics_dump", AsyncMock(return_value=dump)):
        result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["entry"]["refresh_token"] == "**REDACTED**"
    assert result["all_attributes"]["home"]["hubs"][0]["devices"][0]["serialNumber"] == "**REDACTED**"
    assert {d["id"] for d in result["parsed_devices"]} == {"hub1", "v1", "s1", "lock1"}
