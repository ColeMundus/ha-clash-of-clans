"""Actual HA setup, entity registry, lifecycle and followed-clan states."""

from copy import deepcopy
from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

DOMAIN = "clash_of_clans"
INPUT = {"api_key": "synthetic-key", "player_tag": "#P0Y", "scan_interval": 5}
PREFIX = "sensor.clash_of_clans_synthetic_player_"


async def setup(hass, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="#P0Y", data=INPUT, options=options or {}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_meaningful_player_clan_war_states(hass, provider):
    entry = await setup(hass)
    expected = {
        "trophies": "5100",
        "best_trophies": "5300",
        "town_hall_level": "16",
        "exp_level": "200",
        "war_stars": "123",
        "donations": "40",
        "donations_received": "30",
        "attack_wins": "7",
        "defense_wins": "2",
        "builder_base_trophies": "2900",
        "league": "Synthetic League",
        "clan_members": "35",
        "clan_level": "12",
        "clan_points": "30000",
        "war_state": "inWar",
        "current_war_stars": "20",
        "opponent_stars": "18",
        "used_attacks": "10",
        "war_end": "2026-11-06T00:00:00+00:00",
        "clan_capital_contributions": "unavailable",
    }
    states = {s.entity_id: s for s in hass.states.async_all("sensor")}
    assert set(states) == {PREFIX + key for key in expected}
    assert {key: states[PREFIX + key].state for key in expected} == expected
    assert (
        states[PREFIX + "trophies"].attributes["friendly_name"]
        == "Clash of Clans Synthetic Player Trophies"
    )
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 20
    assert {entity.unique_id for entity in entities} == {
        f"#P0Y_{key}" for key in expected
    }
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, "#P0Y"), entry.entry_id
    )
    assert device.name == "Clash of Clans Synthetic Player"
    assert len(provider.requests) == 3


@pytest.mark.parametrize(
    "key, icon",
    {
        "trophies": "mdi:trophy",
        "best_trophies": "mdi:trophy-award",
        "town_hall_level": "mdi:castle",
        "exp_level": "mdi:star-circle",
        "war_stars": "mdi:star",
        "donations": "mdi:hand-heart",
        "donations_received": "mdi:gift",
        "attack_wins": "mdi:sword",
        "defense_wins": "mdi:shield-check",
        "builder_base_trophies": "mdi:hammer",
        "clan_capital_contributions": "mdi:bank-transfer-out",
        "league": "mdi:medal",
        "clan_members": "mdi:account-group",
        "clan_level": "mdi:shield-star",
        "clan_points": "mdi:counter",
        "war_state": "mdi:sword-cross",
        "current_war_stars": "mdi:star-check",
        "opponent_stars": "mdi:star-outline",
        "used_attacks": "mdi:target",
        "war_end": "mdi:timer-sand",
    }.items(),
)
async def test_metric_icons_in_actual_ha_states(hass, provider, key, icon):
    await setup(hass)
    assert hass.states.get(PREFIX + key).attributes.get("icon") == icon


async def test_no_clan_player_still_available(hass, provider, player):
    player.pop("clan")
    provider.set("/v1/players/#P0Y", body=player)
    await setup(hass)
    assert hass.states.get(PREFIX + "trophies").state == "5100"
    for key in [
        "clan_members",
        "clan_level",
        "clan_points",
        "war_state",
        "war_end",
        "current_war_stars",
    ]:
        assert hass.states.get(PREFIX + key).state == "unavailable"
    assert [path for path, _ in provider.requests] == ["/v1/players/#P0Y"]


async def test_private_war_keeps_player_and_clan(hass, provider):
    provider.set("/v1/clans/#Q0G/currentwar", 403, {"reason": "accessDenied"})
    await setup(hass)
    assert hass.states.get(PREFIX + "trophies").state == "5100"
    assert hass.states.get(PREFIX + "clan_members").state == "35"
    assert hass.states.get(PREFIX + "war_state").state == "unavailable"
    assert hass.states.get(PREFIX + "current_war_stars").state == "unavailable"


@pytest.mark.parametrize(
    "body", [{"state": "notInWar"}, {"state": "inWar", "endTime": "invalid"}]
)
async def test_optional_war_metrics_not_fabricated(hass, provider, body):
    provider.set("/v1/clans/#Q0G/currentwar", body=body)
    await setup(hass)
    assert hass.states.get(PREFIX + "current_war_stars").state == "unavailable"
    assert hass.states.get(PREFIX + "war_end").state == "unavailable"


