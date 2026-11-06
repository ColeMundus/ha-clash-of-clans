<img src="https://raw.githubusercontent.com/ColeMundus/ha-clash-of-clans/main/custom_components/clash_of_clans/brand/icon.png" alt="Clash of Clans" width="96">

# Clash of Clans for Home Assistant

[![CI: workflow](docs/badges/ci.svg)](https://github.com/ColeMundus/ha-clash-of-clans/actions/workflows/ci.yml)
[![HA tested: 2026.11.0](docs/badges/compatibility.svg)](https://github.com/ColeMundus/ha-clash-of-clans/actions/workflows/ci.yml)
[![License: MIT](docs/badges/license.svg)](LICENSE)
[![Distribution: HACS custom](docs/badges/distribution.svg)](#installation)

Player, clan and public clan-war sensors using Supercell's API. Enter a player tag once; the integration follows that player's current clan automatically.

## Installation

Requires **Home Assistant Core 2026.11.0 or newer**.

1. Open **Settings → Marketplace → Add from link** and enter `https://github.com/ColeMundus/ha-clash-of-clans`. Connect GitHub if prompted.
2. Open **Clash of Clans** and choose **Install**. No pre-release setting is needed.
3. Install and restart Home Assistant when prompted.
4. Open **Settings → Devices & services → Add integration → Clash of Clans**.

Until catalog inclusion, add this repository as a custom integration in HACS/Marketplace.

**Manual install:** Download the [release ZIP](https://github.com/ColeMundus/ha-clash-of-clans/releases/download/v0.1.0/clash_of_clans-0.1.0.zip), extract it into your Home Assistant configuration directory, and restart.

## Create an API key

1. Sign in at the [Clash of Clans developer portal](https://developer.clashofclans.com/).
2. Open **My Account → Create New Key** and enter a name and description.
3. Under **Allowed IP addresses**, enter the public IP address of the network running Home Assistant.
4. Create the key, then paste its **Token** into the integration's **API key** field and enter your in-game **Player tag**.

Polling defaults to five minutes and can be changed from 1–60 minutes through **Configure**. Add another entry to monitor another player.

![Clash of Clans setup in Home Assistant](docs/images/setup.png)

## Sensors

| Group | Sensors |
| --- | --- |
| Player | Trophies, best trophies, Town Hall level, XP level, war stars, donations, donations received, attack and defense wins, Builder Base trophies, Clan Capital contributions, league |
| Current clan | Members, level, clan points |
| Current war | State, clan stars, opponent stars, attacks used, end time |

## Limitations

- The API does not provide resource balances, builder availability, training queues or upgrade timers.
- War details require a public war log. Private logs leave war sensors unavailable; player and clan sensors still work. Clan War League rounds and raid-weekend details are not included.

Clash of Clans artwork belongs to Supercell; see [NOTICE.md](NOTICE.md). This material is unofficial and is not endorsed by Supercell. See Supercell's [Fan Content Policy](https://supercell.com/en/fan-content-policy/).
