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
        self.assertEqual(self.hardware["a7670c"]["tx_pin"], 17)
        self.assertEqual(self.hardware["a7670c"]["rx_pin"], 18)
        self.assertEqual(self.hardware["a7670c"]["pwrkey_pin"], 47)
        self.assertIsNone(self.hardware["a7670c"]["reset_pin"])
        for component, conf in self.hardware.items():
            if component != "board":
                self.assertIs(conf["enabled"], False)

    def test_hardware_defaults_are_copies(self):
        self.hardware["a7670c"]["tx_pin"] = 15
        self.assertEqual(default_hardware_config()["a7670c"]["tx_pin"], 17)
        self.assertEqual(A7670C_CONFIG["tx_pin"], 17)

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
        self.hardware["a7670c"]["tx_pin"] = None
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)
        self.hardware["a7670c"]["tx_pin"] = 17
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


    def test_unique_gpio_map(self):
        from config import _PIN_FIELDS, ALLOCATABLE_GPIO
        used = {}
        for name, fields in _PIN_FIELDS:
            for field in fields:
                pin = self.hardware[name][field]
                if pin is not None:
                    self.assertNotIn(pin, used, (name, field))
                    used[pin] = name + "." + field
        self.assertEqual(len(used), 23)
        self.assertEqual(set(used), set(ALLOCATABLE_GPIO))

    def test_shared_i2c_and_distinct_sensor_addresses(self):
        a, r = self.hardware["as7341"], self.hardware["rtc"]
        self.assertEqual((a["i2c_id"], a["sda_pin"], a["scl_pin"]),
                         (r["i2c_id"], r["sda_pin"], r["scl_pin"]))
        self.assertEqual((a["address"], r["address"]), (0x39, 0x68))
        self.assertEqual(validate_hardware_config(self.hardware), self.hardware)

    def test_i2c_bus_or_address_collision_is_rejected(self):
        self.hardware["rtc"]["sda_pin"] = 4
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)
        self.hardware["rtc"]["sda_pin"] = 8
        self.hardware["rtc"]["address"] = 0x39
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_critical_reserved_gpio_rejected(self):
        for pin in (0, 3, 19, 20, 26, 33, 35, 36, 37,
                    38, 43, 44, 45, 46, 48):
            with self.subTest(pin=pin):
                settings = default_hardware_config()
                settings["flow"]["flow_pulse_pin"] = pin
                with self.assertRaises(ValueError):
                    validate_hardware_config(settings)

    def test_two_components_cannot_use_same_gpio(self):
        self.hardware["actuators"]["uv_led_pin"] = 17
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_jtag_pads_not_permitted_for_actuators(self):
        self.hardware["flow"]["flow_pulse_pin"] = None
        self.hardware["actuators"]["uv_led_pin"] = 42
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_voltage_inputs_require_adc1(self):
        self.hardware["sdcard"]["detect_pin"] = None
        self.hardware["power"]["solar_adc_pin"] = 40
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_pair_setup_buttons_must_support_rtc_wake(self):
        self.hardware["power"]["leak_pin"] = None
        self.hardware["buttons"]["pair_pin"] = 39
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_no_stage1_peripheral_can_enable(self):
        for component in ("as7341", "rtc", "sdcard", "actuators",
                          "buttons", "power", "flow"):
            with self.subTest(component=component):
                conf = default_hardware_config()
                conf[component]["enabled"] = True
                with self.assertRaises(ValueError):
                    validate_hardware_config(conf)

    def test_wrong_sd_slot_is_rejected(self):
        self.hardware["sdcard"]["slot"] = 0
        with self.assertRaises(ValueError):
            validate_hardware_config(self.hardware)

    def test_pin_plan_cannot_turn_on_physical_devices(self):
        board = FakeBoard()
        self.assertEqual(run(board=board, hardware=self.hardware)["state"], "SAFE_IDLE")
        self.assertEqual(board.calls, ["set_safe_outputs"])

    def test_unbound_board_remains_unconfigured(self):
        self.assertEqual(run()["state"], "UNCONFIGURED")


if __name__ == "__main__":
    unittest.main()
