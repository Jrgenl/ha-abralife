"""Setup wizard (config flow) for Abralife."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import AbraAuthError, AbraClient, AbraConnectionError, AbraHome, AbraMfaRequired
from .const import (
    CONF_ALLOW_OPEN,
    CONF_API_SETTINGS,
    CONF_API_URL,
    CONF_CLIENT_ID,
    CONF_HOME_ID,
    CONF_REFRESH_TOKEN,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_USER_POOL_ID,
    DEFAULT_API_URL,
    DEFAULT_CLIENT_ID,
    DEFAULT_REGION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USER_POOL_ID,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

_API_KEYS = (CONF_REGION, CONF_USER_POOL_ID, CONF_CLIENT_ID, CONF_API_URL)
_DEFAULTS = {
    CONF_REGION: DEFAULT_REGION,
    CONF_USER_POOL_ID: DEFAULT_USER_POOL_ID,
    CONF_CLIENT_ID: DEFAULT_CLIENT_ID,
    CONF_API_URL: DEFAULT_API_URL,
}


def _user_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    api = defaults.get(CONF_API_SETTINGS, _DEFAULTS)
    # Collapse the advanced section when the built-in defaults are complete.
    collapsed = all(_DEFAULTS.values())
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
            ),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
            ),
            vol.Required(CONF_API_SETTINGS): section(
                vol.Schema(
                    {
                        vol.Required(CONF_REGION, default=api.get(CONF_REGION, "")): str,
                        vol.Required(CONF_USER_POOL_ID, default=api.get(CONF_USER_POOL_ID, "")): str,
                        vol.Required(CONF_CLIENT_ID, default=api.get(CONF_CLIENT_ID, "")): str,
                        vol.Required(CONF_API_URL, default=api.get(CONF_API_URL, "")): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.URL)
                        ),
                    }
                ),
                {"collapsed": collapsed},
            ),
        }
    )


class AbraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Abralife setup wizard."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._homes: list[AbraHome] = []

    async def _login(self, username: str, password: str, api: Mapping[str, Any]) -> tuple[AbraClient | None, dict[str, str]]:
        client = AbraClient(
            async_get_clientsession(self.hass),
            region=api[CONF_REGION].strip(),
            user_pool_id=api[CONF_USER_POOL_ID].strip(),
            client_id=api[CONF_CLIENT_ID].strip(),
            api_url=api[CONF_API_URL].strip(),
        )
        try:
            await client.login(username.strip(), password)
        except AbraMfaRequired:
            return None, {"base": "mfa_not_supported"}
        except AbraAuthError:
            return None, {"base": "invalid_auth"}
        except AbraConnectionError:
            return None, {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error during Abralife login")
            return None, {"base": "unknown"}
        return client, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1: e-mail and password."""
        errors: dict[str, str] = {}
        client: AbraClient | None = None
        if user_input is not None:
            api = user_input[CONF_API_SETTINGS]
            if not all(str(api.get(k, "")).strip() for k in _API_KEYS):
                errors["base"] = "missing_api_settings"
            else:
                client, errors = await self._login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD], api)
            if not errors and client is not None:
                try:
                    self._homes = await client.get_homes()
                except AbraConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    if not self._homes:
                        return self.async_abort(reason="no_homes")
                    self._data = {
                        CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                        CONF_REFRESH_TOKEN: client.refresh_token,
                        **{k: str(api[k]).strip() for k in _API_KEYS},
                    }
                    if len(self._homes) == 1:
                        return await self._create(self._homes[0])
                    return await self.async_step_home()

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input or {}),
            errors=errors,
            description_placeholders={"portal": "https://developer.abralife.com/"},
        )

    async def async_step_home(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 2 (only with several homes): pick the home."""
        if user_input is not None:
            home = next(h for h in self._homes if h.id == user_input[CONF_HOME_ID])
            return await self._create(home)
        options = [SelectOptionDict(value=h.id, label=h.name) for h in self._homes]
        return self.async_show_form(
            step_id="home",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOME_ID): SelectSelector(SelectSelectorConfig(options=options))}
            ),
        )

    async def _create(self, home: AbraHome) -> ConfigFlowResult:
        await self.async_set_unique_id(home.id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=home.name, data={**self._data, CONF_HOME_ID: home.id})

    # ---------------------------------------------------------------- reauth
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            client, errors = await self._login(entry.data[CONF_USERNAME], user_input[CONF_PASSWORD], entry.data)
            if client is not None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_REFRESH_TOKEN: client.refresh_token}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
                    )
                }
            ),
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> AbraOptionsFlow:
        return AbraOptionsFlow()


class AbraOptionsFlow(OptionsFlow):
    """Options: safety switch for opening the water and polling interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ALLOW_OPEN, default=opts.get(CONF_ALLOW_OPEN, False)): BooleanSelector(),
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL, max=600, step=5, unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
