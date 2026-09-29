from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ems_home_assistant.api import CannotConnect, InvalidAuth
from custom_components.ems_home_assistant.const import DOMAIN
from custom_components.ems_home_assistant.diagnostics import async_get_config_entry_diagnostics

from .test_mapping import ATTRS


async def test_real_ha_setup_sync_reconnect_reauth_diagnostics_and_unload(hass, entry_data):
    hass.states.async_set("sensor.house_power", "0", ATTRS)
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, title="Home", unique_id="station-one")
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ems_home_assistant.api.BridgeClient.send",
        AsyncMock(return_value={"accepted": 1}),
    ) as send:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data
        assert coordinator.data["status"] == "connected"
        send.side_effect = CannotConnect
        await coordinator.async_refresh()
        assert coordinator.data["status"] == "offline"
        assert coordinator.update_interval.total_seconds() >= 60
        send.side_effect = None
        await coordinator.async_refresh()
        assert coordinator.data["status"] == "connected"
        assert coordinator.update_interval.total_seconds() == 30
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        assert entry_data["token"] not in str(diagnostics) and "sensor.house_power" not in str(
            diagnostics
        )
        send.side_effect = InvalidAuth
        await coordinator.async_refresh()
        assert coordinator.data["status"] == "reauth_required"
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_disconnected_entry_never_sends(hass, entry_data):
    entry = MockConfigEntry(domain=DOMAIN, data={**entry_data, "disconnected": True, "token": ""})
    entry.add_to_hass(hass)
    with patch("custom_components.ems_home_assistant.api.BridgeClient.send", AsyncMock()) as send:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.data["status"] == "disconnected"
        send.assert_not_called()
        await hass.config_entries.async_unload(entry.entry_id)
