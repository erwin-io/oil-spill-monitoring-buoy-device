"""BlueGuard firmware configuration: non-secret hardware defaults and cloud settings.

Hardware values are local build-time definitions, never cloud-synced API fields.
The physical A7670C driver is NOT enabled in this Stage 1 refactor.
Do not put device keys, claim codes, SIM credentials or AP passwords here.
"""

# ============================================================
# 1. ESP32-S3 BOARD CONFIGURATION
# ============================================================

BOARD_CONFIG = {
    "model": "ESP32-S3-N16R8",
}


# ============================================================
# 2. A7670C LTE MODEM CONFIGURATION
# ============================================================

A7670C_CONFIG = {
    "enabled": False,
    # UART is reserved for later verified modem integration.
    "uart_id": 1,
    "tx_pin": None,
    "rx_pin": None,
    "baudrate": 115200,
    # Electrical control interface and polarity are not verified.
    "pwrkey_pin": None,
    "reset_pin": None,
}


# ============================================================
# 3. AS7341 SPECTRAL SENSOR CONFIGURATION
# ============================================================
# Deferred until sensor mapping and the driver are verified.


# ============================================================
# 4. RTC CONFIGURATION
# ============================================================
# Deferred until the RTC module and its electrical interface are verified.


# ============================================================
# 5. SDCARD CONFIGURATION
# ============================================================
# Deferred until the storage adapter is implemented.


# ============================================================
# 6. PUMP AND ACTUATOR CONFIGURATION
# ============================================================
# Deferred until output polarity and safe boot states are verified.


# ============================================================
# 7. PHYSICAL BUTTON CONFIGURATION
# ============================================================
# SETUP, PAIR and RESET must remain separate actions; GPIOs unassigned.


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
# 9. HARDWARE CONFIGURATION HELPERS
# ============================================================

def default_hardware_config():
    """Fresh component settings; never share mutable global defaults."""
    return {"board": dict(BOARD_CONFIG), "a7670c": dict(A7670C_CONFIG)}


def validate_hardware_config(hardware):
    """Structural checks only. Never touch machine, GPIO or modem hardware.

    Stage 1 deliberately refuses an enabled modem until its wiring, voltage
    levels, supply and driver implementation have been reviewed.
    """
    if not isinstance(hardware, dict) or set(hardware) != {"board", "a7670c"}:
        raise ValueError("Unknown or missing hardware components")
    board = hardware["board"]
    modem = hardware["a7670c"]
    if not isinstance(board, dict) or set(board) != set(BOARD_CONFIG):
        raise ValueError("Invalid board settings")
    if board["model"] != BOARD_CONFIG["model"]:
        raise ValueError("Unverified board model")
    if not isinstance(modem, dict) or set(modem) != set(A7670C_CONFIG):
        raise ValueError("Invalid A7670C settings")
    if not isinstance(modem["enabled"], bool):
        raise ValueError("A7670C enabled flag must be boolean")
    if modem["enabled"]:
        raise ValueError("A7670C hardware is unverified and cannot be enabled in Stage 1")
    uart_id = modem["uart_id"]
    if isinstance(uart_id, bool) or not isinstance(uart_id, int) or uart_id not in (1, 2):
        raise ValueError("Invalid A7670C UART ID")
    baud = modem["baudrate"]
    if isinstance(baud, bool) or not isinstance(baud, int) or not 1200 <= baud <= 2000000:
        raise ValueError("Invalid A7670C UART baud rate")
    pin_names = ("tx_pin", "rx_pin", "pwrkey_pin", "reset_pin")
    occupied = []
    for name in pin_names:
        pin = modem[name]
        if pin is not None:
            if isinstance(pin, bool) or not isinstance(pin, int) or not 0 <= pin <= 48:
                raise ValueError("Invalid A7670C GPIO: " + name)
            occupied.append(pin)
    if len(occupied) != len(set(occupied)):
        raise ValueError("A7670C GPIO assignments must be distinct")
    if (modem["tx_pin"] is None) != (modem["rx_pin"] is None):
        raise ValueError("A7670C UART TX/RX must both be specified or unassigned")
    # A valid pin number is NOT proof that it is free, safe or voltage-compatible.
    return {"board": dict(board), "a7670c": dict(modem)}
