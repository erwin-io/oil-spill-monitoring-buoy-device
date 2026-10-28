"""BlueGuard non-secret configuration. All GPIOs are PROVISIONAL and DISABLED.

Only the future verified physical drivers may control pins. Never store
SIM passwords, X-Device-Key, protected QR claim codes or AP credentials here.
DEFAULT_CONFIG is the unchanged strict, cloud-facing API contract.
"""

# ============================================================
# 1. ESP32-S3 N16R8 BOARD AND RESERVED PIN POLICY
# ============================================================

BOARD_CONFIG = {
    "model": "ESP32-S3-N16R8",
    "pin_plan_status": "PROPOSED_NOT_WIRED",
}
# 26-37 reserved for Flash/Octal PSRAM; 0,3,45,46 are straps;
# 19,20 native USB; 43,44 UART0; 38/48 on-board RGB by revision.
# External JTAG on 39-42 is unavailable when these inputs are used.
ALLOCATABLE_GPIO = (
    1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    17, 18, 21, 39, 40, 41, 42, 47,
)


# ============================================================
# FIRST-BOOT LOCAL SETUP AP — BUILT-IN ESP32 RADIO (NO EXTERNAL GPIO)
# ============================================================
# Setup is not cloud ownership, PAIR or reset. The AP's unique password
# lives on the MCU filesystem only, never in Git or cloud config.
SETUP_AP_CONFIG = {
    "first_boot_enabled": True,
    "session_ms": 15 * 60 * 1000,
    "save_grace_ms": 10 * 1000,
    "max_clients": 2,
}

# ============================================================
# 2. A7670C LTE MODEM — UART + TRANSISTOR CONTROL
# ============================================================

A7670C_CONFIG = {
    "enabled": False,
    "uart_id": 1,
    "tx_pin": 17,       # MCU TX -> modem RXD, voltage translation as required
    "rx_pin": 18,       # MCU RX <- modem TXD, voltage translation as required
    "baudrate": 115200,  # candidate, AT probe before use
    "pwrkey_pin": 47,   # switched circuit; NEVER wire directly to raw PWRKEY
    "reset_pin": None,  # unused; recover over AT / PWRKEY
}


# ============================================================
# 3. AS7341 OPTICAL SENSOR — SHARED I2C BUS
# ============================================================

AS7341_CONFIG = {
    "enabled": False,
    "i2c_id": 0,
    "sda_pin": 8,
    "scl_pin": 9,
    "address": 0x39,
    "int_pin": None,    # polling; no AS7341 interrupt pin reserved
}


# ============================================================
# 4. DS3231 RTC — SAME I2C BUS; NO ALARM IRQ
# ============================================================

RTC_CONFIG = {
    "enabled": False,
    "i2c_id": 0,
    "sda_pin": 8,
    "scl_pin": 9,
    "address": 0x68,
    "alarm_pin": None,   # read RTC after scheduled wakes; revise if IRQ needed
}


# ============================================================
# 5. MICROSD — DEDICATED SPI SIGNALS
# ============================================================

SDCARD_CONFIG = {
    "enabled": False,
    "slot": 2,         # ESP32-S3 MicroPython SPI-mode slot; verify version
    "sck_pin": 12,
    "mosi_pin": 11,
    "miso_pin": 13,
    "cs_pin": 10,
    "detect_pin": 40,  # OPTIONAL socket CD switch; no CD = omit driver use
}


# ============================================================
# 6. ACTUATORS — EXTERNAL DRIVER ONLY, DEFAULT POWER OFF
# ============================================================

ACTUATOR_CONFIG = {
    "enabled": False,
    "sample_pump_pin": 4,
    "wash_pump_pin": 5,
    "dosing_pump_pin": 6,
    "intake_valve_pin": 7,
    "wash_valve_pin": 14,
    "uv_led_pin": 21,   # driver PWM/enable only, NEVER direct 3 W LED drive
}


# ============================================================
# 7. PHYSICAL BUTTONS — PAIR AND SETUP RTC-CAPABLE
# ============================================================

BUTTON_CONFIG = {
    "enabled": False,
    "pair_pin": 15,         # physical PAIR; independent from SETUP/RESET
    "setup_pin": 16,        # physical local AP SETUP
    "reset_action_pin": 41, # logical RESET action; separate from EN reboot
}


