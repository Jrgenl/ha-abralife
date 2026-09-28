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
class AbraDevice:
    """Normalised view of an Abralife device."""

    id: str
    name: str
    kind: str  # "valve", "water_sensor", "hub" or "other"
    model: str | None = None
    room: str | None = None
    online: bool | None = None
    valve_open: bool | None = None
    leak: bool | None = None
    temperature: float | None = None
    humidity: float | None = None
    battery: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _first(data: dict[str, Any], *keys: str) -> Any:
    """Return the first non-None value for any of ``keys``."""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _as_bool(value: Any, true_words: tuple[str, ...]) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in true_words


def _as_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def parse_device(data: dict[str, Any]) -> AbraDevice:
    """Turn a GraphQL device object into an :class:`AbraDevice`."""
    state = data.get("state") or {}
    if isinstance(state, str):  # AWSJSON scalars arrive as strings
        try:
            state = json.loads(state)
        except ValueError:
            state = {"value": state}
    if not isinstance(state, dict):
        state = {"value": state}
    merged = {**state, **{k: v for k, v in data.items() if k != "state"}}

    dev_type = str(_first(merged, "type", "deviceType", "category") or "").lower()
    model = _first(merged, "model", "productName", "product")

    valve_raw = _first(merged, "valveOpen", "isOpen", "open", "valveState", "valve")
    valve_open = _as_bool(valve_raw, ("open", "opened", "on", "true", "1"))

    leak = _as_bool(
        _first(merged, "leak", "leakDetected", "waterDetected", "water", "alarm", "wet"),
        ("true", "1", "wet", "leak", "alarm", "detected", "on"),
    )

    if "valve" in dev_type or valve_raw is not None:
        kind = "valve"
    elif any(word in dev_type for word in ("water", "leak", "moisture", "sensor")) or leak is not None:
        kind = "water_sensor"
    elif any(word in dev_type for word in ("linkbox", "hub", "gateway", "adapter")):
        kind = "hub"
    else:
        kind = "other"

    room = merged.get("room")
    if isinstance(room, dict):
        room = room.get("name")

    online_raw = _first(merged, "online", "connected", "isOnline", "reachable")
    return AbraDevice(
        id=str(merged["id"]),
        name=str(_first(merged, "name", "label") or model or merged["id"]),
        kind=kind,
        model=str(model) if model else None,
        room=room,
        online=_as_bool(online_raw, ("true", "1", "online", "connected")),
        valve_open=valve_open,
        leak=leak,
        temperature=_as_float(_first(merged, "temperature", "temp")),
        humidity=_as_float(_first(merged, "humidity", "relativeHumidity")),
        battery=_as_float(_first(merged, "battery", "batteryLevel", "batteryPercent")),
        raw=data,
    )


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
        self._use_id_token = False

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
                # AppSync may be configured for ID tokens instead of access tokens.
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
        if payload.get("errors"):
            _LOGGER.debug("Partial GraphQL errors: %s", payload["errors"])
        return payload.get("data") or {}

    # ------------------------------------------------------------ high level
    async def get_homes(self) -> list[AbraHome]:
        data = await self.graphql(queries.HOMES_QUERY)
        return [AbraHome(id=str(h["id"]), name=h.get("name") or str(h["id"])) for h in data.get("homes") or []]

    async def get_devices(self, home_id: str) -> dict[str, AbraDevice]:
        data = await self.graphql(queries.DEVICES_QUERY, {"homeId": home_id})
        home = data.get("home") or {}
        devices = [parse_device(d) for d in home.get("devices") or [] if d and d.get("id")]
        return {d.id: d for d in devices}

    async def set_valve(self, device_id: str, open_: bool) -> None:
        await self.graphql(queries.SET_VALVE_MUTATION, {"deviceId": device_id, "open": open_})

    async def introspect(self) -> dict[str, Any]:
        return await self.graphql(queries.INTROSPECTION_QUERY)
