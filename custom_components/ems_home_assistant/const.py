"""EMS integration constants."""

DOMAIN = "ems_home_assistant"
KINDS = {
    "power": (("sensor",), ("W", "kW")),
    "energy": (("sensor",), ("Wh", "kWh")),
    "temperature": (("sensor",), ("°C", "°F")),
    "occupancy": (("binary_sensor",), ("boolean",)),
    "boiler_status": (("binary_sensor", "sensor"), ("state",)),
    "hvac_status": (("binary_sensor", "sensor"), ("state",)),
    "evse_status": (("binary_sensor", "sensor"), ("state",)),
    "flexibility": (("sensor", "input_number"), ("W", "kW")),
}
STATUSES = ("connecting", "connected", "stale", "offline", "reauth_required", "disconnected")
