"""Read-only EMS energy context bridge."""

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BridgeClient, BridgeError
from .coordinator import BridgeCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass, entry):
    client = BridgeClient(async_get_clientsession(hass), entry.data["url"], entry.data["token"])
    coordinator = entry.runtime_data = BridgeCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass, entry):
    if not entry.data.get("token"):
        return
    client = BridgeClient(async_get_clientsession(hass), entry.data["url"], entry.data["token"])
    try:
        await client.disconnect()
    except BridgeError:
        # The UI options flow confirms remote deletion; direct HA deletion is best effort.
        # No credential is retained locally after HA deletes the config entry.
        import logging

        logging.getLogger(__name__).warning(
            "EMS revocation could not be confirmed; disconnect this instance in EMS"
        )
