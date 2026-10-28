# BlueGuard Buoy — Module D Device Firmware

**Module D resident firmware services now run even without Module E.** The ESP32-S3 runs a monotonic measurement scheduler, periodic heartbeat and live uptime/status reporting with no AS7341/UV sensor. Sensor-dependent opportunities are skipped, never invented as oil readings. The safe A7670C AT driver remains offline-tested; real modem/cloud, pumps, AP and pairing require electrical integration.

## Desktop tests

```powershell
py -3 -m unittest discover -s tests -v
py -3 tools/simulate.py
py -3 main.py
```

`main.run()` returns `RUNNING_OFFLINE`. On MicroPython, `main.py` executes a **resident foreground service** until Ctrl+C; it does not initialize GPIO, network, UART or secrets. The simulator uses in-memory fakes, and its measurements are tagged `SIMULATED_DO_NOT_USE_FOR_SCIENCE`.

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
- `main.py`: active Module D service (no Module E dependency); `main.status()` shows uptime and scheduling counters after Ctrl+C in Thonny.
- `config.py`: **single non-secret configuration location** with a provisional **23-GPIO map** for modem, optics, RTC, SD, pumps/valves/UV, buttons and battery/solar monitoring. All physical hardware remains disabled. Cloud-only DEFAULT_CONFIG is unchanged. See [Hardware pin audit](docs/HARDWARE_MAPPING.md).
- `app/`: safe validation plus a working periodic scheduler and resident heartbeat/uptime runtime.
- `drivers/`: fail-closed physical adapter boundary; `modem_a7670c.py` implements allowlisted, bounded AT transactions against injected UART without activating physical pins.
- `services/`: measurement/health preparation, fake-transport API client, physical-PAIR policy, and read-only `network.py` modem status parsing.
- `firmware-manifest.json`: exact allowlist of files permitted on the ESP32; update when runtime modules change (enforced in CI).
- `upload-firmware.bat`: **only BAT launcher**; pulls main and invokes `tools/deploy_firmware.py`, the underlying serial implementation. No cloud calls.
- `tests/fakes/`: simulated board, sources, clock, IDs and HTTP transport.
- `tools/simulate.py`: hardware-free runnable demo.
- `docs/`: architecture, hardware unknowns and test evidence.

Documentation: [Architecture](docs/ARCHITECTURE.md) · [Module D progress](docs/MODULE_D_PROGRESS.md) · [Tests](docs/TESTING.md) · [Stage 1 evidence](docs/STAGE1_EVIDENCE.md).

**Local smoke test after flashing:** allow the resident loop to print startup messages, press Ctrl+C to return to Thonny REPL, then run `import main; print(main.status())`. It must report `RUNNING_OFFLINE`, `sensor=NOT_INSTALLED`, `modem=NOT_CONNECTED`, and `scientificMeasurements=0`. Press EN to reboot into the service again. This is **local software readiness, not active oil detection or LTE connectivity**.

**Security:** Never commit real device credentials. No production Firebase/Vercel endpoint is contacted by desktop simulations or deployment tools. The device repo currently uses `main` directly by owner authorization; successful tests do not establish physical acceptance.
