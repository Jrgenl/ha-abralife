"""Async client for the Abralife cloud (AWS Cognito + AppSync GraphQL).

This module has no Home Assistant imports so it can also be used from the
stand-alone ``tools/abra_probe.py`` script.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from . import queries

_LOGGER = logging.getLogger(__name__)

_COGNITO_TARGET = "AWSCognitoIdentityProviderService.InitiateAuth"
_TOKEN_MARGIN = 120  # refresh this many seconds before expiry


class AbraError(Exception):
    """Base error for the Abralife client."""


class AbraAuthError(AbraError):
    """Credentials or refresh token rejected."""


class AbraMfaRequired(AbraAuthError):
    """The account requires a challenge (MFA / new password) we can't answer."""


class AbraConnectionError(AbraError):
    """Network problem or unexpected response from the API."""


@dataclass
class AbraTokens:
    """Cognito tokens."""

    access_token: str
    id_token: str
    refresh_token: str
    expires_at: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at - _TOKEN_MARGIN


@dataclass
class AbraHome:
    """A home (site) in Abralife."""

    id: str
    name: str


@dataclass
class AbraAlarm:
    """A home-level alarm record."""

    id: str
    kind: str  # GraphQL typename, e.g. "WaterAlarm"
    state: str  # ALARM, SNOOZED or CLEARED
    triggered_at: str | None = None

    @property
    def active(self) -> bool:
        return self.state in ("ALARM", "SNOOZED")


@dataclass
class AbraDevice:
    """Normalised view of an Abralife device or Linkbox (hub)."""

    id: str
    name: str
    kind: str  # "valve", "water_sensor", "hub" or "other"
    device_type: str | None = None
    serial: str | None = None
    firmware: str | None = None
    room: str | None = None
    via_hub: str | None = None
    online: bool | None = None
    last_reported: str | None = None
    valve_open: bool | None = None
    valve_uses_open_percent: bool = False
    leak: bool | None = None
    temperature: float | None = None
    humidity: float | None = None
    battery: float | None = None
    low_battery: bool | None = None
    fault: str | None = None
    water_guard_mode: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class AbraData:
    """Everything the coordinator knows about one home."""

    devices: dict[str, AbraDevice]
    alarms: list[AbraAlarm]

    @property
    def water_alarm(self) -> bool:
        return any(a.active for a in self.alarms if a.kind == "WaterAlarm")


_VALVE_TYPES = {"WATER_VALVE"}
_WATER_SENSOR_TYPES = {"WATER_LEAK_DETECTOR", "WATER_SENSOR_TAPE"}


