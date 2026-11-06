"""Native HA flow tests; only provider HTTP is replaced."""

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant.common import MockConfigEntry

DOMAIN = "clash_of_clans"
INPUT = {"api_key": "synthetic-key", "player_tag": "#P0Y", "scan_interval": 5}


def entry_for(hass, **kwargs):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="#P0Y", data=INPUT.copy(), **kwargs
    )
    entry.add_to_hass(hass)
    return entry


def fields(result):
    return {str(key): key for key in result["data_schema"].schema}


async def test_setup_required_fields(hass, provider):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert set(fields(result)) == {"api_key", "player_tag", "scan_interval"}
    assert all(type(key).__name__ == "Required" for key in fields(result).values())
    schema = result["data_schema"]
    assert (
        schema({"api_key": "synthetic-key", "player_tag": "P0Y"})["scan_interval"] == 5
    )
    assert schema.schema[fields(result)["api_key"]].config["type"] == "password"
    assert provider.requests == []


@pytest.mark.parametrize("tag", ["p0y", "#p0y", " #P0Y "])
async def test_create_canonical_player(hass, provider, tag):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**INPUT, "player_tag": tag}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == INPUT
    assert result["result"].unique_id == "#P0Y"
    await hass.async_block_till_done()
    assert result["result"].runtime_data.data["clan"]["tag"] == "#Q0G"


async def test_duplicate_before_http(hass, provider):
    entry_for(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={**INPUT, "player_tag": "p0y"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert provider.requests == []


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (401, {}, "invalid_auth"),
        (403, {}, "invalid_auth"),
        (403, {"reason": "accessDenied.invalidIp"}, "ip_not_allowed"),
        (404, {}, "player_not_found"),
        (429, {}, "rate_limited"),
        (500, {}, "cannot_connect"),
        (200, [], "cannot_connect"),
    ],
)
async def test_setup_http_errors(hass, provider, status, body, error):
    provider.set("/v1/players/#P0Y", status, body)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("player_tag", "ABC", "invalid_tag"),
        ("player_tag", "P0Y/war", "invalid_tag"),
        ("scan_interval", 1.5, "invalid_interval"),
        ("scan_interval", True, "invalid_interval"),
        ("scan_interval", 61, "invalid_interval"),
    ],
)
async def test_setup_invalid_input_no_http(hass, provider, field, value, error):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={**INPUT, field: value},
    )
    assert result["errors"] == {field: error}
    assert provider.requests == []


@pytest.mark.parametrize("value", [True, False, "5", 1.5, 0, 61, None])
async def test_setup_native_schema_rejects_invalid_interval(hass, provider, value):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {**INPUT, "scan_interval": value}
        )
    assert not provider.requests
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_interval_selector_renders_native_number(hass, provider):
    import probatio
    from homeassistant.helpers import config_validation as cv

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    serialized = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    interval = next(item for item in serialized if item["name"] == "scan_interval")
    assert interval["selector"]["number"]["unit_of_measurement"] == "min"
    values = result["data_schema"]({**INPUT, "scan_interval": 5.0})
    assert type(values["scan_interval"]) is int


async def test_options_success(hass, provider):
    entry = entry_for(hass, options={"unrelated": "preserved"})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert set(fields(result)) == {"scan_interval"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 10}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"unrelated": "preserved", "scan_interval": 10}
    assert entry.data == INPUT
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "value", [True, False, 0, 61, 1.5, "5", None, float("inf"), float("nan")]
)
async def test_options_strict_validation(hass, provider, value):
    entry = entry_for(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    try:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"scan_interval": value}
        )
    except InvalidData:
        pass  # Native schema rejection is also valid; configuration stays unchanged.
    else:
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"scan_interval": "invalid_interval"}
    assert entry.options == {}
    assert entry.data == INPUT
    assert provider.requests == []


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
async def test_reauth_failure_preserves_original(hass, provider, status):
    entry = entry_for(hass, options={"scan_interval": 10})
    provider.set("/v1/players/#P0Y", status, {"message": "PRIVATE-CANARY"})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert set(fields(result)) == {"api_key"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "replacement-synthetic-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert entry.data == INPUT
    assert entry.options == {"scan_interval": 10}
    assert entry.unique_id == "#P0Y"


async def test_reauth_success(hass, provider):
    entry = entry_for(hass, options={"scan_interval": 10})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "replacement-synthetic-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {**INPUT, "api_key": "replacement-synthetic-key"}
    assert entry.options == {"scan_interval": 10}
    await hass.async_block_till_done()


async def test_reopened_setup_cannot_bypass_extreme_429(hass, provider):
    provider.set("/v1/players/#P0Y", 429, {}, {"Retry-After": "1e308"})
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT
    )
    hass.config_entries.flow.async_abort(first["flow_id"])
    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT
    )
    assert second["errors"] == {"base": "rate_limited"}
    assert len(provider.requests) == 1


@pytest.mark.parametrize("missing", ["api_key", "player_tag"])
async def test_missing_required_field_rejected(hass, provider, missing):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    values = {key: value for key, value in INPUT.items() if key != missing}
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(result["flow_id"], values)
    assert provider.requests == []


async def test_cancelled_reauth_preserves_entry(hass, provider):
    entry = entry_for(hass, options={"scan_interval": 10})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    hass.config_entries.flow.async_abort(result["flow_id"])
    assert entry.data == INPUT
    assert entry.options == {"scan_interval": 10}
    assert provider.requests == []


@pytest.mark.parametrize("tag", ["#Q0G", "invalid", None])
async def test_reauth_wrong_or_malformed_player_preserves_entry(hass, provider, tag):
    entry = entry_for(hass, options={"scan_interval": 10})
    provider.set("/v1/players/#P0Y", body={"tag": tag})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "replacement-synthetic-key"}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == INPUT
    assert entry.options == {"scan_interval": 10}
