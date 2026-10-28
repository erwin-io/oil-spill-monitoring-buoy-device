# Module D — resident offline firmware runtime + UART boundary (2026-10-28)

## Approved decisions

- ESP32-S3 N16R8 + MicroPython; simple app/ / drivers/ / services/ separation. Hardware-free boot/entrypoint execution and a verified 13-file upload succeeded on the physical ESP32-S3 via COM15 CH343; new D41 code remains offline-only until physically tested.
- Temporary physically authorized Wi-Fi AP with browser setup is approved **for a later stage**, not implemented here.
- SETUP action is distinct from PAIR and reset. Provisional pin assignments are now recorded for audit only; no electrical wiring approval or device-driver activation exists.
- QR v2 has **public fixed deviceId only**, physical PAIR, five-minute server-intent/challenge/nonce and cloud-only atomic Owner assignment. No claimCode is used in the new mobile journey; legacy v1 API remains only for older clients during migration. Local AP/setup access never confers ownership.
- USB provisioning with secrets outside Git is a development direction only; production flash encryption, secure boot and recovery require separate review.

## Dependency architecture

    boot.py (passive)
    main.py -> app.controller -> config.validate_config (cloud only)
            -> app.runtime / app.scheduler (resident local service)
                             -> config.validate_hardware_config (board + A7670C)
                             -> drivers.unbound (no GPIO)
    services.telemetry -> injected measurement_source / clock / id_generator
    services.health    -> injected health_source / clock / id_generator
    services.api_client -> injected transport; no built-in internet client
    drivers.modem_a7670c -> injected UART and monotonic clock (D41)
    services.network     -> D42 read-only SIM/CEREG/CSQ/CGATT parser
    services.pairing    -> explicitly physical PAIR action gate only
                           (not a cloud handshake)
    tests/fakes         -> pure Python fake dependencies

Shared services consume small duck-typed methods: set_safe_outputs(), read_measurement(), read_health(), iso_now(), next_id(prefix) and request(method,path,headers,payload). They do not import machine, network, UART or storage modules. Test-only fakes implement the same methods. Future real drivers can replace fakes without changing service logic.

## Resident Module D service — independent of Module E

1. `boot.preflight()` stays passive (no GPIO/network/secret initialization).
2. `main.run()` calls the safe-output adapter before cloud and hardware validation. UnboundBoard's False result now permits a **software-only runtime**, never real actuator or modem output.
3. Invalid settings/hardware configuration and safe-output exceptions still yield `FAULT`; no scheduler begins.
4. Without sensors the default state is `RUNNING_OFFLINE` with `sensor=NOT_INSTALLED`, `modem=NOT_CONNECTED`, `cloud=OFFLINE`, and `actuators=DISABLED`.
5. On MicroPython `main.py` runs a foreground monotonic scheduler and a one-minute heartbeat. It counts due-but-unmeasurable cycles as `SKIPPED_SENSOR_UNAVAILABLE` and **never fabricates scientific telemetry or posts to production**.
6. Ctrl+C returns the Thonny REPL; `import main; print(main.status())` exposes uptime and counters while the service is paused.

The runtime does not import `machine`, use a socket, write periodic flash logs or power unverified hardware. The cloud `DEFAULT_CONFIG` and provisional 23-GPIO map remain centrally defined in `config.py`.

**Operational limit:** `RUNNING_OFFLINE` is software-service readiness only; no LTE/HTTPS, UV sensor, real local logging or pump/UV control has been proven.

## API boundary

Server implementation remains authoritative for strict request validation. Stage 1 prepares only required six spectral channels, allowed classification enums, offset timestamps, diagnostic health keys and mocked X-Device-ID/X-Device-Key headers. The API adapter accepts a caller-provided transport, which is fake-only in Stage 1. It implements no HTTPS/TLS, queue durability, error retries or real pairing.

