# Module D — Stage 1 foundation + initial UART implementation (2026-10-28)

## Approved decisions

- ESP32-S3 N16R8 + MicroPython; simple app/ / drivers/ / services/ separation. Hardware-free boot/entrypoint execution and a verified 13-file upload succeeded on the physical ESP32-S3 via COM15 CH343; new D41 code remains offline-only until physically tested.
- Temporary physically authorized Wi-Fi AP with browser setup is approved **for a later stage**, not implemented here.
- SETUP action is distinct from PAIR and reset. Provisional pin assignments are now recorded for audit only; no electrical wiring approval or device-driver activation exists.
- Protected internal QR (deviceId + claimCode), physical PAIR, five-minute server challenge/nonce and cloud-only Owner assignment remain mandatory. No local AP/setup access can confer ownership.
- USB provisioning with secrets outside Git is a development direction only; production flash encryption, secure boot and recovery require separate review.

## Dependency architecture

    boot.py (passive)
    main.py -> app.controller -> config.validate_config (cloud only)
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

## Safe startup contract

1. boot.preflight() is passive; it makes no hardware claims.
2. main.run() supplies an UnboundBoard by default, whose set_safe_outputs() returns false rather than guessing GPIOs.
3. The controller requests the fail-safe output state **before** validating configuration.
4. Without verified board binding, the state is UNCONFIGURED and no network, sensing or scheduling runs.
5. With a fake safe board and separately validated cloud and hardware configuration, the state is SAFE_IDLE; this is a software-only result.
6. Initialization exceptions, invalid cloud configuration or invalid hardware configuration transition to FAULT without enabling operations.

The centralized config.py contains disabled, provisional 23-GPIO assignments for A7670C, AS7341, DS3231, microSD, pumps, valves, UV, separate buttons, battery/solar ADC and optional leak/flow/card-detect inputs; the strict API-facing DEFAULT_CONFIG remains unchanged. Hardware validation checks collision/reserved-pin constraints and rejects enabling any component. It does not initialize UART/I2C/SPI or GPIO. See docs/HARDWARE_MAPPING.md.

Physical fail-safe actuator wiring, modem power delivery, RTC, microSD, secure storage and real watchdog operation are *not verified*.

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
