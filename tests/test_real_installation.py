"""Tests against data shaped like a real Waterguard+ installation."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

import copy

from custom_components.abralife.api import AbraClient, AbraData, parse_home
from custom_components.abralife.const import DOMAIN

from .fixtures_real import HUB, REAL_EXTRAS, REAL_HOME

DATA = {"username": "a@b.no", "refresh_token": "rt", "home_id": "home-1", "region": "eu-west-1",
        "user_pool_id": "p", "client_id": "c", "api_url": "https://x/graphql"}


async def _real_data() -> AbraData:
    """Run AbraClient.get_data against canned responses for all three queries."""
    responses = {"AbraHomes": {"homes": [copy.deepcopy(REAL_HOME)]}, "AbraExtras": REAL_EXTRAS,
                 "AbraAlarms": {"alarms": {"alarms": []}}}

    async def graphql(self, query, variables=None):
        self.last_errors = []
        return copy.deepcopy(next(v for k, v in responses.items() if f"query {k}" in query))

    with patch.object(AbraClient, "graphql", graphql):
        client = AbraClient(None, region="r", user_pool_id="p", client_id="c", api_url="u")
        return await client.get_data("home-1")


async def test_parse_real_home() -> None:
    devices = (await _real_data()).devices
    hub, valve = devices[HUB], devices[f"{HUB}valveMonitor"]
    kitchen, tape = devices["sensor-kitchen"], devices[f"{HUB}waterMonitor"]

    assert (valve.kind, valve.valve_open, valve.valve_uses_open_percent) == ("valve", True, True)
    assert valve.fault is None  # empty fault list
    assert hub.fault == "fault/disconnect"
    assert hub.battery is None  # mains powered Linkbox reports 0 without backup battery
    assert (kitchen.online, kitchen.last_reported) == (False, "2026-04-03T15:57:54Z")
    assert (kitchen.temperature, kitchen.battery, kitchen.leak) == (27.0, 62.0, False)
    assert (tape.kind, tape.leak, tape.online) == ("water_sensor", False, None)


async def test_real_entities(hass: HomeAssistant) -> None:
    base = "custom_components.abralife.api.AbraClient"
    with (
        patch(f"{base}.get_data", AsyncMock(return_value=await _real_data())),
        patch(f"{base}.set_valve", AsyncMock()) as set_valve,
    ):
        entry = MockConfigEntry(domain=DOMAIN, title="Hjemme", unique_id="home-1", data=DATA)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("valve.waterguard_valve").state == "open"
        # Offline sensor: readings keep their last value, leak state is withheld
        assert hass.states.get("sensor.waterguard_water_sensor_temperature").state == "27.0"
        assert hass.states.get("sensor.waterguard_water_sensor_battery").state == "62.0"
        assert hass.states.get("binary_sensor.waterguard_water_sensor_leak").state == "unavailable"
        connection = hass.states.get("binary_sensor.waterguard_water_sensor_connection")
        assert connection.state == "off"
        assert connection.attributes["last_reported"] == "2026-04-03T15:57:54Z"
        # Sensor tape has no connection attribute and stays available
        assert hass.states.get("binary_sensor.linkbox_sensortape_leak").state == "off"
        problem = hass.states.get("binary_sensor.linkbox_wifi_problem")
        assert (problem.state, problem.attributes["fault"]) == ("on", "fault/disconnect")
        assert hass.states.get("sensor.linkbox_wifi_battery") is None

        await hass.services.async_call("valve", "close_valve", {"entity_id": "valve.waterguard_valve"}, blocking=True)
        set_valve.assert_awaited_once_with(f"{HUB}valveMonitor", False, use_open_percent=True)


def test_valve_state_unknown_without_extras() -> None:
    """If the extras query fails, the valve state is unknown rather than wrong."""
    valve = parse_home(copy.deepcopy(REAL_HOME))[f"{HUB}valveMonitor"]
    assert valve.valve_open is None
    assert valve.valve_uses_open_percent is True
