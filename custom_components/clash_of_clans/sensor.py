"""Player, followed-clan, and current-war sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ClashOfClansConfigEntry
from .const import DOMAIN
from .coordinator import ClashOfClansCoordinator


def value_at(data: dict[str, Any], section: str, key: str) -> Any:
    return (data.get(section) or {}).get(key)


def league(data: dict[str, Any]) -> str | None:
    player = data.get("player") or {}
    tier = player.get("leagueTier") or player.get("league") or {}
    return tier.get("name") if isinstance(tier, dict) else None


def war_stat(data: dict[str, Any], side: str, key: str) -> int | None:
    war = data.get("war") or {}
    if war.get("state") in (None, "notInWar"):
        return None
    return (war.get(side) or {}).get(key)


def war_end(data: dict[str, Any]) -> datetime | None:
    war = data.get("war") or {}
    if war.get("state") in (None, "notInWar") or not war.get("endTime"):
        return None
    try:
        return datetime.strptime(war["endTime"], "%Y%m%dT%H%M%S.%f%z")
    except ValueError, TypeError:
        return None


@dataclass(frozen=True, kw_only=True)
class ClashOfClansSensorDescription(SensorEntityDescription):
    """One value getter per stable metric."""

    value_fn: Callable[[dict[str, Any]], Any]


def numeric(
    key: str, name: str, section: str, field: str
) -> ClashOfClansSensorDescription:
    return ClashOfClansSensorDescription(
        key=key,
        name=name,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: value_at(data, section, field),
    )


SENSORS = (
    numeric("trophies", "Trophies", "player", "trophies"),
    numeric("best_trophies", "Best trophies", "player", "bestTrophies"),
    numeric("town_hall_level", "Town hall level", "player", "townHallLevel"),
    numeric("exp_level", "XP level", "player", "expLevel"),
    numeric("war_stars", "War stars", "player", "warStars"),
    numeric("donations", "Donations", "player", "donations"),
    numeric("donations_received", "Donations received", "player", "donationsReceived"),
    numeric("attack_wins", "Attack wins", "player", "attackWins"),
    numeric("defense_wins", "Defense wins", "player", "defenseWins"),
    numeric(
        "builder_base_trophies", "Builder trophies", "player", "builderBaseTrophies"
    ),
    numeric(
        "clan_capital_contributions",
        "Capital contributions",
        "player",
        "clanCapitalContributions",
    ),
    ClashOfClansSensorDescription(key="league", name="League", value_fn=league),
    numeric("clan_members", "Clan members", "clan", "members"),
    numeric("clan_level", "Clan level", "clan", "clanLevel"),
    numeric("clan_points", "Clan points", "clan", "clanPoints"),
    ClashOfClansSensorDescription(
        key="war_state",
        name="War state",
        value_fn=lambda data: value_at(data, "war", "state"),
    ),
    ClashOfClansSensorDescription(
        key="current_war_stars",
        name="Current war stars",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: war_stat(data, "clan", "stars"),
    ),
    ClashOfClansSensorDescription(
        key="opponent_stars",
        name="Opponent stars",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: war_stat(data, "opponent", "stars"),
    ),
    ClashOfClansSensorDescription(
        key="used_attacks",
        name="Used attacks",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: war_stat(data, "clan", "attacks"),
    ),
    ClashOfClansSensorDescription(
        key="war_end",
        name="War end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=war_end,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ClashOfClansConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose all metrics, including unavailable optional fields."""
    async_add_entities(
        ClashOfClansSensor(entry.runtime_data, description) for description in SENSORS
    )


class ClashOfClansSensor(CoordinatorEntity[ClashOfClansCoordinator], SensorEntity):
    """Stable player-scoped identity, even when the player changes clans."""

    _attr_has_entity_name = True
    entity_description: ClashOfClansSensorDescription

    def __init__(
        self,
        coordinator: ClashOfClansCoordinator,
        description: ClashOfClansSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.player_tag}_{description.key}"

    @property
    def suggested_object_id(self) -> str:
        """Core prepends the service-branded device name to this local suffix."""
        return self.entity_description.key

    @property
    def device_info(self) -> DeviceInfo:
        player = (self.coordinator.data or {}).get("player") or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.player_tag)},
            name=f"Clash of Clans {player.get('name', self.coordinator.player_tag)}",
            manufacturer="Supercell",
            model="Clash of Clans player",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None