def _attributes(obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map attribute typename -> first attribute of that type across all traits."""
    result: dict[str, dict[str, Any]] = {}
    for trait in obj.get("traits") or []:
        for attr in (trait or {}).get("attributes") or []:
            if attr and attr.get("__typename"):
                known = result.get(attr["__typename"])
                # Keep the first attribute with data; a bare {"__typename"}
                # (fields not queried) is replaced by a later one with values.
                if known is None or len(known) == 1:
                    result[attr["__typename"]] = attr
    return result


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def parse_device(data: dict[str, Any], hub_id: str | None = None, hub_room: str | None = None) -> AbraDevice:
    """Turn a GraphQL Device or Hub object into an :class:`AbraDevice`."""
    attrs = _attributes(data)
    is_hub = "waterGuard" in data
    device_type = data.get("deviceType")

    if is_hub:
        kind = "hub"
    elif device_type in _VALVE_TYPES:
        kind = "valve"
    elif device_type in _WATER_SENSOR_TYPES:
        kind = "water_sensor"
    else:
        kind = "other"

    alarm = attrs.get("TraitAttributeAlarm")
    # The schema types fault as a list of statuses; accept a single object too.
    faults = (attrs.get("TraitAttributeFault") or {}).get("fault") or []
    if isinstance(faults, dict):
        faults = [faults]
    fault_text = ", ".join(
        str(f.get("name") or f.get("code") or f.get("description")) for f in faults if isinstance(f, dict) and any(f.values())
    ) or None

    commands = {c for trait in data.get("traits") or [] for c in (trait or {}).get("commands") or []}
    valve_open = None
    if kind == "valve":
        # Abra models an open valve as "unlocked" on some valves and as an open
        # percentage on others (Waterguard+). Only read these on real valves so
        # door locks are never exposed as water valves.
        unlocked = (attrs.get("TraitAttributeIsUnlocked") or {}).get("isUnlocked")
        percent = _num((attrs.get("TraitAttributeOpenPercent") or {}).get("openPercent"))
        valve_open = unlocked if unlocked is not None else (percent > 0 if percent is not None else None)

    power_source = (attrs.get("TraitAttributeCurrentPowerSource") or {}).get("currentPowerSource")
    battery = _num((attrs.get("TraitAttributeCurrentPowerSourceLevel") or {}).get("currentPowerSourceLevel"))
    if is_hub or power_source == "CONSTANT_POWER":
        # Mains powered: the level describes a backup battery at best (the
        # Linkbox reports 0 with no battery fitted); faults cover that case.
        battery = None
    connection = attrs.get("TraitAttributeIsConnected") or {}

    area = data.get("area") or {}
    return AbraDevice(
        id=str(data["id"]),
        name=data.get("name") or ("Linkbox" if is_hub else str(device_type or data["id"]).replace("_", " ").title()),
        kind=kind,
        device_type=data.get("productType") if is_hub else device_type,
        serial=data.get("serialNumber"),
        firmware=data.get("firmwareVersion"),
        room=area.get("areaName") or hub_room,
        via_hub=hub_id,
        online=connection.get("isConnected"),
        last_reported=connection.get("reportedAt"),
        valve_open=valve_open,
        valve_uses_open_percent=kind == "valve" and "OPEN_PERCENT" in commands,
        leak=(alarm.get("alarm") == "WATER_LEAK") if alarm and kind == "water_sensor" else None,
        temperature=_num((attrs.get("TraitAttributeTemperature") or {}).get("temperature")),
        humidity=_num((attrs.get("TraitAttributeHumidity") or {}).get("humidity")),
        battery=battery,
        low_battery=(attrs.get("TraitAttributeLowBatteryWarning") or {}).get("lowBatteryWarning"),
        fault=fault_text,
        water_guard_mode=(data.get("waterGuard") or {}).get("mode"),
        raw=data,
    )


def parse_home(home: dict[str, Any]) -> dict[str, AbraDevice]:
    """Flatten hubs and their devices for one home."""
    devices: dict[str, AbraDevice] = {}
    for hub in home.get("hubs") or []:
        if not hub or not hub.get("id"):
            continue
        hub_dev = parse_device(hub)
        devices[hub_dev.id] = hub_dev
        for dev in hub.get("devices") or []:
            if dev and dev.get("id"):
                parsed = parse_device(dev, hub_id=hub_dev.id, hub_room=hub_dev.room)
                devices[parsed.id] = parsed
    return devices


class AbraClient:
    """Minimal Abralife API client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        region: str,
        user_pool_id: str,
        client_id: str,
        api_url: str,
        refresh_token: str | None = None,
    ) -> None:
        self._session = session
        self._region = region
        self._user_pool_id = user_pool_id
        self._client_id = client_id
        self._api_url = api_url
        self._tokens: AbraTokens | None = None
        self._refresh_token = refresh_token
        self._lock = asyncio.Lock()
        # Abra's own example app authorises AppSync with the ID token.
        self._use_id_token = True
        # GraphQL errors returned alongside data by the most recent request
        self.last_errors: list[dict[str, Any]] = []
        # GraphQL errors from the latest poll (homes + alarms)
        self.poll_errors: list[dict[str, Any]] = []

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    # ------------------------------------------------------------------ auth
    async def login(self, username: str, password: str) -> AbraTokens:
        """Sign in with e-mail/password using Cognito SRP.

        The password is only used here and is never stored.
        """
        loop = asyncio.get_running_loop()
        tokens = await loop.run_in_executor(None, self._srp_login, username, password)
        self._tokens = tokens
        self._refresh_token = tokens.refresh_token
        return tokens

    def _srp_login(self, username: str, password: str) -> AbraTokens:
        # Imported lazily: pycognito pulls in boto3 which is slow to import.
        from botocore.exceptions import BotoCoreError, ClientError
        from pycognito import Cognito
        from pycognito.exceptions import (
            ForceChangePasswordException,
            MFAChallengeException,
        )

        user = Cognito(
            self._user_pool_id,
            self._client_id,
            username=username,
            user_pool_region=self._region,
        )
        try:
            user.authenticate(password=password)
        except (MFAChallengeException, ForceChangePasswordException) as err:
            raise AbraMfaRequired(str(err)) from err
        except ClientError as err:
            code = err.response.get("Error", {}).get("Code", "")
            if code in ("NotAuthorizedException", "UserNotFoundException"):
                raise AbraAuthError(code) from err
            raise AbraConnectionError(code or str(err)) from err
        except BotoCoreError as err:
            raise AbraConnectionError(str(err)) from err

        return AbraTokens(
            access_token=user.access_token,
            id_token=user.id_token,
            refresh_token=user.refresh_token,
            expires_at=time.time() + 3600,
        )

    async def _refresh(self) -> AbraTokens:
        if not self._refresh_token:
            raise AbraAuthError("No refresh token")
        body = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": self._client_id,
            "AuthParameters": {"REFRESH_TOKEN": self._refresh_token},
        }
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": _COGNITO_TARGET,
        }
        url = f"https://cognito-idp.{self._region}.amazonaws.com/"
        try:
            async with self._session.post(
                url, data=json.dumps(body), headers=headers, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                payload = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise AbraConnectionError(f"Token refresh failed: {err}") from err

        if resp.status != 200:
            err_type = str(payload.get("__type", ""))
            if "NotAuthorized" in err_type or resp.status in (400, 401):
                raise AbraAuthError(payload.get("message", err_type))
            raise AbraConnectionError(f"Token refresh HTTP {resp.status}")

        result = payload["AuthenticationResult"]
        self._tokens = AbraTokens(
            access_token=result["AccessToken"],
            id_token=result["IdToken"],
            # Cognito only returns a new refresh token when rotation is enabled
            refresh_token=result.get("RefreshToken", self._refresh_token),
            expires_at=time.time() + int(result.get("ExpiresIn", 3600)),
        )
        self._refresh_token = self._tokens.refresh_token
        return self._tokens

    async def _valid_tokens(self) -> AbraTokens:
        async with self._lock:
            if self._tokens is None or self._tokens.expired:
                await self._refresh()
            assert self._tokens is not None
            return self._tokens

    # --------------------------------------------------------------- graphql
    async def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run a GraphQL document and return ``data``."""
        tokens = await self._valid_tokens()
        for attempt in range(2):
            jwt = tokens.id_token if self._use_id_token else tokens.access_token
            try:
                async with self._session.post(
                    self._api_url,
                    json={"query": query, "variables": variables or {}},
                    headers={"Authorization": jwt},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    status = resp.status
                    payload = await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                raise AbraConnectionError(str(err)) from err

            if status == 401 and attempt == 0:
                # Fall back to the other Cognito token type once.
                self._use_id_token = not self._use_id_token
                continue
            break

        if status == 401:
            raise AbraAuthError("API rejected token")
        if status != 200 or not isinstance(payload, dict):
            raise AbraConnectionError(f"GraphQL HTTP {status}")
        if payload.get("errors") and not payload.get("data"):
            messages = "; ".join(str(e.get("message")) for e in payload["errors"])
            if "Unauthorized" in messages:
                raise AbraAuthError(messages)
            raise AbraConnectionError(messages)
        self.last_errors = payload.get("errors") or []
        if self.last_errors:
            # Abra nulls fields it can't resolve; those states then show as unknown
            _LOGGER.warning(
                "Abralife returned partial data: %s",
                "; ".join(str(e.get("message")) for e in self.last_errors[:5]),
            )
        return payload.get("data") or {}

    # ------------------------------------------------------------ high level
    async def get_homes(self) -> list[AbraHome]:
        data = await self.graphql(queries.HOME_IDS_QUERY)
        return [
            AbraHome(id=str(h["id"]), name=(h.get("homeInfo") or {}).get("nickname") or str(h["id"]))
            for h in data.get("homes") or []
        ]

    async def get_data(self, home_id: str) -> AbraData:
        """Fetch all hubs, devices and alarms for one home."""
        data = await self.graphql(queries.HOMES_QUERY)
        errors = list(self.last_errors)
        home = next((h for h in data.get("homes") or [] if str(h.get("id")) == home_id), None)
        if home is None:
            raise AbraConnectionError(f"Home {home_id} is no longer available on this account")
        _merge_extras(home, await self._extras(home_id))
        errors += self.last_errors
        alarms_data = await self.graphql(queries.ALARMS_QUERY, {"homeId": home_id})
        self.poll_errors = errors + self.last_errors
        alarms = [
            AbraAlarm(id=str(a["id"]), kind=a["__typename"], state=a.get("state") or "", triggered_at=a.get("triggeredAt"))
            for a in ((alarms_data.get("alarms") or {}).get("alarms") or [])
            if a and a.get("id")
        ]
        return AbraData(devices=parse_home(home), alarms=alarms)

    async def _extras(self, home_id: str) -> dict[str, list[dict[str, Any]]]:
        """Device id -> extra attributes (valve position, power source)."""
        try:
            data = await self.graphql(queries.EXTRAS_QUERY)
        except AbraAuthError:
            raise
        except AbraError as err:
            _LOGGER.warning("Could not read valve position/power source: %s", err)
            return {}
        extras: dict[str, list[dict[str, Any]]] = {}
        for home in data.get("homes") or []:
            if not home or str(home.get("id")) != home_id:
                continue
            for hub in home.get("hubs") or []:
                for dev in (hub or {}).get("devices") or []:
                    if not dev or not dev.get("id"):
                        continue
                    attrs = [
                        a
                        for trait in dev.get("traits") or []
                        for a in (trait or {}).get("attributes") or []
                        if a and len(a) > 1  # skip bare {"__typename": ...}
                    ]
                    if attrs:
                        extras[str(dev["id"])] = attrs
        return extras

    async def diagnostics_dump(self, home_id: str) -> dict[str, Any]:
        """Every trait attribute Abra reports for the home, plus any API errors."""
        try:
            data = await self.graphql(queries.DIAGNOSTICS_QUERY)
        except AbraError as err:
            return {"error": f"{type(err).__name__}: {err}"}
        homes = [h for h in data.get("homes") or [] if h and str(h.get("id")) == home_id]
        return {"home": homes[0] if homes else None, "errors": self.last_errors}

    async def set_valve(self, device_id: str, open_: bool, *, use_open_percent: bool = False) -> None:
        if use_open_percent:
            data = await self.graphql(
                queries.SET_OPEN_PERCENT_MUTATION, {"deviceId": device_id, "percent": 100.0 if open_ else 0.0}
            )
            _raise_payload_errors(data.get("deviceSetOpenPercent"))
        else:
            data = await self.graphql(queries.SET_VALVE_MUTATION, {"deviceId": device_id, "open": open_})
            _raise_payload_errors(data.get("deviceSetUnlocked"))

    async def resolve_alarm(self, alarm_id: str) -> None:
        data = await self.graphql(queries.ALARM_RESOLVE_MUTATION, {"alarmId": alarm_id})
        _raise_payload_errors(data.get("alarmResolve"))


def _merge_extras(home: dict[str, Any], extras: dict[str, list[dict[str, Any]]]) -> None:
    """Attach extra attributes to the matching devices as their own trait."""
    for hub in home.get("hubs") or []:
        for dev in (hub or {}).get("devices") or []:
            if dev and str(dev.get("id")) in extras:
                dev["traits"] = [
                    *(dev.get("traits") or []),
                    {"traitType": "EXTRA", "commands": [], "attributes": extras[str(dev["id"])]},
                ]


def _raise_payload_errors(payload: dict[str, Any] | None) -> None:
    """Abra mutations report business errors in an ``errors`` list."""
    if payload is None:
        raise AbraConnectionError("Empty response from Abralife")
    errors = [e for e in payload.get("errors") or [] if e]
    if errors:
        raise AbraError("; ".join(e.get("message") or e.get("__typename", "error") for e in errors))
