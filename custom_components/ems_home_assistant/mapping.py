"""Only explicitly selected state values can leave Home Assistant."""

from decimal import Decimal, InvalidOperation

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import KINDS


def metadata_valid(state: State, mapping: dict) -> bool:
    kind = mapping["kind"]
    domains, units = KINDS[kind]
    if state.domain not in domains or mapping["unit"] not in units:
        return False
    attrs = state.attributes
    if (
        kind in ("power", "energy", "temperature", "flexibility")
        and attrs.get("unit_of_measurement") != mapping["unit"]
    ):
        return False
    if kind in ("power", "energy", "temperature"):
        classes = ("total", "total_increasing") if kind == "energy" else ("measurement",)
        if attrs.get("device_class") != kind or attrs.get("state_class") not in classes:
            return False
    return not (kind == "occupancy" and attrs.get("device_class") not in ("occupancy", "presence"))


def create_mapping(hass: HomeAssistant, data: dict) -> dict:
    state = hass.states.get(data["entity_id"])
    if state is None or data["kind"] not in KINDS:
        raise ValueError("invalid_mapping")
    kind = data["kind"]
    mapping = {
        "entity_id": state.entity_id,
        "kind": kind,
        "unit": "boolean"
        if kind == "occupancy"
        else "state"
        if kind.endswith("_status")
        else state.attributes.get("unit_of_measurement"),
        "device_class": state.attributes.get("device_class"),
        "state_class": state.attributes.get("state_class"),
        "max_age_seconds": int(data["max_age_seconds"]),
        "source_validated": data.get("source_validated", False),
        "quality": "simulated"
        if data.get("simulated")
        else "declared"
        if kind == "flexibility"
        else "estimated",
    }
    if (
        not metadata_valid(state, mapping)
        or not 30 <= mapping["max_age_seconds"] <= 3600
        or (kind in ("power", "energy") and not mapping["source_validated"])
    ):
        raise ValueError("invalid_mapping")
    registry = er.async_get(hass).async_get(state.entity_id)
    mapping["registry_id"] = registry.id if registry else None
    return mapping


def value_for(state: State, mapping: dict):
    if not metadata_valid(state, mapping) or state.state in (
        "unknown",
        "unavailable",
        "none",
        "None",
        "",
    ):
        return None
    value, kind = state.state, mapping["kind"]
    if kind == "occupancy":
        return {"on": True, "off": False}.get(value)
    if kind.endswith("_status"):
        return (
            value
            if value
            in (
                "on",
                "off",
                "idle",
                "heating",
                "cooling",
                "defrosting",
                "charging",
                "connected",
                "disconnected",
            )
            else None
        )
    if len(value) > 32:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    if (
        not number.is_finite()
        or number.as_tuple().exponent < -6
        or number.copy_abs() > Decimal("1e15")
    ):
        return None
    canonical = number / 1000 if mapping["unit"] in ("W", "Wh") else number
    if mapping["unit"] == "°F":
        canonical = (number - 32) * Decimal(5) / 9
    low, high = (
        (-100, 100) if kind == "temperature" else (0, 1000000000 if kind == "energy" else 1000)
    )
    return value if low <= canonical <= high else None


def collect_samples(hass: HomeAssistant, mappings: list[dict], missing: dict) -> tuple[list, int]:
    samples, stale_count = [], 0
    now = dt_util.utcnow()
    registry = er.async_get(hass)
    for mapping in mappings:
        entity_id = mapping["entity_id"]
        state = hass.states.get(entity_id)
        registered = registry.async_get(entity_id)
        # Replacement or rename needs explicit remapping; never silently adopt another source.
        if mapping.get("registry_id") and (
            not registered or registered.id != mapping["registry_id"]
        ):
            state = None
        if state is None:
            observed = missing.setdefault(entity_id, now)
            value = None
        else:
            missing.pop(entity_id, None)
            observed = state.last_reported
            value = value_for(state, mapping)
        stale = value is None or (now - observed).total_seconds() > mapping["max_age_seconds"]
        stale_count += stale
        samples.append(
            {
                "entity_id": entity_id,
                "kind": mapping["kind"],
                "unit": mapping["unit"],
                "source": "home_assistant",
                "observed_at": observed.isoformat(),
                "sample_id": observed.isoformat(),
                "value": value,
                "available": value is not None,
                "quality": mapping["quality"] if value is not None else "unknown",
            }
        )
    return samples, stale_count
