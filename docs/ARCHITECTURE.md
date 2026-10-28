# Module D — Stage 1 architecture (2026-10-28)

## Approved decisions

- ESP32-S3 N16R8 + MicroPython; simple app/ / drivers/ / services/ separation. The source is designed to be compatible with constrained MicroPython, but there has been no board compatibility test.
- Temporary physically authorized Wi-Fi AP with browser setup is approved **for a later stage**, not implemented here.
- SETUP action is distinct from PAIR and reset; no GPIO assignments have been authorized.
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

The centralized config.py holds BOARD_CONFIG and A7670C_CONFIG, separate from the unchanged DEFAULT_CONFIG cloud schema. GPIO pins are unassigned, and enabling the A7670C is rejected until its actual driver and physical wiring are verified. Config validation does not initialize UARTs or pins.

Physical fail-safe actuator wiring, modem power delivery, RTC, microSD, secure storage and real watchdog operation are *not verified*.

## API boundary

Server implementation remains authoritative for strict request validation. Stage 1 prepares only required six spectral channels, allowed classification enums, offset timestamps, diagnostic health keys and mocked X-Device-ID/X-Device-Key headers. The API adapter accepts a caller-provided transport, which is fake-only in Stage 1. It implements no HTTPS/TLS, queue durability, error retries or real pairing.

The server has no named uptime health field. The client-side guard disallows it; raise a separate upstream integration request rather than silently extending payloads.

## Out of scope until separately authorized

Real A7670C AT commands/TLS, SIM/APN, portal HTML/server, GPIO mapping, secure provisioning storage, persistent SD queue, RTC sync, background sampling, physical pairing/confirmation polling, optical ML, fluidics and deployment. These belong to later stages or other module boundaries. No A/B/C code or official checklist was modified.

## Known software-only limitations

- The local timestamp validator checks offset structure, not real clock correctness; full Zod parity is an upstream contract-test objective for Stage 2.
- API client records can be posted through a fake transport without persistent queueing; production use must wait for record-before-upload durable queue (Stage 3).
- Test IDs are deterministic and **must never** be used as physical record IDs.
- Physical PAIR is only a guarded event abstraction; five-minute challenge handling is not implemented.