# ============================================================
# 8. POWER AND OPTIONAL DIAGNOSTIC INPUTS
# ============================================================

POWER_CONFIG = {
    "enabled": False,
    "battery_adc_pin": 1,  # ADC1, through calibrated voltage divider
    "solar_adc_pin": 2,    # ADC1, through suitable divider
    "leak_pin": 39,        # OPTIONAL digital leak detector, voltage-safe
}
FLOW_CONFIG = {
    "enabled": False,
    "flow_pulse_pin": 42,  # RESERVED if Module F chooses flow sensor
}

# Future charge/current/temperature diagnostics can use the same I2C bus
# with address checks. Four-way intake manifold and coconut filter are
# passive plumbing, not four automatically allocated electrical controls.


# ============================================================
# 8. CLOUD CONFIGURATION DEFAULTS
# ============================================================
# Existing API-facing keys and ranges must not change in this refactor.

DEFAULT_CONFIG = {
    "samplingIntervalMinutes": 15,
    "measurementRepeats": 3,
    "settleSeconds": 3,
    "cleaningCycles": 2,
    "maxCleaningRetries": 3,
    "oilConfidenceThreshold": 0.8,
    "lowBatteryThreshold": 20,
    "configVersion": 1,
}
_LIMITS = {
    "samplingIntervalMinutes": (1, 1440, True),
    "measurementRepeats": (1, 20, True),
    "settleSeconds": (0, 120, True),
    "cleaningCycles": (1, 10, True),
    "maxCleaningRetries": (0, 10, True),
    "oilConfidenceThreshold": (0, 1, False),
    "lowBatteryThreshold": (1, 50, True),
    "configVersion": (1, None, True),
}


def default_config():
    return dict(DEFAULT_CONFIG)


def validate_config(settings):
    """Fail closed on unknown fields/types/ranges. No persistent mutation."""
    if not isinstance(settings, dict) or set(settings) != set(_LIMITS):
        raise ValueError("Configuration keys do not match the Stage 1 contract")
    for name, (minimum, maximum, integral) in _LIMITS.items():
        value = settings[name]
        # bool is an int in Python but is not a valid API numeric value.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Invalid configuration type: " + name)
        if integral and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError("Expected integer: " + name)
        if value != value or value < minimum or (maximum is not None and value > maximum):
            raise ValueError("Invalid configuration range: " + name)
    return dict(settings)


# ============================================================
# 10. SIDE-EFFECT-FREE HARDWARE CONFIG AND PIN AUDIT
# ============================================================

_HARDWARE_DEFAULTS = (
    ("board", BOARD_CONFIG),
    ("a7670c", A7670C_CONFIG),
    ("as7341", AS7341_CONFIG),
    ("rtc", RTC_CONFIG),
    ("sdcard", SDCARD_CONFIG),
    ("actuators", ACTUATOR_CONFIG),
    ("buttons", BUTTON_CONFIG),
    ("power", POWER_CONFIG),
    ("flow", FLOW_CONFIG),
)
_PIN_FIELDS = (
    ("a7670c", ("tx_pin", "rx_pin", "pwrkey_pin", "reset_pin")),
    ("as7341", ("sda_pin", "scl_pin", "int_pin")),
    ("rtc", ("alarm_pin",)),  # SDA/SCL intentionally shared with AS7341
    ("sdcard", ("sck_pin", "mosi_pin", "miso_pin", "cs_pin", "detect_pin")),
    ("actuators", ("sample_pump_pin", "wash_pump_pin", "dosing_pump_pin",
                   "intake_valve_pin", "wash_valve_pin", "uv_led_pin")),
    ("buttons", ("pair_pin", "setup_pin", "reset_action_pin")),
    ("power", ("battery_adc_pin", "solar_adc_pin", "leak_pin")),
    ("flow", ("flow_pulse_pin",)),
)


def default_hardware_config():
    """Return fresh copies of planned, *disabled* hardware configuration."""
    return {name: dict(defaults) for name, defaults in _HARDWARE_DEFAULTS}


