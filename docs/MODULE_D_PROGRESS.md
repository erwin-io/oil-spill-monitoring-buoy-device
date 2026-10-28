# BlueGuard — Module D implementation and evidence register

Started: 2026-10-28, based on the original approved Module D requirements 39–52. Owner authorized direct development on the firmware repository main branch. This is **not** acceptance of full Module D and does not change the official checklist.

| Requirement | Development state | Evidence and remaining gate |
|---|---|---|
| D39 Modular ESP32-S3 architecture | Resident software runtime implemented | app/runtime and app/scheduler do not depend on optical hardware; this revision awaits physical smoke test |
| D40 Boot and self-test | Safe fallback implemented | UnboundBoard returns UNCONFIGURED; real hardware tests/self-checks pending |
| D41 A7670C UART/AT | Offline driver implemented | Injected UART, bounded command parser and tests; real pin/electrical integration pending |
| D42 SIM/APN/LTE | Read-only diagnostics implemented | CPIN/CEREG/CSQ/CGATT parser; SIM/APN provision/registration/recovery pending |
| D43 HTTPS client | Fake-only request boundary | Certificate/hostname verification and physical LTE upload pending |
| D44 Device secrets | Policy only | Production secure provisioning, storage, erase and recovery pending |
| D45 Measurement scheduler | Monotonic software scheduler implemented | Due events and sensor-skip diagnostics; pump integration and low-power policy pending |
| D46 Remote config sync | Cloud schema guard only | GET/validate/last-known-good persistent rollback pending |
| D47 RTC/timestamps | Not implemented | DS3231 verification, sync and offset-aware timestamp pending |
| D48 microSD local logging | Not implemented | Mount, journal, flush, corruption and power-loss tests pending |
| D49 Offline replay queue | Not implemented | Durable record-before-upload, idempotent retries/backoff pending |
| D50 Device health | Fake-based payload adapter | Real signals and uptime contract gap pending |
| D51 Watchdog and fault recovery | Safe software state only | Modem/pump/storage recovery under fault injection pending |
| D52 Firmware/model versions | Not implemented | Reproducible version release and rollback pending |

## D41 initial software contract

- `drivers/modem_a7670c.py` is importable on desktop Python and MicroPython without loading `machine`. It **cannot** open UARTs or energize the modem; its caller must inject already verified UART and monotonic clock objects.
- Only `AT`, `AT+CPIN?`, `AT+CEREG?`, `AT+CSQ`, `AT+CGATT?` are available. Arbitrary modem writes, APN, SIM PIN, resets, URLs, authentication headers and upload payloads are not accepted.
- Single-command transaction is bounded by timeout (100–15000 ms), max total bytes, max line length and max response lines; UART errors and terminal failures are redacted. No secrets in logs.
- `services/network.py` maps SIM, registration, signal and packet status to non-identifying fields. `httpsReady` remains false by design; an attached modem is not equivalent to TLS success.
- Desktop tests use fake UART and clock, including a wrapping tick counter; CI runs compile/test and firmware-manifest validation. Do not treat simulated status as cellular connectivity.

## Owner hardware gate before activating UART

Verify exact A7670C carrier variant (front/back photos, labels), UART voltage level and translation, independent modem supply capable of verified transmission peaks, PWRKEY control transistor and safe OFF circuit. Test AT from an isolated UART bench first; do not power raw modem through ESP32 3.3 V. The provisional mapping is GPIO17=ESP32 TX, GPIO18=ESP32 RX, GPIO47=PWRKEY control circuit. `config.py` keeps all hardware `enabled=False` and the default `UnboundBoard` remains in place.

## Next implementation order

D41 real hardware smoke verification when electrically cleared → D42 registration/APN state machine and bounded retry → D47 RTC → D48/49 durable journal/queue → D43 TLS/HTTP transport integrated with durable queue → D45/46 scheduler/config → D44 provisioning and physical PAIR integration → D50/51/52 health, watchdog and releases → multi-module E/F/G end-to-end evidence.

**Upstream A/B/C API and mobile contracts are not modified.** Official checklist status remains unchanged until physical/contract evidence and owner acceptance.

## Resident software increment — no Module E hardware required

`main.py` now starts a continuous local Module D service on MicroPython. The `RUNNING_OFFLINE` state does not claim live LTE, cloud health transmission, a working oil detector, or pumps. One-minute heartbeat and configurable measurement schedule run without UV/AS7341; skipped due events are counted without producing synthetic measurements. Status can be inspected after Ctrl+C using `import main; print(main.status())`. No new hardware is enabled, no periodic flash writes, and the existing strict API configuration is preserved. Physical firmware evidence on this exact revision is still required.
