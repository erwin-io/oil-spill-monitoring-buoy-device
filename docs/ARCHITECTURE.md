# Module D — resident offline firmware runtime + UART boundary (2026-10-28)

## Approved decisions

- ESP32-S3 N16R8 + MicroPython; simple app/ / drivers/ / services/ separation. Hardware-free boot/entrypoint execution and a verified 13-file upload succeeded on the physical ESP32-S3 via COM15 CH343; new D41 code remains offline-only until physically tested.
- Temporary physically authorized Wi-Fi AP with browser setup is approved **for a later stage**, not implemented here.
- SETUP action is distinct from PAIR and reset. Provisional pin assignments are now recorded for audit only; no electrical wiring approval or device-driver activation exists.
- Protected internal QR (deviceId + claimCode), physical PAIR, five-minute server challenge/nonce and cloud-only Owner assignment remain mandatory. No local AP/setup access can confer ownership.
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
