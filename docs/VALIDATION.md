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

## Verified 2026-09-29

- Home Assistant 2026.9.4 / Python 3.14.6: 31 deterministic integration tests pass.
- Companion backend: 1,079 unit/integration tests pass against isolated PostgreSQL.
- Separate real HA instance + real FastAPI backend + PostgreSQL + verified local
  HTTPS: pairing/confirmation/mapping/test, zero → unknown → recovery, config-entry
  reload, backend revocation → reauthentication required, and removal all passed.
  No HA harness fixtures or HTTP mocks were used in this run. It used synthetic
  sensors and a disposable test station, with no production/hardware access.

Example against an already running disposable backend:

```sh
REQUESTS_CA_BUNDLE=/path/to/public-plus-test-ca.pem \
SSL_CERT_FILE=/path/to/public-plus-test-ca.pem \
.venv/bin/python scripts/real_ha_smoke.py \
  --url https://localhost:18443 --code-file /path/to/test-pairing-code
```

The code file should be readable only by its owner. Test CA bundles must include
normal public CAs so HA can install its core dependencies. Temporary HA config and
credentials are removed by the script; it revokes its test bridge before exit.
