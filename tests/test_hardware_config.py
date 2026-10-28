"""Desktop-only central hardware configuration tests; no physical GPIO is used."""
import unittest
from config import (
    A7670C_CONFIG,
    BOARD_CONFIG,
    default_config,
    default_hardware_config,
    validate_config,
    validate_hardware_config,
)
from main import run
from tests.fakes.device import FakeBoard


class HardwareConfigTests(unittest.TestCase):
    def setUp(self):
        self.hardware = default_hardware_config()

    def test_default_is_valid_and_modem_is_disabled(self):
        self.assertEqual(validate_hardware_config(self.hardware), self.hardware)
        self.assertEqual(self.hardware["board"], BOARD_CONFIG)
        self.assertEqual(self.hardware["a7670c"], A7670C_CONFIG)
        self.assertFalse(self.hardware["a7670c"]["enabled"])
        for key in ("tx_pin", "rx_pin", "pwrkey_pin", "reset_pin"):
            self.assertIsNone(self.hardware["a7670c"][key])

    def test_hardware_defaults_are_copies(self):
        self.hardware["a7670c"]["tx_pin"] = 17
        self.assertIsNone(default_hardware_config()["a7670c"]["tx_pin"])
        self.assertIsNone(A7670C_CONFIG["tx_pin"])

    def test_cloud_config_stays_api_only(self):
        config = default_config()
        self.assertNotIn("a7670c", config)
        self.assertNotIn("board", config)
        self.assertEqual(validate_config(config), config)
        config["a7670c"] = self.hardware["a7670c"]
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_no_early_modem_enable(self):
        self.hardware["a7670c"]["enabled"] = True
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_enabled_must_be_boolean(self):
        self.hardware["a7670c"]["enabled"] = 1
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_unknown_hardware_component_is_rejected(self):
        self.hardware["relay"] = {}
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_unknown_modem_setting_is_rejected(self):
        self.hardware["a7670c"]["apn_password"] = "never here"
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_wrong_board_model_is_rejected(self):
        self.hardware["board"]["model"] = "ESP32"
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_invalid_uart_id_and_baud_are_rejected(self):
        for key, value in (("uart_id", True), ("uart_id", 0),
                           ("baudrate", False), ("baudrate", -9600),
                           ("baudrate", 3000000)):
            with self.subTest(key=key, value=value):
                hardware = default_hardware_config()
                hardware["a7670c"][key] = value
                with self.assertRaises(ValueError):
                    validate_hardware_config(hardware)

    def test_invalid_pin_values_are_rejected(self):
        for invalid in (True, -1, 49, 17.5, "17"):
            with self.subTest(invalid=invalid):
                hardware = default_hardware_config()
                hardware["a7670c"]["pwrkey_pin"] = invalid
                with self.assertRaises(ValueError):
                    validate_hardware_config(hardware)

    def test_uart_pair_and_conflicting_pins_are_rejected(self):
        self.hardware["a7670c"]["tx_pin"] = 17
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)
        self.hardware["a7670c"]["rx_pin"] = 17
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_proposed_disabled_pins_are_not_activated(self):
        self.hardware["a7670c"]["tx_pin"] = 17
        self.hardware["a7670c"]["rx_pin"] = 18
        self.assertEqual(validate_hardware_config(self.hardware), self.hardware)
        board = FakeBoard()
        result = run(board=board, hardware=self.hardware)
        self.assertEqual(result["state"], "SAFE_IDLE")
        self.assertEqual(board.calls, ["set_safe_outputs"])

    def test_enabled_modem_never_initializes_even_with_fake_safe_board(self):
        self.hardware["a7670c"]["enabled"] = True
        board = FakeBoard()
        self.assertEqual(run(board=board, hardware=self.hardware),
                         {"state": "FAULT", "reason": "INVALID_HARDWARE_CONFIG"})
        self.assertEqual(board.calls, ["set_safe_outputs"])

    def test_unbound_board_remains_unconfigured(self):
        self.assertEqual(run()["state"], "UNCONFIGURED")


if __name__ == "__main__":
    unittest.main()
