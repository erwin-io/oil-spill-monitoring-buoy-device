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
