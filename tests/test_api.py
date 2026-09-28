"""Tests for the API client and parser."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.abralife.api import AbraClient, AbraError, parse_home

from .conftest import RAW_HOME

API = "https://x.appsync-api.eu-west-1.amazonaws.com/graphql"
COGNITO = "https://cognito-idp.eu-west-1.amazonaws.com/"


def test_parse_home() -> None:
    devices = parse_home(RAW_HOME)
    hub, valve, sensor, lock = devices["hub1"], devices["v1"], devices["s1"], devices["lock1"]

    assert (hub.kind, hub.water_guard_mode, hub.online) == ("hub", "NORMAL", True)
    assert (valve.kind, valve.valve_open, valve.via_hub) == ("valve", True, "hub1")
    assert valve.room == "Teknisk rom"  # inherited from the Linkbox
    assert sensor.kind == "water_sensor"
    assert sensor.leak is False
    assert (sensor.temperature, sensor.humidity, sensor.battery) == (21.5, 40.0, 88.0)
    assert sensor.fault is None
    # A door lock also uses isUnlocked but must never become a water valve
    assert (lock.kind, lock.valve_open) == ("other", None)


def test_parse_leak_and_fault() -> None:
    sensor = {
        "id": "s2",
        "deviceType": "WATER_SENSOR_TAPE",
        "traits": [
            {"attributes": [
                {"__typename": "TraitAttributeAlarm", "alarm": "WATER_LEAK"},
                {"__typename": "TraitAttributeFault", "fault": {"code": "E12", "name": "Cable cut", "description": None}},
            ]}
        ],
    }
    dev = parse_home({"hubs": [{"id": "h", "waterGuard": {"mode": "TAMPERED"}, "devices": [sensor]}]})["s2"]
    assert dev.leak is True
    assert dev.fault == "Cable cut"
    assert dev.name == "Water Sensor Tape"


def _cognito(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(
        COGNITO, json={"AuthenticationResult": {"AccessToken": "acc", "IdToken": "idt", "ExpiresIn": 3600}}
    )


def _client(hass: HomeAssistant) -> AbraClient:
    return AbraClient(
        async_get_clientsession(hass), region="eu-west-1", user_pool_id="p", client_id="c", api_url=API,
        refresh_token="rt",
    )


async def test_refresh_and_get_data(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Refresh token -> ID token -> GraphQL, falling back to the access token on 401."""
    from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

    _cognito(aioclient_mock)
    responses = [
        (401, {"errors": [{"message": "Unauthorized"}]}),
        (200, {"data": {"homes": [RAW_HOME]}}),
        (200, {"data": {"alarms": {"alarms": [
            {"__typename": "WaterAlarm", "id": "a1", "state": "ALARM", "triggeredAt": "2026-09-28T06:00:00Z"},
            {"__typename": "FireAlarm", "id": "a2", "state": "CLEARED", "triggeredAt": None},
        ]}}}),
    ]

    async def graphql(method, url, data):
        status, body = responses.pop(0)
        return AiohttpClientMockResponse(method, url, status=status, json=body)

    aioclient_mock.post(API, side_effect=graphql)
    client = _client(hass)
    data = await client.get_data("h1")

    assert data.devices["v1"].valve_open is True
    assert data.water_alarm is True
    assert client.refresh_token == "rt"  # no rotation returned -> keep old
    auth = [c[3]["Authorization"] for c in aioclient_mock.mock_calls if str(c[1]) == API]
    assert auth == ["idt", "acc", "acc"]


async def test_set_valve_uses_unlock_mutation(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    _cognito(aioclient_mock)
    aioclient_mock.post(API, json={"data": {"deviceSetUnlocked": {"command": {}, "errors": []}}})
    await _client(hass).set_valve("v1", False)
    body = [c[2] for c in aioclient_mock.mock_calls if str(c[1]) == API][0]
    assert "deviceSetUnlocked" in body["query"]
    assert body["variables"] == {"deviceId": "v1", "open": False}


async def test_mutation_errors_raise(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    _cognito(aioclient_mock)
    aioclient_mock.post(API, json={"data": {"deviceSetUnlocked": {"errors": [
        {"__typename": "TraitUpdateFailedError", "message": "Valve did not respond"}]}}})
    try:
        await _client(hass).set_valve("v1", True)
    except AbraError as err:
        assert "Valve did not respond" in str(err)
    else:
        raise AssertionError("expected AbraError")
