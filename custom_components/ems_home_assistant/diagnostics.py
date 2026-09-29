"""Allowlist diagnostics, excluding credentials, entity IDs, values and instance IDs."""


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    return {
        "schema_version": 1,
        "mapping_version": entry.data["mapping_version"],
        "mapping_count": len(entry.data["mappings"]),
        "status": coordinator.data["status"],
        "failure_count": coordinator.failures,
        "last_success": coordinator.last_success,
        "stale_entities": coordinator.data["stale_entities"],
        "physical_control": False,
    }
