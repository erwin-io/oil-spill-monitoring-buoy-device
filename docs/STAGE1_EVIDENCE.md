# Stage 1 acceptance and evidence ledger — 2026-10-28

**Status:** Foundational software candidate for owner review; not physical Module D acceptance.

## Authorized scope

Project Owner authorized Stage 1 in erwin-io/oil-spill-monitoring-buoy-device, a dedicated development branch and draft PR. No Modules A/B/C edits, production cloud, production credentials, real hardware, PR merge or official checklist modifications.

## Implemented software capabilities

- Safe default startup: UNCONFIGURED without verified physical hardware bindings.
- Explicit board dependency and fail-safe output call ordering.
- Validated public settings with no device credentials stored in config.py; .gitignore excludes common secret/provisioning paths.
- Independently executable desktop fake measurement, health and HTTP transport paths.
- Pairing action gate: only an explicit physical PAIR event can arm the *future* cloud handshake; RESET or SETUP never arms it.
- Import isolation, startup failure cases, payload validation and mock request tests.
- GitHub Actions branch and PR checks.

## Evidence categories

| Stage 1 assertion | Evidence | Not proven |
|---|---|---|
| Startup fail-closed | Fake/unbound board and exception tests | Real pump/valve safe-state behavior during reset |
| Service isolation | Offline Python tests with dependency fakes | Actual ESP32 MicroPython memory or flash compatibility |
| Telemetry shapes | Client guards and fake request captures | Full API Zod parity, LTE or certificate-verified HTTPS |
| Pairing separation | PAIR/SETUP/RESET action gate tests | Physical switch, server challenge, nonce or ownership |
| Config and secret separation | Public defaults, ignored private credential filenames, fake-only key | Encrypted production credential storage |
| CI validation | Exact branch HEAD workflow run to be inspected separately | Any physical/production acceptance |

## Local execution record

- Environment: Python 3.13.5, isolated working directory.
- Python bytecode compile: PASS.
- Unit tests: **21 run, 21 passed**.
- Synthetic example: PASS, two in-memory fake requests for measurement and health, no sockets or production services.
- Default main.py: prints BlueGuard Stage 1: UNCONFIGURED.

## Known gaps and gates

- Device-facing API provides no read endpoint for pending claims; bounded confirmation strategy must be tested in future pairing implementation before an API change request.
- Strict backend health schema lacks an uptime field required by original D #50.
- Physical SETUP/PAIR GPIO, A7670C firmware variant, TLS/CA and power constraints remain unverified.
- AP server is approved for later stage and not delivered by Stage 1.
- No Stage 2, flashing, actual credential handling, production writes, deployment, merge or checklist status updates are authorized.
