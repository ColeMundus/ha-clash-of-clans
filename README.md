<img src="custom_components/clash_of_clans/brand/icon.png" alt="Clash of Clans" width="96">

# Clash of Clans for Home Assistant

[![CI: workflow](docs/badges/ci.svg)](https://github.com/ColeMundus/ha-clash-of-clans/actions/workflows/ci.yml)
[![HA tested: 2026.11.0](docs/badges/compatibility.svg)](https://github.com/ColeMundus/ha-clash-of-clans/actions/workflows/ci.yml)
[![License: MIT](docs/badges/license.svg)](LICENSE)
[![Distribution: private preview](docs/badges/distribution.svg)](#installation)

Read-only player, clan and public clan-war sensors using Supercell's Clash of Clans API. Enter a player tag once; the integration follows that player's current clan automatically.

## Installation

Requires Home Assistant Core **2026.11.0 or newer**. This is a private preview, not a Marketplace or HACS catalog listing.

1. Copy `custom_components/clash_of_clans` into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → Clash of Clans**.

## Create an API key

1. Register or sign in at the [Clash of Clans developer portal](https://developer.clashofclans.com/).
2. Open **My Account** and choose **Create New Key**. Enter a name and description, such as “Home Assistant”.
3. Under **Allowed IP addresses**, enter the public outbound IPv4 address of the network running Home Assistant—not its LAN address, Tailscale address, or your phone's address. You can check the address from that network using a public-IP lookup service. If HA uses a VPN, use its actual outbound address.
4. Create the key and copy the **Token** into the integration's **API key** field. This is the developer token, not the player verification token found in-game.
5. Enter your **Player tag** from your in-game profile and choose the **Polling interval (minutes)**. The default is five minutes; supported values are whole minutes from 1 to 60.

Keep the token private. If your public IP changes, update or recreate the key's allowlist in the developer portal and reauthenticate the integration with the replacement token when needed. An “IP address not allowed” error means the requests are leaving from a different public address than the key permits.

Change polling through the integration's **Configure** option. Add another config entry to monitor another player.

## Sensors

| Group | Information |
| --- | --- |
| Player | Trophies, best trophies, Town Hall level, experience level, war stars, donations, donations received, attack and defense wins, Builder Base trophies, Clan Capital contributions, league |
| Current clan | Member count, level, clan points |
| Current war | State, clan stars, opponent stars, attacks used, end time |

Entities have Clash of Clans branding in their names and IDs. Clan sensors follow the configured player rather than requiring a separate entry for every clan change. Missing provider values are not converted to zero.

## Limits and privacy

- Supercell's public API does **not** expose live gold/elixir balances, builder availability, training queues, or upgrade timers. This integration does not automate gameplay.
- War details require a public war log. A private log makes war sensors unavailable without breaking player and clan sensors. Clan War League rounds and raid-weekend details are not included in this preview.
- Seasonal counters can decrease or reset. They are not treated as lifetime-increasing statistics.
- The developer key is stored in Home Assistant's config-entry storage and may be included in your HA backups. It is sent only to Supercell's API; no developer account password is needed.
- Provider throttling is respected. A manual refresh or reload is not a promise of an immediate new provider request.

## Development

Use Python 3.14 and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python scripts/build_artifact.py
```

Tests use synthetic game data and do not require an API key. Report bugs through [GitHub Issues](https://github.com/ColeMundus/ha-clash-of-clans/issues); do not attach tokens or full HA storage files. See [SECURITY.md](SECURITY.md) for private security reporting and [NOTICE.md](NOTICE.md) for artwork attribution.

This material is unofficial and is not endorsed by Supercell. For more information see Supercell's [Fan Content Policy](https://supercell.com/en/fan-content-policy/).
