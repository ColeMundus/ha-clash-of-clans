"""Official HA harness bootstrap and synthetic loopback provider."""

from copy import deepcopy
from pathlib import Path

import pytest
import pytest_socket
from aiohttp import web
from aiohttp.test_utils import TestServer

import custom_components

# The official harness ships a regular custom_components test package, which
# otherwise shadows this checkout's namespace package during HA discovery.
_COMPONENTS = str(Path(__file__).resolve().parents[1] / "custom_components")
if _COMPONENTS not in custom_components.__path__:
    custom_components.__path__.append(_COMPONENTS)

PLAYER = {
    "tag": "#P0Y",
    "name": "Synthetic Player",
    "townHallLevel": 16,
    "expLevel": 200,
    "trophies": 5100,
    "bestTrophies": 5300,
    "warStars": 123,
    "attackWins": 7,
    "defenseWins": 2,
    "donations": 40,
    "donationsReceived": 30,
    "builderHallLevel": 10,
    "builderBaseTrophies": 2900,
    "role": "member",
    "leagueTier": {"id": 29000022, "name": "Synthetic League"},
    "clan": {"tag": "#Q0G", "name": "Synthetic Clan"},
}
CLAN = {
    "tag": "#Q0G",
    "name": "Synthetic Clan",
    "clanLevel": 12,
    "members": 35,
    "clanPoints": 30000,
    "warWins": 100,
    "warWinStreak": 2,
    "warLeague": {"name": "Synthetic War League"},
}
WAR = {
    "state": "inWar",
    "teamSize": 15,
    "attacksPerMember": 2,
    "startTime": "20261105T000000.000Z",
    "endTime": "20261106T000000.000Z",
    "clan": {"tag": "#Q0G", "stars": 20, "attacks": 10, "destructionPercentage": 40.5},
    "opponent": {"tag": "#R0J", "name": "Synthetic Opponent", "stars": 18},
}


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup():
    """Permit only local provider sockets; never unrestricted Internet."""
    pytest_socket.enable_socket()
    pytest_socket.socket_allow_hosts(["127.0.0.1", "::1"], allow_unix_socket=True)


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Discover real checked-out integration through the official HA loader."""


@pytest.fixture
def player():
    return deepcopy(PLAYER)


@pytest.fixture
def clan():
    return deepcopy(CLAN)


@pytest.fixture
def war():
    return deepcopy(WAR)


@pytest.fixture
async def provider(monkeypatch, player, clan, war):
    """Use real aiohttp HTTP parsing, sessions, errors and response teardown."""
    pytest_socket.enable_socket()
    pytest_socket.socket_allow_hosts(["127.0.0.1", "::1"], allow_unix_socket=True)
    from custom_components.clash_of_clans import api

    class Provider:
        responses = {
            "/v1/players/#P0Y": (200, player, {}),
            "/v1/clans/#Q0G": (200, clan, {}),
            "/v1/clans/#Q0G/currentwar": (200, war, {}),
        }

        def __init__(self):
            self.requests = []
            self.responses = deepcopy(self.responses)

        def set(self, path, status=200, body=None, headers=None):
            self.responses[path] = (status, body, headers or {})

        async def handle(self, request):
            self.requests.append((request.path, request.headers.get("Authorization")))
            if callback := getattr(self, "before_response", None):
                await callback(request)
            status, body, headers = self.responses.get(request.path, (404, {}, {}))
            if isinstance(body, str):
                return web.Response(status=status, text=body, headers=headers)
            return web.json_response(body, status=status, headers=headers)

    provider = Provider()
    app = web.Application()
    app.router.add_get("/{path:.*}", provider.handle)
    async with TestServer(app, host="127.0.0.1", access_log=None) as server:
        monkeypatch.setattr(api, "API_BASE", str(server.make_url("/v1")))
        yield provider