The server has no named uptime health field. The client-side guard disallows it; raise a separate upstream integration request rather than silently extending payloads.

## D41/D42 code added, physical activation still gated

The safe read-only A7670C AT driver now handles injected UART reads/writes, bounded timing, split responses, unsolicited lines, terminal status and errors. The D42 diagnostics parse CPIN/CEREG/CSQ/CGATT into a non-secret status shape. The allowed commands are deliberately restricted to AT, AT+CPIN?, AT+CEREG?, AT+CSQ and AT+CGATT?. It cannot set PIN/APN, initiate attachment or HTTPS. The module imports no machine package and no active physical board is constructed.

Pending implementation/verification: real UART electrical adapter and modem power, SIM/APN and LTE registration management, certificate-verified TLS, setup AP, secure provisioning storage, persistent microSD queue, RTC sync, background sampling, physical pairing/confirmation polling, optical ML and fluidics. No A/B/C code or official checklist was changed.

## Known software-only limitations

- The local timestamp validator checks offset structure, not real clock correctness; full Zod parity is an upstream contract-test objective for Stage 2.
- API client records can be posted through a fake transport without persistent queueing; production use must wait for record-before-upload durable queue (Stage 3).
- Test IDs are deterministic and **must never** be used as physical record IDs.
- Physical PAIR is only a guarded event abstraction; five-minute challenge handling is not implemented.

## Local first-boot setup AP

The native ESP32-S3 Wi-Fi radio is independent of the UV sensor and LTE UART. During the actual MicroPython boot, main.serve_forever() creates the local setup portal only for an unprovisioned device. It serves a browser page and allows saving **only** a device label and SIM APN. It is not a remote API configuration write; DEFAULT_CONFIG is untouched. It has no claim/ownership or protected QR authority, and does not accept X-Device-Key. WPA2 uses a unique on-device key stored outside version control. The session is bounded to 15 minutes, and auto-entry is disabled after successful setup. A verified physical SETUP GPIO16 trigger and manufacturing-safe distribution of the unique password remain pending.


## Module E software boundaries

drivers/as7341.py implements independently-testable I2C configuration and six channel extraction. services/optics.py supports UV-OFF/UV-ON repeated sampling but requires injected VERIFIED UV-switch interface and fails off on exceptions. services/calibration.py requires physical clean-water runs with final optical geometry. services/edge_model.py executes a compact tree forest trained off-board; without an approved model file it cannot classify. The service intentionally does not auto-energize GPIO21 or assert calibrated oil sensing on an unbuilt optical stack.

## Pairing code boundary

services/cloud_pairing.py implements contract-level 5-min PAIR challenge and server confirmation flow, but device-to-cloud HTTPS transport, encrypted identity provisioning and physical PAIR input integration are unresolved. Never register a device as Owner based on AP access or mock responses.


Physical PAIR input and cloud pairing are injected jointly; main.serve_forever() rejects one without the other. Factory credential format is separate from the setup AP and firmware manifest. Certificate-validated A7670C HTTPS, device credential provisioning/flash encryption and real GPIO/button integration remain gating steps.


## QR v2 contract integration (2026-10-29)

The canonical firmware-to-API contract is `oil-spill-monitoring-buoy-api/docs/QR_V2_DEVICE_PAIRING_CONTRACT.md`. The phone creates a Firebase-authenticated intent; only a local debounced GPIO15 event triggers a device-authenticated `{"protocol":2}` challenge over LTE. The API returns `protocol, deviceId, intentId, challengeId, nonce, expiresAt`; firmware validates version, correlation, 32–128-character secret, bounded expiry against synchronized UTC, then submits `protocol, intentId, challengeId, nonce` and checks the exact successful confirmation response. A lost success response is UNVERIFIED, never inferred from ALREADY_OWNED. No QR reader, claimCode or arbitrary phone command exists in the device service. No secret may be printed. This is a software milestone only, not physical pairing acceptance.
