"""Bridge health without imported control entities or personal attributes."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUSES


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([BridgeStatus(entry.runtime_data, entry)])


class BridgeStatus(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "bridge_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(STATUSES)
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = entry.entry_id + "_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="EMS " + entry.title,
            manufacturer="EMS",
            model="Outbound context bridge",
        )

    @property
    def native_value(self):
        return self.coordinator.data["status"]

    @property
    def extra_state_attributes(self):
        return {
            "last_success": self.coordinator.last_success,
            "stale_entities": self.coordinator.data["stale_entities"],
            "mapping_version": self.coordinator.entry.data["mapping_version"],
            "physical_control": False,
        }
