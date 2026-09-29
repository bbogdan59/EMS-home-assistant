# Repository guidance

This repository owns the Home Assistant custom integration only. Platform APIs,
tenant authorization, persistence, normalization, business rules, insights and
notifications belong in `bbogdan59/EMS-management-platform`. Mobile UI belongs in
`bbogdan59/EMS-mobile-app`.

Read the platform's `docs/SOURCE_CODE_ARCHITECTURE.md` and canonical
`contracts/home_assistant/` before cross-repository contract changes. Keep API
changes backward compatible and land the backend before its consumer. Do not
copy cloud optimization, billing or policy logic into HA.

- Export only explicitly selected states. Never export all entities or attributes.
- Preserve source timestamps, provenance, simulated quality, zero and null.
- Keep occupancy and contextual insights opt-in; no actuator/service-call channel.
- TLS verification and redirect refusal are mandatory. Never log tokens/codes.
- Keep all runtime files inside `custom_components/ems_home_assistant`.
- Run Ruff and the appropriate HA harness tests. Report real-instance smoke,
  deterministic mocks and physical hardware verification separately.
- Check CI on the exact PR head before merging. Use squash merge and keep a
  changelog/version consistent with `manifest.json`.
