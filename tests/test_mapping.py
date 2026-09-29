from datetime import timedelta

import pytest
from homeassistant.core import State
from homeassistant.util import dt as dt_util

from custom_components.ems_home_assistant.mapping import collect_samples, create_mapping, value_for

ATTRS = {"unit_of_measurement": "W", "device_class": "power", "state_class": "measurement"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", "0"),
        ("unknown", None),
        ("unavailable", None),
        ("NaN", None),
        ("Infinity", None),
        ("-1", None),
        ("0.0000001", None),
        ("123.456", "123.456"),
        ("1000001", None),
    ],
)
def test_numeric_contract(mapping, raw, expected):
    assert value_for(State("sensor.house_power", raw, ATTRS), mapping) == expected


@pytest.mark.parametrize(
    "change", [{"unit_of_measurement": "kW"}, {"device_class": "energy"}, {"state_class": "total"}]
)
def test_metadata_change_is_unavailable(mapping, change):
    assert value_for(State("sensor.house_power", "42", {**ATTRS, **change}), mapping) is None


async def test_only_allowlist_leaves_ha_and_retry_preserves_observation(hass, mapping):
    hass.states.async_set("sensor.house_power", "0", ATTRS)
    hass.states.async_set("person.private", "home", {"latitude": 42})
    hass.states.async_set("sensor.secret", "do not export")
    samples, stale = collect_samples(hass, [mapping], {})
    assert stale == 0
    assert len(samples) == 1 and samples[0]["value"] == "0"
    assert "latitude" not in str(samples) and "secret" not in str(samples)
    again, _ = collect_samples(hass, [mapping], {})
    assert again == samples


async def test_removed_source_is_null_with_stable_retry_timestamp(hass, mapping):
    missing = {}
    first, stale = collect_samples(hass, [mapping], missing)
    assert first[0]["value"] is None and stale == 1
    again, _ = collect_samples(hass, [mapping], missing)
    assert again == first


async def test_source_freshness_not_send_time(hass, mapping, freezer):
    hass.states.async_set("sensor.house_power", "10", ATTRS)
    first, _ = collect_samples(hass, [mapping], {})
    freezer.tick(timedelta(minutes=4))
    samples, stale = collect_samples(hass, [mapping], {})
    assert stale == 1 and samples == first
    assert samples[0]["observed_at"] != dt_util.utcnow().isoformat()


async def test_forbidden_domain_and_unvalidated_power(hass):
    for entity in ("person.alice", "sensor.house_power"):
        hass.states.async_set(entity, "1", ATTRS)
        with pytest.raises(ValueError):
            create_mapping(hass, {"entity_id": entity, "kind": "power", "max_age_seconds": 180})


async def test_occupancy_false_is_not_null(hass):
    hass.states.async_set("binary_sensor.house", "off", {"device_class": "occupancy"})
    mapping = create_mapping(
        hass, {"entity_id": "binary_sensor.house", "kind": "occupancy", "max_age_seconds": 180}
    )
    samples, _ = collect_samples(hass, [mapping], {})
    assert samples[0]["value"] is False and samples[0]["available"] is True
