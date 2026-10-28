# BlueGuard Buoy — Module D Device Firmware

**Stage 1: desktop-testable foundation only.** This repository does not yet operate a buoy, modem, sensor, pump, Wi-Fi AP, or actual cloud pairing.

## Desktop tests

```powershell
py -3 -m unittest discover -s tests -v
py -3 tools/simulate.py
py -3 main.py
```

`main.py` defaults to `UNCONFIGURED` and does not initialize GPIO, network, UART or secrets. The simulator uses in-memory fakes, and its measurements are tagged `SIMULATED_DO_NOT_USE_FOR_SCIENCE`.

## ESP32-S3 upload and Thonny debugging (Windows)

**One-time:**

```powershell
py -3 -m pip install -r tools\requirements-deploy.txt
```

**Every future update on main (from this repo):**

```powershell
.\upload-firmware.bat
```

The Windows tool safely pulls main, checks serial identity, uploads **only changed files** from `firmware-manifest.json`, verifies on-device SHA-256 and requests a MicroPython soft reset. You must **release Thonny's COM port before running** the command, then reconnect Thonny to inspect the Shell. **No hardware deployment has yet been physically tested**; start with loads disconnected. The tool **always displays a numbered list of COM ports**, with a recommended default. Press Enter to accept or enter a number. Use `--port COM7` to bypass the prompt.

Full instructions: [Windows upload + Thonny guide](docs/DEPLOYMENT_THONNY.md).

## Repository organization

- `boot.py`: passive startup; no GPIO initialization.
- `main.py`: explicit cloud/hardware configuration injection and safe unconfigured default.
- `config.py`: **single non-secret configuration location** with a provisional **23-GPIO map** for modem, optics, RTC, SD, pumps/valves/UV, buttons and battery/solar monitoring. All physical hardware remains disabled. Cloud-only DEFAULT_CONFIG is unchanged. See [Hardware pin audit](docs/HARDWARE_MAPPING.md).
- `app/`: bootstrap and safe-state orchestration.
- `drivers/`: fail-closed physical adapter boundary; actual pin mapping pending.
- `services/`: measurement/health prep, fake-transport API client, and physical-PAIR policy gate.
- `firmware-manifest.json`: exact allowlist of files permitted on the ESP32; update when runtime modules change (enforced in CI).
- `upload-firmware.bat`: **only BAT launcher**; pulls main and invokes `tools/deploy_firmware.py`, the underlying serial implementation. No cloud calls.
- `tests/fakes/`: simulated board, sources, clock, IDs and HTTP transport.
- `tools/simulate.py`: hardware-free runnable demo.
- `docs/`: architecture, hardware unknowns and test evidence.

Documentation: [Architecture](docs/ARCHITECTURE.md) · [Tests](docs/TESTING.md) · [Stage 1 evidence](docs/STAGE1_EVIDENCE.md).

**Security:** Never commit real device credentials. No production Firebase/Vercel endpoint is contacted by desktop simulations or deployment tools. The device repo currently uses `main` directly by owner authorization; successful tests do not establish physical acceptance.