def validate_hardware_config(hardware):
    """Audit known ESP32-S3 module pins without initializing any hardware.

    All hardware remains disabled regardless of valid planned GPIO numbers.
    A successful structural check is not an electrical or board-level approval.
    """
    keys = {name for name, _ in _HARDWARE_DEFAULTS}
    if not isinstance(hardware, dict) or set(hardware) != keys:
        raise ValueError("Unknown or missing hardware component")
    clean = {}
    for name, defaults in _HARDWARE_DEFAULTS:
        part = hardware[name]
        if not isinstance(part, dict) or set(part) != set(defaults):
            raise ValueError("Invalid hardware keys: " + name)
        if name == "board":
            if part != defaults:
                raise ValueError("Board or provisional pin-plan status mismatch")
        else:
            if not isinstance(part["enabled"], bool) or part["enabled"]:
                raise ValueError("Hardware disabled pending verification: " + name)
        clean[name] = dict(part)

    modem = clean["a7670c"]
    if (isinstance(modem["uart_id"], bool) or
            not isinstance(modem["uart_id"], int) or
            modem["uart_id"] not in (1, 2)):
        raise ValueError("Invalid modem UART")
    baud = modem["baudrate"]
    if (isinstance(baud, bool) or not isinstance(baud, int)
            or not 1200 <= baud <= 2000000):
        raise ValueError("Invalid modem baudrate")
    if (modem["tx_pin"] is None) != (modem["rx_pin"] is None):
        raise ValueError("Modem TX/RX must both be assigned or both unset")

    as7341 = clean["as7341"]
    rtc = clean["rtc"]
    if ((as7341["sda_pin"], as7341["scl_pin"], as7341["i2c_id"]) !=
            (rtc["sda_pin"], rtc["scl_pin"], rtc["i2c_id"])):
        raise ValueError("AS7341 and RTC must share exactly the I2C bus")
    if as7341["i2c_id"] not in (0, 1) or isinstance(as7341["i2c_id"], bool):
        raise ValueError("Invalid I2C bus")
    for name, part in (("as7341", as7341), ("rtc", rtc)):
        addr = part["address"]
        if isinstance(addr, bool) or not isinstance(addr, int) or not 0x08 <= addr <= 0x77:
            raise ValueError("Invalid I2C address: " + name)
    if as7341["address"] == rtc["address"]:
        raise ValueError("Conflicting I2C addresses")

    sdslot = clean["sdcard"]["slot"]
    if isinstance(sdslot, bool) or sdslot not in (2, 3):
        raise ValueError("Invalid ESP32-S3 SPI SDCard slot")

    used = {}
    allowed = set(ALLOCATABLE_GPIO)
    for component, fields in _PIN_FIELDS:
        for field in fields:
            pin = clean[component][field]
            if pin is None:
                continue
            if isinstance(pin, bool) or not isinstance(pin, int) or pin not in allowed:
                raise ValueError("Unsafe or unavailable GPIO: " + component + "." + field)
            if pin in used:
                raise ValueError("GPIO{} collision: {} / {}.{}".format(
                    pin, used[pin], component, field))
            used[pin] = component + "." + field

    # Shared I2C pins are counted only once above; RTC must match AS7341.
    for name in ("pair_pin", "setup_pin"):
        pin = clean["buttons"][name]
        if pin is None or not 0 <= pin <= 21:
            raise ValueError("PAIR and SETUP require RTC-capable wake GPIO")

    for name in ("battery_adc_pin", "solar_adc_pin"):
        pin = clean["power"][name]
        if pin is None or not 1 <= pin <= 10:
            raise ValueError("Voltage measurement requires ADC1 pin 1..10")

    # Reserve JTAG-capable 39..42 for optional sensing/buttons only; no
    # pump, valve, UV, UART, SPI or PWRKEY outputs on these pads.
    for name in ("sample_pump_pin", "wash_pump_pin", "dosing_pump_pin",
                 "intake_valve_pin", "wash_valve_pin", "uv_led_pin"):
        if clean["actuators"][name] in (39, 40, 41, 42):
            raise ValueError("Unsafe actuator on JTAG-capable GPIO")
    if modem["pwrkey_pin"] in (39, 40, 41, 42):
        raise ValueError("Unsafe modem control on JTAG-capable GPIO")

    return clean
