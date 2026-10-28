# BlueGuard Buoy — Module D Device Firmware

**Stage 1 hardware bootstrap verified on ESP32-S3 N16R8; Module D development started.** First D41/D42 slice implements a safe, injected A7670C AT-command driver and read-only SIM/LTE status parsing. No physical modem, cellular/HTTPS call, sensor, pump, local AP or cloud pairing is activated.

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

The Windows tool safely pulls main, recognizes WCH CH343 adapters, checks serial identity, uploads **only changed files** from `firmware-manifest.json`, verifies on-device SHA-256 and requests a MicroPython soft reset. You must **release Thonny's COM port before running** the command, then reconnect Thonny to inspect the Shell. **Physical ESP32-S3 upload of 13 previous runtime files was verified through COM15 CH343 (2026-10-28); the new A7670C driver has only desktop tests so far.** Keep loads disconnected. The tool **always displays a numbered list of COM ports**, with a recommended default. Press Enter to accept or enter a number. Use `--port COM7` to bypass the prompt.

Full instructions: [Windows upload + Thonny guide](docs/DEPLOYMENT_THONNY.md).

## Repository organization

- `boot.py`: passive startup; no GPIO initialization.
- `main.py`: explicit cloud/hardware configuration injection and safe unconfigured default.
- `config.py`: **single non-secret configuration location** with a provisional **23-GPIO map** for modem, optics, RTC, SD, pumps/valves/UV, buttons and battery/solar monitoring. All physical hardware remains disabled. Cloud-only DEFAULT_CONFIG is unchanged. See [Hardware pin audit](docs/HARDWARE_MAPPING.md).
- `app/`: bootstrap and safe-state orchestration.
- `drivers/`: fail-closed physical adapter boundary; `modem_a7670c.py` implements allowlisted, bounded AT transactions against injected UART without activating physical pins.
- `services/`: measurement/health preparation, fake-transport API client, physical-PAIR policy, and read-only `network.py` modem status parsing.
- `firmware-manifest.json`: exact allowlist of files permitted on the ESP32; update when runtime modules change (enforced in CI).
- `upload-firmware.bat`: **only BAT launcher**; pulls main and invokes `tools/deploy_firmware.py`, the underlying serial implementation. No cloud calls.
- `tests/fakes/`: simulated board, sources, clock, IDs and HTTP transport.
- `tools/simulate.py`: hardware-free runnable demo.
- `docs/`: architecture, hardware unknowns and test evidence.

Documentation: [Architecture](docs/ARCHITECTURE.md) · [Module D progress](docs/MODULE_D_PROGRESS.md) · [Tests](docs/TESTING.md) · [Stage 1 evidence](docs/STAGE1_EVIDENCE.md).

**Security:** Never commit real device credentials. No production Firebase/Vercel endpoint is contacted by desktop simulations or deployment tools. The device repo currently uses `main` directly by owner authorization; successful tests do not establish physical acceptance.
