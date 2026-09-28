"""Tests for the setup wizard."""

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.abralife.api import AbraAuthError, AbraHome
from custom_components.abralife.const import DOMAIN

API = {"region": "eu-west-1", "user_pool_id": "eu-west-1_abc", "client_id": "cid",
       "api_url": "https://x.appsync-api.eu-west-1.amazonaws.com/graphql"}
INPUT = {"username": "a@b.no", "password": "pw", "api_settings": API}


async def test_single_home(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hjemme"
    assert result["data"]["refresh_token"] == "rt-1"
    assert result["data"]["home_id"] == "h1"
    assert "password" not in result["data"]
    mock_api["login"].assert_awaited_once_with("a@b.no", "pw")


async def test_multiple_homes(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    mock_api["get_homes"].return_value = [AbraHome("h1", "Hus"), AbraHome("h2", "Hytte")]
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["step_id"] == "home"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"home_id": "h2"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hytte"


async def test_invalid_auth_then_recover(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    mock_api["login"].side_effect = AbraAuthError
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["errors"] == {"base": "invalid_auth"}
    mock_api["login"].side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_missing_api_settings(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**INPUT, "api_settings": {**API, "client_id": " "}}
    )
    assert result["errors"] == {"base": "missing_api_settings"}
    mock_api["login"].assert_not_awaited()
