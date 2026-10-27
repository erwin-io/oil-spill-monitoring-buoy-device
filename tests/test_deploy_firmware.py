"""All deployment tests are PC-only; no COM ports or sockets are opened."""
import hashlib
import json
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import deploy_firmware as d


class FakeMpremoteRunner:
    def __init__(self, root, *, machine="Generic ESP32S3 module with ESP32S3", fail_copy=None):
        self.root = root
        self.remote = {}
        self.machine = machine
        self.fail_copy = fail_copy
        self.calls = []
        self.resets = 0

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if command[:3] == ["git", "status", "--porcelain"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        self_test = command[5:]
        if self_test[:1] == ["exec"]:
            script = self_test[1]
            if d.PROBE_MARKER in script:
                return subprocess.CompletedProcess(command, 0, d.PROBE_MARKER + "micropython|" + self.machine + "\n", "")
            if d.HASH_START in script:
                filenames = list(json.loads(self.root.joinpath("firmware-manifest.json").read_text())["files"])
                hashes = {n: hashlib.sha256(self.remote[n]).hexdigest() if n in self.remote else None for n in filenames}
                return subprocess.CompletedProcess(command, 0, d.HASH_START + "\n" + json.dumps(hashes) + "\n" + d.HASH_END + "\n", "")
            return subprocess.CompletedProcess(command, 0, "", "")
        if self_test[:2] == ["fs", "cp"]:
            name = self_test[2]
            if name == self.fail_copy:
                return subprocess.CompletedProcess(command, 1, "", "failed")
            self.remote[name] = (self.root / name).read_bytes()
            return subprocess.CompletedProcess(command, 0, "", "")
        if self_test == ["soft-reset"]:
            self.resets += 1
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError("Unexpected mock mpremote command: " + repr(command))


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = ["boot.py", "config.py", "services/telemetry.py", "main.py"]
        for name in self.files:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# " + name + "\n")
        self.make_manifest()

    def make_manifest(self, files=None):
        self.root.joinpath("firmware-manifest.json").write_text(json.dumps({"schemaVersion": 1, "files": self.files if files is None else files}))

    def test_manifest_explicit_file_list(self):
        self.assertEqual(d.load_manifest(self.root), self.files)

    def test_manifest_rejects_escaping_root(self):
        self.make_manifest(self.files + ["../private.key"])
        with self.assertRaises(d.DeployError):
            d.load_manifest(self.root)

    def test_manifest_rejects_unknown_root(self):
        path = self.root / "secrets.py"
        path.write_text("SECRET='never upload'")
        self.make_manifest(self.files + ["secrets.py"])
        with self.assertRaises(d.DeployError):
            d.load_manifest(self.root)

    def test_manifest_rejects_duplicates(self):
        self.make_manifest(self.files + ["main.py"])
        with self.assertRaises(d.DeployError):
            d.load_manifest(self.root)

    def test_manifest_rejects_missing_file(self):
        (self.root / "main.py").unlink()
        with self.assertRaises(d.DeployError):
            d.load_manifest(self.root)

    def test_manifest_rejects_symlink(self):
        (self.root / "main.py").unlink()
        (self.root / "main.py").symlink_to(self.root / "config.py")
        with self.assertRaises(d.DeployError):
            d.load_manifest(self.root)

    def test_real_repository_runtime_modules_all_in_manifest(self):
        files = set(d.load_manifest(d.ROOT))
        expected = {"boot.py", "config.py", "main.py"}
        for folder in ("app", "drivers", "services"):
            expected.update(str(f.relative_to(d.ROOT)).replace("\\", "/") for f in (d.ROOT / folder).rglob("*.py"))
        self.assertEqual(files & expected, expected, "Update firmware-manifest.json when adding firmware modules")
        self.assertEqual({n for n in files if n.endswith(".py")}, expected, "Remove obsolete module entries")

    def test_dry_run_opens_no_serial_port(self):
        with patch.object(d, "list_ports", side_effect=AssertionError("COM should never be touched")):
            self.assertEqual(d.main(["--dry-run"], root=self.root), 0)

    def test_deploy_only_missing_files_and_verify(self):
        runner = FakeMpremoteRunner(self.root)
        output = []
        changed = d.perform_deploy(self.root, self.files, "COM7", runner=runner, say=output.append)
        self.assertEqual(changed[-1], "main.py")
        self.assertEqual(set(runner.remote), set(self.files))
        self.assertEqual(runner.resets, 1)
        self.assertTrue(any("verified" in line.lower() for line in output))

    def test_second_deploy_skips_all_unchanged_files(self):
        runner = FakeMpremoteRunner(self.root)
        d.perform_deploy(self.root, self.files, "COM7", runner=runner, say=lambda x: None)
        runner.calls.clear()
        changed = d.perform_deploy(self.root, self.files, "COM7", runner=runner, say=lambda x: None)
        self.assertEqual(changed, [])
        self.assertFalse(any("cp" in call for call in runner.calls))
        self.assertEqual(runner.resets, 2)

    def test_only_changed_file_is_uploaded(self):
        runner = FakeMpremoteRunner(self.root)
        d.perform_deploy(self.root, self.files, "COM7", runner=runner, say=lambda x: None)
        (self.root / "services/telemetry.py").write_text("# updated\n")
        runner.calls.clear()
        changed = d.perform_deploy(self.root, self.files, "COM7", runner=runner, say=lambda x: None)
        self.assertEqual(changed, ["services/telemetry.py"])

    def test_missing_remote_file_restored_even_if_local_unchanged(self):
        runner = FakeMpremoteRunner(self.root)
        d.perform_deploy(self.root, self.files, "COM7", runner=runner, say=lambda x: None)
        del runner.remote["config.py"]
        self.assertEqual(d.perform_deploy(self.root, self.files, "COM7", runner=runner, say=lambda x: None), ["config.py"])

    def test_force_resends_all(self):
        runner = FakeMpremoteRunner(self.root)
        d.perform_deploy(self.root, self.files, "COM7", runner=runner, say=lambda x: None)
        self.assertEqual(len(d.perform_deploy(self.root, self.files, "COM7", runner=runner, force=True, say=lambda x: None)), len(self.files))

    def test_failed_copy_never_restarts(self):
        runner = FakeMpremoteRunner(self.root, fail_copy="services/telemetry.py")
        with self.assertRaises(d.DeployError):
            d.perform_deploy(self.root, self.files, "COM7", runner=runner, say=lambda x: None)
        self.assertEqual(runner.resets, 0)

    def test_wrong_board_is_rejected_before_upload(self):
        runner = FakeMpremoteRunner(self.root, machine="ESP8266")
        with self.assertRaises(d.DeployError):
            d.perform_deploy(self.root, self.files, "COM7", runner=runner, say=lambda x: None)
        self.assertEqual(runner.remote, {})

    def test_no_reset_option(self):
        runner = FakeMpremoteRunner(self.root)
        d.perform_deploy(self.root, self.files, "COM7", runner=runner, no_reset=True, say=lambda x: None)
        self.assertEqual(runner.resets, 0)


class SerialSelectionTests(unittest.TestCase):
    def fake_port(self, device, vid, pid, description=""):
        return types.SimpleNamespace(device=device, vid=vid, pid=pid, description=description)

    def test_single_esp_serial_auto_selected(self):
        ports = [self.fake_port("COM3", None, None, "Bluetooth"), self.fake_port("COM7", 0x303A, 0x1001)]
        self.assertEqual(d.choose_port(ports), "COM7")

    def test_multiple_usb_adapters_fail_closed(self):
        ports = [self.fake_port("COM7", 0x303A, 0x1001), self.fake_port("COM9", 0x10C4, 0xEA60)]
        with self.assertRaises(d.DeployError):
            d.choose_port(ports)
        self.assertEqual(d.choose_port(ports, "COM9"), "COM9")

    def test_missing_manual_port_rejected(self):
        with self.assertRaises(d.DeployError):
            d.choose_port([], "COM7")

    def test_malicious_port_string_rejected(self):
        with self.assertRaises(d.DeployError):
            d.choose_port([self.fake_port("COM7", 0x303A, 0x1001)], "COM7 & del files")

    def test_serial_parser_requires_known_device(self):
        with self.assertRaises(d.DeployError):
            d.parse_probe(d.PROBE_MARKER + "micropython|Generic ESP32")

    def test_hash_response_rejects_unexpected_file(self):
        value = d.HASH_START + "\n" + json.dumps({"unknown.py": None}) + "\n" + d.HASH_END
        with self.assertRaises(d.DeployError):
            d.parse_hashes(value, ["main.py"])


if __name__ == "__main__":
    unittest.main()
