# BlueGuard firmware deployment — Windows + Thonny

**Deployment status:** Host-side uploader tested with PC fakes only. Real ESP32-S3 port selection, MicroPython compatibility, file copy, hashing and reset need the Project Owner's Thonny/hardware acceptance. No real device or production cloud access was used to build this tool.

## One-time workstation setup

From PowerShell in the existing repository:

```powershell
cd C:\Development\oil-spill-monitoring-buoy\oil-spill-monitoring-buoy-device
py -3 -m pip install -r tools\requirements-deploy.txt
.\upload-firmware.bat --dry-run
.\upload-firmware.bat --list-ports
```

The installer installs **mpremote and pyserial on the Windows PC**, never on the ESP32. The ESP32-S3 must already have a working MicroPython interpreter; these scripts do **not flash/erase** the MicroPython firmware.

**Thonny serial-port rule:** Thonny and mpremote cannot both own the COM port simultaneously. Disconnect the Thonny backend, switch Thonny temporarily to *Local Python 3*, or close Thonny before uploading. After the script has finished and released the port, reconnect Thonny to *MicroPython (ESP32)* to inspect its Shell. Merely clicking Thonny's Stop button may restart and reconnect its backend; if the COM port remains busy, close Thonny fully.

## Your fixed one-command workflow (from repository root)

```powershell
.\update-and-upload.bat
```

This batch script (1) confirms the current branch is `main`, (2) runs `git pull --ff-only origin main`, (3) refuses local uncommitted firmware or manifest edits, (4) selects exactly one compatible USB-serial port, (5) verifies an ESP32-S3 MicroPython interpreter on that port, (6) uploads **only changed or missing allowlisted files**, (7) verifies SHA-256 hashes on the device, (8) requests a soft reset so on-device `main.py` restarts, and (9) releases the port for Thonny. If any upload/verification step fails, it **does not intentionally reset** the board; rerunning the same command safely rechecks the device's actual files.

**Preferred safe rule:** Run it with pumps, UV LED and other loads disconnected during Stage 1. On current Stage 1 firmware, the expected device boot output is `BlueGuard Stage 1: UNCONFIGURED` (not `SAFE_IDLE`, which belongs to desktop FakeBoard).

## Options

```powershell
.\upload-firmware.bat --list-ports     # identify serial devices; no upload
.\upload-firmware.bat --dry-run       # print allowlisted files; no COM use
.\update-and-upload.bat --port COM7  # use COM7 when multiple possible adapters
.\upload-firmware.bat --force --port COM7     # rewrite all tracked files
.\upload-firmware.bat --no-reset --port COM7  # verify files, do not restart
```

Automatic port selection is intentionally conservative: it considers common Espressif, CP210x, CH340/CH9102 and FTDI USB-serial devices. If multiple eligible ports exist, it stops and requires an explicit `--port COMx` to prevent uploading to the wrong adapter. The identified board is then checked through the serial MicroPython REPL; anything other than **ESP32-S3 MicroPython** is rejected **before writing files**. A generic USB-UART adapter ID cannot by itself prove the attached board is ESP32-S3.

## Upload tracking

`firmware-manifest.json` is the **single allowlist**. It explicitly tracks the on-device Python scripts (and later static web assets). Windows `.bat` files, desktop tests, `docs/`, `.github/`, `.git/`, and secrets are **never uploaded**. The tool calculates local SHA-256 hashes and compares each to the **actual MCU filesystem contents**, so it detects modified or missing files without trusting a stale local cache. The upload order places `main.py` last. It verifies *all* tracked remote file checksums before resetting. No device files are silently deleted, even if removed from the manifest.

**Developer maintenance rule:** When adding, renaming or deleting any runtime module in `app/`, `drivers/` or `services/`, update `firmware-manifest.json` **in the same commit**. The CI test `test_real_repository_runtime_modules_all_in_manifest` fails if runtime `.py` files are omitted or obsolete. The batch files and uploader must be revised if the deployment process itself changes. The user continues to use the **same fixed command** after every merge/push to `main`.

## Safe troubleshooting

- `Missing mpremote / pyserial`: run the one-time pip command above using the *same* `py -3` Python launcher.
- `Multiple eligible serial ports`: run `--list-ports`, inspect Thonny's configured COM port, then run `--port COMx`.
- `Serial command failed`: close/disconnect Thonny, check cable and the MicroPython interpreter (not ROM bootloader), retry.
- `Not ESP32-S3`: inspect board identity and wiring; never bypass the probe just to force an upload.
- `Upload verification failed`: retry without clearing flash; the next run rechecks real file checksums and resends missing/mismatched files. If persistent, inspect MCU flash/storage and serial reliability in Thonny.
- `Local/uncommitted changes`: stash/commit your edits, or restore the main-branch firmware; the helper intentionally deploys only the checked-out, unmodified firmware files.
- If `main.py` raises an exception on reboot, reconnect to Thonny's Shell and capture the full traceback. Do not erase/flash to hide an import or memory error.

## Security/physical limitations

This is a **file synchronizer for an existing MicroPython installation**, not an OTA updater, secure provisioning tool, firmware flash programmer or production deployment mechanism. Transfers occur over physical serial and are not transactional across multiple files; a power failure during upload can leave mixed revisions. It never uploads device keys or secret configuration files. The Stage 1 `UNCONFIGURED` state is a software startup result, not validation of GPIO/pump electrical safety. No physical device outcome has been tested yet.
