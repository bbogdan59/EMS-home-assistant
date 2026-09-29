# EMS Home Assistant

An outbound, read-only Home Assistant integration for EMS energy context. Pair
with one EMS station, select a local entity allowlist, review consent, then test
the connection. No Home Assistant access token, inbound connection, broker or
port forwarding is required.

![EMS](custom_components/ems_home_assistant/brand/icon.png)

## Install

Requires **Home Assistant 2026.9+** and the EMS HACS bridge API described in
[the contract](docs/CONTRACT.md). Enable `HOME_ASSISTANT_BRIDGE_ENABLED=true` on
the backend and apply its database migration. Run its worker/beat for retention.

This repository is currently private. HACS does not support private repositories;
until the owner chooses public distribution, copy `custom_components/ems_home_assistant`
from an authenticated checkout to your HA configuration's `custom_components`
directory and restart Home Assistant. Repository visibility is not changed by
this integration.

For public distribution: HACS → Custom repositories → add
`https://github.com/bbogdan59/EMS-home-assistant`, category **Integration** → download
**EMS Home Assistant** → restart. This repository is not part of HACS's default catalog.

## Connect

1. Open the station dashboard in EMS → **Conecteaza Home Assistant**.
2. Generate a pairing code. It expires in 10 minutes, can be used once, and
   replaces any previous bridge for that station.
3. In HA → Settings → Devices & services → Add integration → **EMS Home Assistant**,
   enter your EMS HTTPS origin and code. Confirm the station and local instance.
4. Select up to 20 entities. The picker shows domain, unit, integration source
   and last updated. Validate power/energy sources explicitly. Sources must have
   compatible device and state classes; there is no unit guessing.
5. Review the mappings and consent. Occupancy is limited to one aggregate household
   `binary_sensor` and needs separate consent. Insights/notifications are opt-in.
6. Submit the test. Success means the backend accepted the mapping and samples.

Eligible context: power (`W`, `kW`), energy (`Wh`, `kWh`), indoor temperature
(`°C`, `°F`), aggregate occupancy, boiler/HVAC/EVSE state sensors, and declared
flexible power. Create an explicit template sensor for an observed appliance
state if necessary; climate/setpoint entities are not treated as observations.
Sources are `estimated`, `declared` or explicitly `simulated`; this integration
does not certify measurements or authorize hardware control.

## Manage and troubleshoot

- The diagnostic **Bridge status** sensor reports connected, stale, offline,
  reauthentication required or disconnected. Setup and the EMS API also expose
  connecting. Inspect the last successful sync and stale entity count.
- Sync runs every 30 seconds. Failed requests back off to 15 minutes with jitter.
  Retrying preserves source timestamps and sample identity. An unchanged source
  must still report periodically (`last_reported`) to stay fresh.
- Configure → Replace entity mapping and consent replaces the complete allowlist.
  Renamed, removed or replaced entities and metadata changes become unavailable;
  explicitly remap them. No new entity is adopted automatically.
- Credentials expire after 90 days. Generate a new code in EMS and complete the
  HA reauthentication flow. Reinstallation requires a new code.
- Configure → Disconnect stops local publishing immediately (persisted across
  restart), revokes the backend credential and deletes the shared context. If
  offline, retry to confirm remote deletion, or disconnect in EMS. Directly
  deleting the HA entry makes a best-effort revoke; use EMS if it was unreachable.
- To reconnect a deliberately disconnected entry, delete it and add the integration
  again using a new code.

## Privacy and scope

Only reviewed state values and their mapping metadata leave HA; no attributes,
history, persons, cameras, locks, alarms, precise location or discovery inventory
are sent. Unknown/unavailable is `null`; zero and `false` remain valid values.
The backend stores only the latest observation per entity, hides stale values
immediately, erases values older than 24 hours on its hourly retention task, and
keeps timestamps for replay protection. Disconnect erases the context immediately.
Data has separate `home_assistant` provenance and never overwrites the Deye meter.

The opaque bridge credential is stored only in HA's config entry; the server
stores its SHA-256 hash. Protect HA's `.storage` and backups. Diagnostics exclude
credentials, URLs, station/instance IDs, entity IDs and readings. TLS certificate
validation is mandatory; redirects are refused.

This repository implements the HA component of
[EMS issue #216](https://github.com/bbogdan59/EMS-management-platform/issues/216).
The companion backend implements pairing, context, health and disconnect. Mobile
screens, mobile OAuth/session integration (#199/#202), and contextual notification
processing (#206) remain in their respective repositories. Consent is recorded,
but this bridge does not create notifications or automation commands.

## Development

```sh
uv venv --python 3.14
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check custom_components tests
.venv/bin/pytest -q
```

CI runs HA config-flow/runtime tests, protocol/privacy regressions, hassfest and
HACS validation. See [real-instance validation](docs/VALIDATION.md) for the separate
HA/backend smoke test. Synthetic sensors validate software behavior, not physical equipment.
