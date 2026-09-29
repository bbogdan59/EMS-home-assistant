from unittest.mock import AsyncMock, patch

from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ems_home_assistant.api import CannotConnect
from custom_components.ems_home_assistant.const import DOMAIN

from .test_mapping import ATTRS


async def test_disconnect_failure_persists_local_stop_and_retry_revokes(hass, entry_data):
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, title="Home", unique_id="station-one")
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ems_home_assistant.api.BridgeClient.send",
            AsyncMock(return_value={"accepted": 1}),
        ),
        patch(
            "custom_components.ems_home_assistant.api.BridgeClient.disconnect",
            AsyncMock(side_effect=CannotConnect),
        ) as disconnect,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "disconnect"}
        )
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {})
        assert flow["errors"] == {"base": "cannot_connect"}
        assert entry.data["disconnected"] is True
        await hass.config_entries.async_reload(entry.entry_id)
        assert entry.runtime_data.data["status"] == "disconnected"
        disconnect.side_effect = None
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {})
        assert flow["type"] == FlowResultType.CREATE_ENTRY
        assert entry.data["token"] == ""
        await hass.config_entries.async_unload(entry.entry_id)


async def test_replace_mapping_stops_previous_allowlist(hass, entry_data):
    hass.states.async_set("sensor.new_power", "10", ATTRS)
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, title="Home", unique_id="station-one")
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ems_home_assistant.api.BridgeClient.send",
            AsyncMock(return_value={"accepted": 1}),
        ),
        patch(
            "custom_components.ems_home_assistant.api.BridgeClient.configure",
            AsyncMock(return_value=3),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "entity"}
        )
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {
                "entity_id": "sensor.new_power",
                "kind": "power",
                "max_age_seconds": 180,
                "source_validated": True,
                "simulated": False,
                "add_another": False,
            },
        )
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {"consent": True, "occupancy_consent": False, "insights_consent": False},
        )
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {})
        assert flow["type"] == FlowResultType.CREATE_ENTRY
        assert entry.data["mappings"][0]["entity_id"] == "sensor.new_power"
        assert len(entry.data["mappings"]) == 1 and entry.data["mapping_version"] == 3
        assert not entry.data["disconnected"]
        await hass.config_entries.async_unload(entry.entry_id)
