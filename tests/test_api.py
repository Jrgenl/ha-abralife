"""Tests for the device parser."""

from custom_components.abralife.api import parse_device

from .conftest import RAW_DEVICES


def test_parse_valve() -> None:
    dev = parse_device(RAW_DEVICES[0])
    assert dev.kind == "valve"
    assert dev.valve_open is True
    assert dev.room == "Teknisk rom"


def test_parse_sensor() -> None:
    dev = parse_device(RAW_DEVICES[1])
    assert dev.kind == "water_sensor"
    assert dev.leak is False
    assert (dev.temperature, dev.humidity, dev.battery) == (21.5, 40.0, 88.0)


def test_parse_string_states() -> None:
    dev = parse_device({"id": 5, "type": "valve", "state": {"valveState": "CLOSED"}})
    assert dev.valve_open is False
    assert dev.name == "5"
    assert parse_device({"id": "x", "state": {"waterDetected": "WET"}}).leak is True


async def test_refresh_and_graphql(hass, aioclient_mock) -> None:
    """Refresh token -> access token -> GraphQL, falling back to the ID token on 401."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from custom_components.abralife.api import AbraClient

    aioclient_mock.post(
        "https://cognito-idp.eu-west-1.amazonaws.com/",
        json={"AuthenticationResult": {"AccessToken": "acc", "IdToken": "idt", "ExpiresIn": 3600}},
    )
    calls: list[str] = []
    api = "https://x.appsync-api.eu-west-1.amazonaws.com/graphql"

    async def graphql(method, url, data):
        calls.append("x")
        from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

        if len(calls) == 1:
            return AiohttpClientMockResponse(method, url, status=401, json={"errors": [{"message": "Unauthorized"}]})
        return AiohttpClientMockResponse(
            method, url, json={"data": {"home": {"devices": [RAW_DEVICES[0]]}}}
        )

    aioclient_mock.post(api, side_effect=graphql)
    client = AbraClient(async_get_clientsession(hass), region="eu-west-1", user_pool_id="p",
                        client_id="c", api_url=api, refresh_token="rt")
    devices = await client.get_devices("h1")
    assert devices["v1"].valve_open is True
    assert client.refresh_token == "rt"  # no rotation returned -> keep old
    headers = [c[3] for c in aioclient_mock.mock_calls if str(c[1]) == api]
    assert [h["Authorization"] for h in headers] == ["acc", "idt"]
