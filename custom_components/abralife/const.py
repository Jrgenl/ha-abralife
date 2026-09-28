"""Constants for the Abralife (Waterguard+) integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "abralife"

# Config entry data keys
CONF_REGION: Final = "region"
CONF_USER_POOL_ID: Final = "user_pool_id"
CONF_CLIENT_ID: Final = "client_id"
CONF_API_URL: Final = "api_url"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_HOME_ID: Final = "home_id"
CONF_API_SETTINGS: Final = "api_settings"

# Options
CONF_ALLOW_OPEN: Final = "allow_open_valve"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 30  # seconds
MIN_SCAN_INTERVAL: Final = 15
UPDATE_INTERVAL: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Public connection settings for the Abralife cloud (AWS AppSync + Cognito).
# Abra documents these as public configuration, not credentials: they ship in
# every Abralife browser build, e.g. the example app on
# https://developer.abralife.com/app. They can be overridden in the setup
# wizard under "Avanserte API-innstillinger".
DEFAULT_REGION: Final = "eu-west-1"
DEFAULT_USER_POOL_ID: Final = "eu-west-1_4VBYn5OoK"
DEFAULT_CLIENT_ID: Final = "5qp60epsh9koila5nmavsv1hpn"
DEFAULT_API_URL: Final = "https://4hmz4jbydjbarli4cogtp2s5yi.appsync-api.eu-west-1.amazonaws.com/graphql"
