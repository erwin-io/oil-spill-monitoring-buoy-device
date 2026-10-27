import builtins
import importlib
import unittest
from unittest.mock import patch

import boot
import main
from app.controller import DeviceController
from config import default_config
from tests.fakes.device import FakeBoard


class StartupTests(unittest.TestCase):
    def test_boot_is_passive(self):
        self.assertEqual(boot.preflight(), {"stage": 1, "hardware_initialized": False, "network_initialized": False})

    def test_default_start_does_not_touch_hardware_or_network(self):
        self.assertEqual(main.run()["state"], "UNCONFIGURED")

    def test_fake_safe_board_reaches_safe_idle(self):
        board = FakeBoard()
        self.assertEqual(main.run(board=board)["state"], "SAFE_IDLE")
        self.assertEqual(board.calls, ["set_safe_outputs"])

    def test_unverified_board_prevents_active_operation(self):
        self.assertEqual(main.run(board=FakeBoard(False))["state"], "UNCONFIGURED")

    def test_invalid_config_never_starts(self):
        board = FakeBoard()
        settings = default_config()
        settings["samplingIntervalMinutes"] = 0
        self.assertEqual(DeviceController(board, settings).start()["state"], "FAULT")
        self.assertEqual(board.calls, ["set_safe_outputs"])

    def test_board_exception_fail_closed(self):
        class Broken:
            def set_safe_outputs(self):
                raise RuntimeError("hardware unavailable")
        self.assertEqual(main.run(board=Broken())["state"], "FAULT")

    def test_imports_do_not_require_machine_or_network(self):
        original = builtins.__import__
        def deny(name, *args, **kwargs):
            if name.split(".")[0] in ("machine", "network", "socket", "urequests", "requests"):
                raise AssertionError("Forbidden import: " + name)
            return original(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=deny):
            for name in ("main", "boot", "config", "app.controller", "drivers.unbound",
                         "services.contracts", "services.telemetry", "services.health",
                         "services.api_client", "services.pairing"):
                importlib.reload(importlib.import_module(name))
            self.assertEqual(main.run()["state"], "UNCONFIGURED")


if __name__ == "__main__":
    unittest.main()
