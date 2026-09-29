"""Run a real HA instance against a disposable, real HTTPS EMS backend.

Requires the backend feature flag and a fresh pairing code for a TEST station.
The code file is never printed; generated credentials stay in the temporary HA
config. Set SSL_CERT_FILE to a test CA bundle when using a local TLS backend.
"""

import argparse
import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from homeassistant import bootstrap, config_entries, loader
from homeassistant.core import HomeAssistant


async def run(args):
    with tempfile.TemporaryDirectory(prefix="ems-real-ha-") as temporary:
        config = Path(temporary)
        components = config / "custom_components"
        components.mkdir()
        source = Path(__file__).resolve().parents[1] / "custom_components" / "ems_home_assistant"
        shutil.copytree(
            source, components / source.name, ignore=shutil.ignore_patterns("__pycache__")
        )
        hass = HomeAssistant(str(config))
        loader.async_setup(hass)
        try:
            assert await bootstrap.async_from_config_dict(
                {
                    "homeassistant": {
                        "name": "EMS software smoke test",
                        "latitude": 0,
                        "longitude": 0,
                        "elevation": 0,
                        "unit_system": "metric",
                        "time_zone": "UTC",
                    },
                },
                hass,
            )
            await hass.async_start()
            attrs = {
                "unit_of_measurement": "W",
                "device_class": "power",
                "state_class": "measurement",
            }
            hass.states.async_set("sensor.ems_smoke_power", "0", attrs)
            hass.states.async_set("person.never_export", "home", {"latitude": 42})
            result = await hass.config_entries.flow.async_init(
                "ems_home_assistant", context={"source": config_entries.SOURCE_USER}
            )

            async def step(data, expected):
                nonlocal result
                result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
                if expected:
                    assert result.get("step_id") == expected, {
                        "step": result.get("step_id"),
                        "errors": result.get("errors"),
                    }

            await step(
                {"url": args.url, "code": Path(args.code_file).read_text().strip()}, "confirm"
            )
            await step({}, "entity")
            await step(
                {
                    "entity_id": "sensor.ems_smoke_power",
                    "kind": "power",
                    "max_age_seconds": 30,
                    "source_validated": True,
                    "simulated": True,
                    "add_another": False,
                },
                "review",
            )
            await step(
                {"consent": True, "occupancy_consent": False, "insights_consent": False}, "test"
            )
            await step({}, None)
            assert result["type"] == "create_entry", {
                "step": result.get("step_id"),
                "errors": result.get("errors"),
            }
            entry = result["result"]
            await hass.async_block_till_done()
            coordinator = entry.runtime_data
            assert coordinator.data["status"] == "connected"
            hass.states.async_set("sensor.ems_smoke_power", "unknown", attrs)
            await coordinator.async_refresh()
            assert coordinator.data["status"] == "stale"
            hass.states.async_set("sensor.ems_smoke_power", "1250", attrs)
            await coordinator.async_refresh()
            assert coordinator.data["status"] == "connected"
            await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            assert entry.runtime_data.data["status"] == "connected"
            await entry.runtime_data.client.disconnect()
            await entry.runtime_data.async_refresh()
            assert entry.runtime_data.data["status"] == "reauth_required"
            await hass.config_entries.async_remove(entry.entry_id)
            print(
                json.dumps(
                    {
                        "home_assistant": "real instance",
                        "transport": "verified HTTPS",
                        "pairing": "passed",
                        "zero_unknown_recovery": "passed",
                        "reload": "passed",
                        "remote_revoke": "passed",
                    }
                )
            )
        finally:
            await hass.async_stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="HTTPS origin of an isolated EMS test backend")
    parser.add_argument(
        "--code-file", required=True, help="Local file containing a fresh TEST station pairing code"
    )
    asyncio.run(run(parser.parse_args()))
