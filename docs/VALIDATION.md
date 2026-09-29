# Validation

The regular suite uses the official custom integration harness with real Home
Assistant config entries, state machine, flow manager, sensor setup and unload;
HTTP is mocked to test failures deterministically. Backend tests separately use
PostgreSQL for row-lock replay protection and station scoping.

The separate `scripts/real_ha_smoke.py` uses a running HTTPS backend and an actual
Home Assistant instance without the pytest harness or transport mocks. Use a
disposable EMS station/database and synthetic sensors; never a production pairing
code. See the script's help for the required URL/code file and temporary config.

Hardware commissioning and mobile UI behavior are separate validations. Software
tests do not establish measurement accuracy or authorize actuator writes.
