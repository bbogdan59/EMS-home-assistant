from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ems_home_assistant.const import DOMAIN

from .test_mapping import ATTRS


async def test_pair_confirm_select_consent_test_success(hass):
    hass.states.async_set("sensor.house_power", "0", ATTRS)

    async def redeem(self, code, instance_id, instance_name):
        self.token = "x" * 43
        return {
            "token": self.token,
            "instance_id": instance_id,
            "station_id": "station-one",
            "station_name": "Home",
            "mapping_version": 1,
        }

    with (
        patch("custom_components.ems_home_assistant.api.BridgeClient.redeem", redeem),
        patch(
            "custom_components.ems_home_assistant.api.BridgeClient.configure",
            AsyncMock(return_value=2),
        ) as configure,
        patch(
            "custom_components.ems_home_assistant.api.BridgeClient.send",
            AsyncMock(return_value={"accepted": 1}),
        ) as send,
        patch(
            "custom_components.ems_home_assistant.async_setup_entry", AsyncMock(return_value=True)
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://ems.example", "code": "pairing-secret"}
        )
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["step_id"] == "entity"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "entity_id": "sensor.house_power",
                "kind": "power",
                "max_age_seconds": 180,
                "source_validated": True,
                "simulated": False,
                "add_another": False,
            },
        )
        assert result["step_id"] == "review"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"consent": False, "occupancy_consent": False, "insights_consent": False},
        )
        assert result["errors"] == {"base": "consent_required"}
        configure.assert_not_awaited()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"consent": True, "occupancy_consent": False, "insights_consent": False},
        )
        assert result["step_id"] == "test"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert "pairing-secret" not in str(result["data"])
        assert send.call_args.args[1][0]["value"] == "0"
        assert result["data"]["mapping_version"] == 2
