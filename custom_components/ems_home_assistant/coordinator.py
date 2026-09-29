"""Bounded outbound sync; retry never changes a source observation's timestamp."""

import logging
import random
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import BridgeClient, BridgeError, InvalidAuth, MappingConflict
from .const import DOMAIN
from .mapping import collect_samples

_LOGGER = logging.getLogger(__name__)


class BridgeCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: BridgeClient):
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(seconds=30)
        )
        self.entry = entry
        self.client = client
        self.missing = {}
        self.failures = 0
        self.last_success = None
        self.stopped = entry.data.get("disconnected", False)
        self.auth_failed = False

    async def _async_update_data(self):
        if self.stopped:
            return {"status": "disconnected", "stale_entities": 0}
        if self.auth_failed:
            return {"status": "reauth_required", "stale_entities": 0}
        samples, stale_count = collect_samples(self.hass, self.entry.data["mappings"], self.missing)
        try:
            await self.client.send(self.entry.data["mapping_version"], samples)
        except InvalidAuth, MappingConflict:
            if self.stopped:
                return {"status": "disconnected", "stale_entities": stale_count}
            self.auth_failed = True
            self.entry.async_start_reauth(self.hass)
            return {"status": "reauth_required", "stale_entities": stale_count}
        except BridgeError:
            if self.stopped:
                return {"status": "disconnected", "stale_entities": stale_count}
            self.failures += 1
            self.update_interval = timedelta(
                seconds=min(900, 30 * 2 ** min(self.failures, 5)) + random.uniform(0, 5)
            )
            return {"status": "offline", "stale_entities": stale_count}
        self.failures = 0
        if self.stopped:
            return {"status": "disconnected", "stale_entities": stale_count}
        self.update_interval = timedelta(seconds=30)
        self.last_success = dt_util.utcnow()
        return {"status": "stale" if stale_count else "connected", "stale_entities": stale_count}
