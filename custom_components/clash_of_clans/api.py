"""Small, fixed-origin, read-only Clash of Clans API client."""

import asyncio
import hashlib
import math
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import aiohttp
from homeassistant.core import HomeAssistant

from .const import API_BASE, DOMAIN, normalize_tag


class ClashOfClansError(Exception):
    """Sanitized provider failure."""


class InvalidAuth(ClashOfClansError):
    """Invalid developer API key."""


class IPNotAllowed(InvalidAuth):
    """The key does not allow this public IP."""


class NotFound(ClashOfClansError):
    """Player or clan does not exist."""


class RateLimited(ClashOfClansError):
    """Provider cooldown active."""


class Retired(ClashOfClansError):
    """An unloaded runtime may not send requests."""


@dataclass
class RequestGate:
    """HA-lifetime provider cooldown; not stored in config-entry data."""

    retry_until: float = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def request_gate(hass: HomeAssistant, token: str) -> RequestGate:
    """Share backoff across flow cancellation, manual refresh, and reload."""
    gates = hass.data.setdefault(f"{DOMAIN}_request_gates", {})
    fingerprint = hashlib.sha256(token.encode()).digest()
    return gates.setdefault(fingerprint, RequestGate())


def retry_delay(value: str | None) -> float:
    """Parse delta/date Retry-After, saturating before timestamp arithmetic."""
    try:
        delay = float(value or "60")
    except ValueError, OverflowError:
        try:
            delay = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except ValueError, TypeError, OverflowError:
            return 60
    if math.isnan(delay):
        return 60
    return min(86400.0, max(1.0, delay))


class ClashOfClansClient:
    """Use the HA-owned session; never include response bodies in exceptions."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        gate: RequestGate | None = None,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self.gate = gate or RequestGate()
        self.retired = False

    async def _get(
        self, path: str, *, private_war: bool = False
    ) -> dict[str, Any] | None:
        async with self.gate.lock:
            if self.retired:
                raise Retired("Runtime unloaded") from None
            if time.monotonic() < self.gate.retry_until:
                raise RateLimited("Provider cooldown active") from None
            try:
                async with self._session.get(
                    f"{API_BASE}/{path}",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=aiohttp.ClientTimeout(total=20, connect=10),
                    allow_redirects=False,
                ) as response:
                    if response.status == 429:
                        self.gate.retry_until = time.monotonic() + retry_delay(
                            response.headers.get("Retry-After")
                        )
                        raise RateLimited("Provider cooldown active")
                    if response.status == 403 and private_war:
                        return None
                    if response.status in (401, 403):
                        try:
                            reason = (await response.json()).get("reason")
                        except ValueError, aiohttp.ClientError, AttributeError:
                            reason = None
                        if reason == "accessDenied.invalidIp":
                            raise IPNotAllowed("Public IP is not allowed")
                        raise InvalidAuth("API key rejected")
                    if response.status == 404:
                        raise NotFound("Resource not found")
                    if response.status != 200:
                        raise ClashOfClansError("Provider request failed")
                    data = await response.json()
                    if not isinstance(data, dict):
                        raise ClashOfClansError("Invalid provider response")
                    if self.retired:
                        raise Retired("Runtime unloaded")
                    return data
            except ClashOfClansError as err:
                raise type(err)(str(err)) from None
            except TimeoutError, aiohttp.ClientError, ValueError, TypeError:
                raise ClashOfClansError("Unable to communicate with provider") from None

    async def async_get_player(self, tag: str) -> dict[str, Any]:
        data = await self._get(f"players/{quote(normalize_tag(tag), safe='')}")
        try:
            valid = data is not None and normalize_tag(
                data.get("tag", "")
            ) == normalize_tag(tag)
        except ValueError:
            valid = False
        if not valid:
            raise ClashOfClansError("Invalid player response") from None
        assert data is not None
        return data

    async def async_get_clan(self, tag: str) -> dict[str, Any]:
        return await self._get(f"clans/{quote(normalize_tag(tag), safe='')}")

    async def async_get_current_war(self, tag: str) -> dict[str, Any] | None:
        return await self._get(
            f"clans/{quote(normalize_tag(tag), safe='')}/currentwar", private_war=True
        )
