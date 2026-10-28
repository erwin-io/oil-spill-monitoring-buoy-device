# BlueGuard Buoy — Module D Device Firmware

**Module D resident firmware services now run even without Module E.** The ESP32-S3 runs a monotonic measurement scheduler, periodic heartbeat and live uptime/status reporting with no AS7341/UV sensor. Sensor-dependent opportunities are skipped, never invented as oil readings. The safe A7670C AT driver remains offline-tested; real modem/cloud, pumps and pairing still require electrical integration. The device can now serve a temporary first-boot Wi-Fi setup portal.

## Desktop tests

```powershell
py -3 -m unittest discover -s tests -v
py -3 tools/simulate.py
py -3 main.py
```

`main.run()` returns `RUNNING_OFFLINE`. On MicroPython, `main.py` executes a **resident foreground service** until Ctrl+C; it never drives unverified GPIO or UART, but it starts the built-in ESP32 Wi-Fi AP for unprovisioned devices. The simulator uses in-memory fakes, and its measurements are tagged `SIMULATED_DO_NOT_USE_FOR_SCIENCE`.

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

## First-boot local Wi-Fi setup

When the ESP32-S3 is unprovisioned, it **automatically advertises a short-lived, WPA2-protected BlueGuard-XXXXXX hotspot** on MicroPython boot. Connect your phone, enter the unique AP password printed to the physical USB serial console for this development prototype, and browse http://192.168.4.1/. No F5 or command is needed to start the AP. Local setup currently stores a device label and SIM-provider APN only, without sending data to cloud or claiming ownership.

The portal closes after 15 minutes or shortly after successful save. Once provisioned, automatic AP startup is disabled; verified physical SETUP re-entry and per-device factory credential labeling are still necessary before production shipping. The APN is **not yet sent to an actual A7670C modem**. See [Setup AP guide](docs/SETUP_AP.md).


## Module E — optics and edge ML software

Software is in drivers/as7341.py, services/optics.py, services/calibration.py and services/edge_model.py. Hardware is NOT automatically energized: AS7341 needs a verified I2C bus and the 365-nm UV source needs a protected constant-current driver with a physically verified OFF default. Without real optical assembly and experiment-labeled physical spectra, firmware NEVER claims PETROLEUM or produces scientific measurements.

Desktop-only Random Forest training (requires scikit-learn):

    py -3 -m pip install scikit-learn
    py -3 -m tools.train_edge_model --dataset your_physical_experiment.csv --output out/edge-model-v1 --version optical-v1

The training script requires physical samples and groups by independent experiment/run ID. No bundled ready-to-use oil classifier exists. See docs/MODULE_E_EVIDENCE.md.

## Device cloud pairing core

services/cloud_pairing.py implements the strict server challenge/confirmation state machine using injected certified HTTPS transport, device identity, clock and a physical PAIR event. It cannot start pairing over the setup AP or without a genuine PAIR input. It is currently **not activated by main.py** because real A7670C HTTPS/certificate verification, secure deviceKey provisioning and a verified PAIR button are not complete. This is not yet mobile-app acceptance.


## Production pairing integration boundary

The firmware includes the new physical_pair_button, device_identity and cloud_pairing modules. The resident firmware loop supports injected physical button + pairing service but does NOT construct these by default: it still needs real certificate-verified A7670C HTTPS and factory-provisioned device ID/key. The PAIR input is proposed on GPIO15; never substitute SETUP or EN/reset. The identity file /blueguard-identity.json is a local factory-only record with schema=1, deviceId and deviceKey, excluded from firmware Git/deploy manifest and setup AP. Plain MicroPython flash storage is not itself secure: production secure boot/flash encryption and protected provisioning are pending. No fake keys or fake server confirmations are allowed.


## Autonomous LTE and app pairing

The firmware now includes UART-to-PPP cellular dial, certificate/hostname-verifying HTTPS, physical PAIR input, cloud challenge/confirmation and actual health posting, with boot-time automatic initialization after factory device identity and reviewed trust anchor provisioning. Hardware acceptance is pending. See docs/CELLULAR_PAIRING.md.
