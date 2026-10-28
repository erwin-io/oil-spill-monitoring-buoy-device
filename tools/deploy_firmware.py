"""Safe, incremental ESP32-S3 MicroPython file deployer for Windows + Thonny.

Only firmware-manifest.json files are eligible. Uses MicroPython mpremote (not
Thonny's serial backend); Thonny must release the COM port before deployment.
No ESP32 firmware flashing, real cloud calls, or unknown-file deletions.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "firmware-manifest.json"
PROBE_MARKER = "__BLUEGUARD_BOARD__"
HASH_START = "__BLUEGUARD_HASHES_BEGIN__"
HASH_END = "__BLUEGUARD_HASHES_END__"
PORT_RE = re.compile(r"^COM[1-9][0-9]*$", re.IGNORECASE)
KNOWN_USB_IDS = {
    (0x303A, 0x1001),  # Espressif USB Serial/JTAG
    (0x303A, 0x0002),  # Espressif native USB serial variant
    (0x10C4, 0xEA60),  # CP210x USB-UART
    (0x1A86, 0x7523),  # CH340
    (0x1A86, 0x55D3),  # CH343
    (0x1A86, 0x55D2),  # CH342
    (0x1A86, 0x55D4),  # CH9102
    (0x0403, 0x6001),  # FTDI USB-UART
}


class DeployError(Exception):
    """Expected setup, safety or upload error; safe to show to operator."""


def load_manifest(root=ROOT):
    path = root / "firmware-manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DeployError("Cannot read firmware manifest: " + str(exc)) from exc
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise DeployError("Unsupported firmware-manifest.json schema")
    files = data.get("files")
    if not isinstance(files, list) or not files or len(set(map(str, files))) != len(files):
        raise DeployError("Firmware manifest must have a nonempty, unique file list")
    validated = []
    for name in files:
        if not isinstance(name, str) or not name or "\\" in name or ":" in name:
            raise DeployError("Invalid firmware path in manifest")
        path_parts = Path(name).parts
        if name.startswith("/") or any(part in (".", "..", "") for part in path_parts):
            raise DeployError("Unsafe firmware path: " + name)
        permitted = name in ("boot.py", "config.py", "main.py") or (
            len(path_parts) >= 2 and path_parts[0] in ("app", "drivers", "services") and name.endswith(".py")
        ) or (len(path_parts) >= 2 and path_parts[0] == "web" and name.endswith((".html", ".css", ".js")))
        if not permitted:
            raise DeployError("Prohibited firmware path: " + name)
        source = root / name
        if not source.is_file() or source.is_symlink() or any(p.is_symlink() for p in source.parents if root in p.parents):
            raise DeployError("Missing or unsafe local firmware file: " + name)
        validated.append(name)
    if "boot.py" not in validated or "main.py" not in validated:
        raise DeployError("The manifest must include boot.py and main.py")
    return validated


def fingerprint(root, files):
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}


def candidate_ports(ports):
    """Conservative auto-selection. Never choose among multiple candidate boards."""
    found = []
    for p in ports:
        dev = getattr(p, "device", "")
        vid = getattr(p, "vid", None)
        pid = getattr(p, "pid", None)
        description = (getattr(p, "description", "") or "").lower()
        if PORT_RE.fullmatch(dev) and ((vid, pid) in KNOWN_USB_IDS or "esp32" in description or "espressif" in description or "ch343" in description):
            found.append(dev.upper())
    return sorted(set(found), key=lambda s: int(s[3:]))


def choose_port(ports, requested=None):
    available = {getattr(p, "device", "").upper(): p for p in ports}
    if requested:
        requested = requested.upper()
        if not PORT_RE.fullmatch(requested):
            raise DeployError("Invalid Windows COM port. Example: --port COM7")
        if requested not in available:
            raise DeployError("Requested " + requested + " is not currently connected")
        return requested
    matches = candidate_ports(ports)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise DeployError("No supported USB serial adapter found. Try --list-ports or --port COM7")
    raise DeployError("Multiple eligible serial ports: " + ", ".join(matches) + ". Use --port COMx")



def recommended_port(ports):
    """Favor ESP32-specific USB interfaces but never skip the board identity probe."""
    eligible = candidate_ports(ports)
    if not eligible:
        return None

    def rank(name):
        entry = next(p for p in ports if str(getattr(p, "device", "")).upper() == name)
        vid = getattr(entry, "vid", None)
        pid = getattr(entry, "pid", None)
        desc = (getattr(entry, "description", "") or "").lower()
        score = (3 if vid == 0x303A else
                 2 if "esp32" in desc or "espressif" in desc else
                 1 if (vid, pid) in KNOWN_USB_IDS else 0)
        return (-score, int(name[3:]))

    return min(eligible, key=rank)


def prompt_port(ports, *, input_fn=input, say=print):
    """Always list COM ports. Enter accepts the smart suggested default."""
    entries = {}
    for entry in ports:
        name = str(getattr(entry, "device", "")).upper()
        if PORT_RE.fullmatch(name) and name not in entries:
            entries[name] = entry
    if not entries:
        raise DeployError("No COM ports detected. Check your USB data cable and driver.")
    names = sorted(entries, key=lambda name: int(name[3:]))
    suggested = recommended_port(list(entries.values()))
    say("Available COM ports (recommended selection marked *):")
    for index, name in enumerate(names, 1):
        item = entries[name]
        # Reject terminal control characters in USB-provided descriptions.
        desc = "".join(c if 32 <= ord(c) <= 126 else " " for c in
                       str(getattr(item, "description", "") or "Unknown serial device"))[:75].strip()
        label = " * RECOMMENDED" if name == suggested else ""
        say("  [{}] {} - {}{}".format(index, name, desc, label))
    if suggested:
        say("Default: {}. Press Enter to use it, or type a number/COM port.".format(suggested))
    else:
        say("No reliable USB match; select a port number/COM name explicitly.")
    for _ in range(3):
        try:
            response = input_fn("Select COM port [Enter = default, Q = cancel]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            raise DeployError("Port selection cancelled; nothing uploaded") from None
        if response in ("Q", "QUIT", "EXIT"):
            raise DeployError("Port selection cancelled; nothing uploaded")
        if response == "" and suggested:
            return suggested
        if response.isascii() and response.isdigit() and 1 <= int(response) <= len(names):
            return names[int(response) - 1]
        if response in entries:
            return response
        say("Invalid choice. Type a listed number, COMx, or Q to cancel.")
    raise DeployError("Too many invalid choices; nothing uploaded")


def parse_probe(text):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(PROBE_MARKER):
            name, sep, machine = line[len(PROBE_MARKER):].partition("|")
            if not sep or name.strip().lower() != "micropython":
                raise DeployError("Connected board is not a MicroPython device")
            if "ESP32S3" not in machine.upper().replace("-", "").replace("_", ""):
                raise DeployError("Connected board is not verified as ESP32-S3: " + machine)
            return machine
    raise DeployError("Cannot verify ESP32-S3 MicroPython identity from serial response")


def parse_hashes(text, files):
    start = text.find(HASH_START)
    end = text.find(HASH_END, start + len(HASH_START))
    if start < 0 or end < 0:
        raise DeployError("Unable to read deployed firmware hashes from the board")
    body = text[start + len(HASH_START):end].strip()
    try:
        hashes = json.loads(body)
    except ValueError as exc:
        raise DeployError("Invalid board checksum response") from exc
    if not isinstance(hashes, dict) or set(hashes) != set(files):
        raise DeployError("Unexpected board checksum keys")
    for name, sha in hashes.items():
        if sha is not None and (not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None):
            raise DeployError("Invalid board checksum for " + name)
    return hashes


def remote_hash_program(files):
    # This script runs on the MCU. It is read-only; no filesystem mutations.
    return "\n".join([
        "import os, json, binascii",
        "try:",
        "    import hashlib",
        "except ImportError:",
        "    import uhashlib as hashlib",
        "_bg_hashes = {}",
        "for _bg_file in " + repr(files) + ":",
        "    try:",
        "        _bg_sha = hashlib.sha256()",
        "        with open('/' + _bg_file, 'rb') as _bg_stream:",
        "            while True:",
        "                _bg_chunk = _bg_stream.read(1024)",
        "                if not _bg_chunk: break",
        "                _bg_sha.update(_bg_chunk)",
        "        _bg_hashes[_bg_file] = binascii.hexlify(_bg_sha.digest()).decode()",
        "    except OSError:",
        "        _bg_hashes[_bg_file] = None",
        "print('" + HASH_START + "')",
        "print(json.dumps(_bg_hashes))",
        "print('" + HASH_END + "')",
    ])


def remote_mkdir_program(directories):
    return "\n".join([
        "import os",
        "for _bg_dir in " + repr(directories) + ":",
        "    try:",
        "        os.mkdir('/' + _bg_dir)",
        "    except OSError:",
        "        os.stat('/' + _bg_dir)  # Existing directory required; upload will fail on a file",
    ])


def safe_serial_exception(stdout, stderr):
    """Return only an exception class; raw serial text might disclose credentials."""
    kinds = ("ImportError", "ModuleNotFoundError", "AttributeError",
             "SyntaxError", "TypeError", "ValueError", "OSError",
             "FileNotFoundError", "MemoryError", "NotImplementedError",
             "PermissionError")
    for line in reversed((stderr + "\n" + stdout).splitlines()):
        line = line.strip()
        for kind in kinds:
            if line == kind or line.startswith(kind + ":"):
                return kind
    return None


def run_mpremote(port, *commands, runner=subprocess.run, root=ROOT, timeout=75,
                 stage="Serial operation"):
    command = [sys.executable, "-m", "mpremote", "connect", port, *commands]
    try:
        result = runner(command, cwd=root, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DeployError(stage + " timed out/failed on " + port +
                          ". Check USB cable and whether Thonny owns the port.") from exc
    if result.returncode != 0:
        # Never print raw stdout/stderr: the firmware could output device secrets.
        kind = safe_serial_exception(result.stdout or "", result.stderr or "")
        reason = " [device " + kind + "]" if kind else ""
        raise DeployError(stage + " failed on " + port + " (exit " +
                          str(result.returncode) + ")" + reason +
                          ". No intentional device restart.")
    return result.stdout


def check_clean_firmware(root, files, runner=subprocess.run):
    # For the pull-and-upload path, reject working tree/index edits to firmware.
    try:
        res = runner(["git", "status", "--porcelain", "--", *files, "firmware-manifest.json", "tools/deploy_firmware.py", "upload-firmware.bat"], cwd=root, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DeployError("Cannot validate Git firmware state") from exc
    if res.returncode != 0:
        raise DeployError("Cannot validate Git firmware state")
    if res.stdout.strip():
        raise DeployError("Firmware has local/uncommitted modifications; commit/stash or discard before deploying main")


def perform_deploy(root, files, port, *, force=False, no_reset=False, runner=subprocess.run, say=print):
    def mp(stage, *arguments):
        return run_mpremote(port, *arguments, runner=runner, root=root, stage=stage)

    say("[1/5] Verifying MicroPython board identity...")
    machine = parse_probe(mp("Board identity", "exec", "import sys,os; print('" + PROBE_MARKER + "' + sys.implementation.name + '|' + os.uname().machine)"))
    say("Verified board: " + machine + " on " + port)
    say("[2/5] Comparing board files with firmware manifest...")
    expected = fingerprint(root, files)
    observed = parse_hashes(mp("Reading board file checksums", "exec", remote_hash_program(files)), files)
    changed = [name for name in files if force or observed[name] != expected[name]]
    # Never restart main.py in the middle of the update.
    changed = [name for name in changed if name != "main.py"] + (["main.py"] if "main.py" in changed else [])
    if changed:
        say("[3/5] Uploading {} missing/modified files...".format(len(changed)))
        dirs = sorted({"/".join(name.split("/")[:i]) for name in changed for i in range(1, len(name.split("/")))}, key=lambda p: (p.count("/"), p))
        if dirs:
            mp("Preparing device folders", "exec", remote_mkdir_program(dirs))
        for index, name in enumerate(changed, 1):
            say("Uploading {}/{}: {}".format(index, len(changed), name))
            mp("Uploading " + name, "fs", "cp", name, ":/" + name)
        say("[4/5] Verifying device file SHA-256...")
        verified = parse_hashes(mp("Verifying device checksums", "exec", remote_hash_program(files)), files)
        failed = [name for name in files if verified[name] != expected[name]]
        if failed:
            raise DeployError("Upload verification failed for: " + ", ".join(failed) + "; board not intentionally restarted")
        say("SHA-256 verified: all {} manifest files".format(len(files)))
    else:
        say("Already synchronized: all {} firmware files".format(len(files)))
    if not no_reset:
        say("[5/5] Requesting MicroPython soft reset...")
        mp("Restarting MicroPython", "soft-reset")
        say("Device soft-reset requested; main.py should start. Reconnect Thonny to monitor its Shell.")
    else:
        say("--no-reset selected; main.py was not restarted")
    return changed


def list_ports():
    try:
        from serial.tools import list_ports as serial_list_ports
    except ImportError as exc:
        raise DeployError("Missing pyserial. Install once: py -3 -m pip install -r tools\\requirements-deploy.txt") from exc
    return list(serial_list_ports.comports())


def ensure_mpremote():
    try:
        import mpremote  # noqa: F401; no serial connection here
    except ImportError as exc:
        raise DeployError("Missing mpremote. Install once: py -3 -m pip install -r tools\\requirements-deploy.txt") from exc


def main(argv=None, *, root=ROOT):
    p = argparse.ArgumentParser(description="Upload only tracked BlueGuard firmware to ESP32-S3; verify SHA-256 and restart")
    p.add_argument("--port", help="Select COMx directly without the numbered interactive prompt")
    p.add_argument("--list-ports", action="store_true", help="Show connected serial ports without uploading")
    p.add_argument("--dry-run", action="store_true", help="Validate and list local manifest only; no serial access")
    p.add_argument("--force", action="store_true", help="Re-upload all manifest files even if checksums match")
    p.add_argument("--no-reset", action="store_true", help="Do not restart after a verified upload")
    args = p.parse_args(argv)
    try:
        if args.list_ports:
            for port in list_ports():
                print("{} | {} | {:04X}:{:04X}".format(port.device, port.description, port.vid or 0, port.pid or 0))
            return 0
        files = load_manifest(root)
        if args.dry_run:
            print("DRY RUN: no serial connection, no files uploaded")
            for name in files:
                print("  " + name)
            print("{} allowlisted firmware files".format(len(files)))
            return 0
        check_clean_firmware(root, files)
        ensure_mpremote()
        connected = list_ports()
        port = choose_port(connected, args.port) if args.port else prompt_port(connected)
        print("Selected port: " + port)
        changed = perform_deploy(root, files, port, force=args.force, no_reset=args.no_reset)
        print("SUCCESS: {} file(s) uploaded; zero unrelated files changed".format(len(changed)))
        return 0
    except DeployError as exc:
        print("DEPLOY FAILED: " + str(exc), file=sys.stderr)
        print("If Thonny is open: disconnect its backend/close Thonny, run this command, then reopen Thonny.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