async def test_follow_changed_clan_and_stable_ids(hass, provider, player, clan, war):
    entry = await setup(hass)
    registry = er.async_get(hass)
    original = {
        e.entity_id: e.unique_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    player["clan"] = {"tag": "#R0J", "name": "New Synthetic Clan"}
    clan = {**clan, "tag": "#R0J", "name": "New Synthetic Clan", "members": 21}
    war = deepcopy(war)
    war["clan"]["tag"] = "#R0J"
    provider.set("/v1/players/#P0Y", body=player)
    provider.set("/v1/clans/#R0J", body=clan)
    provider.set("/v1/clans/#R0J/currentwar", body=war)
    # Advance the native scheduler and monotonic provider budget together.
    import time
    from unittest.mock import patch

    with patch(
        "custom_components.clash_of_clans.coordinator.time.monotonic",
        return_value=time.monotonic() + 301,
    ):
        await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(PREFIX + "clan_members").state == "21"
    assert {
        e.entity_id: e.unique_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    } == original
    assert [p for p, _ in provider.requests[-3:]] == [
        "/v1/players/#P0Y",
        "/v1/clans/#R0J",
        "/v1/clans/#R0J/currentwar",
    ]


async def test_reload_and_unload_preserve_custom_entity(hass, provider):
    entry = await setup(hass)
    old = entry.runtime_data
    registry = er.async_get(hass)
    original = registry.async_get(PREFIX + "trophies")
    registry.async_update_entity(
        original.entity_id,
        new_entity_id="sensor.custom_game_score",
        name="My custom score",
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert old.retired and old.client.retired
    assert entry.runtime_data is not old
    assert hass.states.get("sensor.custom_game_score").state == "5100"
    assert (
        hass.states.get("sensor.custom_game_score").attributes["friendly_name"]
        == "Clash of Clans Synthetic Player My custom score"
    )
    preserved = registry.async_get("sensor.custom_game_score")
    assert preserved.unique_id == original.unique_id
    assert preserved.id == original.id
    assert len(provider.requests) == 3  # Reload cannot bypass polling budget.
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get("sensor.custom_game_score").state == "unavailable"


async def test_manual_refresh_cannot_bypass_poll_floor(hass, provider):
    entry = await setup(hass)
    for _ in range(3):
        await entry.runtime_data.async_refresh()
    assert len(provider.requests) == 3
    assert entry.runtime_data.update_interval == timedelta(minutes=5)


async def test_options_reload_real_entry(hass, provider):
    entry = await setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 10}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval == timedelta(minutes=10)
    assert entry.data == INPUT
    assert len(provider.requests) == 3


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ConfigEntryState.SETUP_ERROR),
        (500, ConfigEntryState.SETUP_RETRY),
        (429, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_provider_failures(hass, provider, status, expected):
    provider.set("/v1/players/#P0Y", status, {}, {"Retry-After": "1e308"})
    entry = MockConfigEntry(domain=DOMAIN, unique_id="#P0Y", data=INPUT)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is expected
    assert entry.data == INPUT
    assert len(provider.requests) == 1


@pytest.mark.parametrize("minutes, expected_delay", [(10, 600), (1, 300)])
async def test_options_reload_preserves_or_extends_deadline(
    hass, provider, freezer, minutes, expected_delay
):
    entry = await setup(hass)
    started = entry.runtime_data.gate.last_attempt
    freezer.tick(timedelta(seconds=30))
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": minutes}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data.gate.next_poll == started + expected_delay
    freezer.tick(timedelta(seconds=expected_delay - 30 - 0.01))
    await entry.runtime_data.async_refresh()
    assert len(provider.requests) == 3
    freezer.tick(timedelta(seconds=0.01))
    await entry.runtime_data.async_refresh()
    assert len(provider.requests) == 6


async def test_native_scheduler_refreshes_at_interval(hass, provider, freezer):
    entry = await setup(hass, {"scan_interval": 1})
    freezer.tick(timedelta(seconds=59))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert len(provider.requests) == 3
    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(provider.requests) == 6
    assert entry.runtime_data.last_update_success


async def test_unload_discards_inflight_response_and_keeps_budget(
    hass, provider, freezer
):
    import asyncio

    entry = await setup(hass)
    old = entry.runtime_data
    started = asyncio.Event()
    release = asyncio.Event()

    async def block_player(request):
        if request.path == "/v1/players/#P0Y":
            started.set()
            await release.wait()

    provider.before_response = block_player
    freezer.tick(timedelta(seconds=301))
    refresh = asyncio.create_task(old.async_refresh())
    try:
        await asyncio.wait_for(started.wait(), 2)
        assert await hass.config_entries.async_unload(entry.entry_id)
        release.set()
        await refresh
        assert old.retired and old.client.retired
        assert old.gate.snapshot is None
        assert len(provider.requests) == 4
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert len(provider.requests) == 4
    finally:
        release.set()
        if not refresh.done():
            refresh.cancel()
        await asyncio.gather(refresh, return_exceptions=True)
