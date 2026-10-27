"""Public, non-secret defaults compatible with the existing API config.

Never store X-Device-Key, claim codes, AP passwords or production SIM secrets here.
"""
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
