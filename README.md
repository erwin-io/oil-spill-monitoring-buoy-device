# BlueGuard Buoy — Module D Device Firmware

**Stage 1: desktop-testable foundation only.** This repository does not yet operate a buoy, modem, sensor, pump, Wi-Fi AP, or actual cloud pairing.

## Quick start (desktop Python 3.11+)

    python -m unittest discover -s tests -v
    python tools/simulate.py
    python main.py

main.py defaults to UNCONFIGURED and does not initialize GPIO, network, UART or secrets. The simulation uses only in-memory fakes and the marker SIMULATED_DO_NOT_USE_FOR_SCIENCE.

## Repository organization

- boot.py: passive startup; no GPIO initialization.
- main.py: explicit dependency wiring and safe, unconfigured default.
- app/: bootstrap and safe-state orchestration.
- drivers/: fail-closed hardware adapter boundary; actual pin mapping pending.
- services/: data preparation, fake-transport API client, health and pairing action gate.
- tests/fakes/: isolated fake board, sensors, clock, IDs, health and HTTP transport.
- tools/simulate.py: executable hardware-free example.
- docs/: architecture, hardware unknowns, Stage 1 test evidence.

Documentation: [Architecture](docs/ARCHITECTURE.md) · [Tests](docs/TESTING.md) · [Stage 1 evidence](docs/STAGE1_EVIDENCE.md).

**Security:** Never commit real device credentials. No production Firebase/Vercel endpoint is contacted by these tests. main remains unchanged until owner review and later merge authorization.
