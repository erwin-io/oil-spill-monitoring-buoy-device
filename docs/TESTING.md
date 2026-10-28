# Stage 1 + D41/D42 offline testing

Run from device repository root using desktop Python 3.11+:

    python -m compileall -q boot.py main.py config.py app drivers services tests tools
    python -m unittest discover -s tests -v
    python tools/simulate.py
    python main.py

Historical Stage 1 baseline: 21 offline tests. The current suite additionally tests manifest-driven upload and centralized BOARD_CONFIG/A7670C_CONFIG validation. GitHub CI uses Python 3.11; check the exact main HEAD workflow for the current total and evidence.

Tests run with fake board, spectrum, health, time, IDs and transport, without physical hardware, modem, storage card, Random Forest, Firebase or production Vercel calls. tests/test_startup.py explicitly rejects imports of machine, network, socket and HTTP libraries in the foundational import path.

The hardware pin suite audits 23 assigned GPIO numbers, I2C sharing and address uniqueness, UART/SD settings, USB/boot-strap/flash/PSRAM exclusions, RTC wake-capable PAIR/SETUP, ADC1 inputs, JTAG/actuator separation, and disabled peripherals. These are desktop checks, **not physical acceptance**.

New modem tests use an entirely offline deterministic fake UART and wrapping monotonic clock. The suite covers AT command echo and fragmentation, unsolicited messages, modem error classes, timeouts, stale buffers, response byte/line limits, disallowed sensitive commands and sanitised SIM/LTE status. Passing these tests is **not** a real A7670C UART, network-registration or HTTPS test.

The ApiClient is an injected request boundary, **not** a cellular/TLS implementation. Stage 1 fake responses of HTTP 201 are never proof that any external API, LTE modem or device accepted records. Stage 2 must run schema-aligned isolated emulator tests; Stage 3 must implement record-before-upload durability and retry behavior. Never transmit synthetic telemetry to production.

CI workflow .github/workflows/stage1-ci.yml runs compilation, unittest discovery, firmware manifest validation and the offline example on pushes to main and pull requests targeting main. A passing CI workflow proves only the source/tests at its exact commit.

## E-independent Module D runtime checks

The runtime tests cover startup without the UV sensor, ticking a resident software scheduler, heartbeat/uptime, due-event skipping without fake measurements, handling long gaps without catch-up storms, invalid config fault behavior, and Ctrl+C releasing the REPL. On physical ESP32 run `main.py` and confirm the startup prints `RUNNING_OFFLINE`; interrupt with Ctrl+C and inspect `import main; print(main.status())`. This is not physical LTE/TLS or scientific oil-detection acceptance.

## Wi-Fi setup AP tests

Offline tests in tests/test_setup_portal.py exercise per-device password persistence, first-boot activation, read-only HTTP status, browser form saving, duplicate/invalid field rejection, local-only Host/Origin, CSRF token, body limit, AP timeout, post-save shutdown and non-reentry. Fakes open no Wi-Fi or cloud sockets. Real ESP32-S3 acceptance must verify that an unprovisioned device advertises BlueGuard-XXXXXX on cold boot and that a phone can load http://192.168.4.1/ and save a valid APN; CI alone cannot prove this.


## Module E and pairing software tests

tests/test_module_e.py covers AS7341 driver with mocked I2C, dark-subtraction, UV OFF cleanup after exception, median robust sampling, saturation rejection, clean-water baseline repeatability rules and conservative tree inference. tests/test_cloud_pairing.py covers physical-event gate, challenge request, deferred confirmation, expiration, server identity validation and nonce redaction. These tests run with no real modem/sensor/network and do not meet physical or scientific acceptance.


Tests test_pair_button.py validate physical debouncing, boot-held button safety, factory identity validation and refusal to run pairing without a physical source. Desktop evidence only.


Additional offline tests exercise the UART LTE registration/APN dial and PPP, HTTPS TLS cert/hostname parameters and redirect refusals, HTTP response framing, and missing factory credentials. Hardware pairing acceptance must still be completed using the actual ESP32 and mobile app.


## QR v2 physical PAIR software verification

`tests/test_cloud_pairing.py` tests exact protocol-2 JSON, authenticated headers, no calls before physical PAIR, wrong device IDs, cross-session correlation, missing intents, competing phone conflict, expiry/UTC plausibility, 429 Retry-After, lost server success (UNVERIFIED), timeout/retry with the same nonce, forbidden/disabled/wrong nonce paths and secret-free status. The production mobile creates intents independently, never through the firmware. Firmware CI runs desktop fakes; actual TLS trust rejection, A7670C UART, PPP registration, GPIO15 electrical behavior and Firebase owner assignment need hardware/operator evidence.
