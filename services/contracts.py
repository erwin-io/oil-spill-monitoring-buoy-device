"""Small client-side data guards. Server Zod schemas remain authoritative."""

SPECTRAL_KEYS = ("f415", "f445", "f480", "f515", "f555", "f590")
CLASSIFICATIONS = ("NORMAL", "PETROLEUM", "INTERFERENCE", "INCONCLUSIVE")
HEALTH_OPTIONAL = (
    "batteryPercent", "batteryVoltage", "charging", "signalStrengthDbm",
    "storage", "sensor", "samplePump", "washPump", "valve", "cellStatus",
    "pendingUploads", "queueDepth", "firmwareVersion", "modelVersion", "errorCodes",
)


def _finite(value, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if value != value or value == float("inf") or value == -float("inf"):
        return False
    return (low is None or value >= low) and (high is None or value <= high)


def _id(value):
    return (isinstance(value, str) and 1 <= len(value) <= 80 and
            all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in value))


def _at(value):
    # Structural offset check only; RTC truth and datetime validity remain pending.
    if not isinstance(value, str) or len(value) < 20 or "T" not in value:
        return False
    if value.endswith("Z"):
        return True
    suffix = value[-6:]
    return (len(suffix) == 6 and suffix[0] in "+-" and suffix[3] == ":" and
            suffix[1:3].isdigit() and suffix[4:6].isdigit() and
            int(suffix[1:3]) <= 23 and int(suffix[4:6]) <= 59)


def validate_measurement(payload):
    required = {"measurementId", "measuredAt", "classification", "confidence", "spectral", "totalFluorescence"}
    allowed = required | {"qualityFlags"}
    if not isinstance(payload, dict) or not required.issubset(payload) or not set(payload).issubset(allowed):
        raise ValueError("Unsupported measurement fields")
    if not _id(payload["measurementId"]) or not _at(payload["measuredAt"]):
        raise ValueError("Invalid measurement ID or timestamp")
    if payload["classification"] not in CLASSIFICATIONS or not _finite(payload["confidence"], 0, 1):
        raise ValueError("Invalid classification or confidence")
    spectral = payload["spectral"]
    if not isinstance(spectral, dict) or set(spectral) != set(SPECTRAL_KEYS):
        raise ValueError("Invalid spectral channels")
    if any(not _finite(spectral[k], 0) for k in SPECTRAL_KEYS) or not _finite(payload["totalFluorescence"], 0):
        raise ValueError("Invalid spectral reading")
    flags = payload.get("qualityFlags", [])
    if (not isinstance(flags, list) or len(flags) > 20 or
            any(not isinstance(x, str) or len(x) > 40 for x in flags)):
        raise ValueError("Invalid quality flags")
    return dict(payload)


def validate_health(payload):
    required = {"healthId", "measuredAt"}
    if not isinstance(payload, dict) or not required.issubset(payload) or not set(payload).issubset(required | set(HEALTH_OPTIONAL)):
        raise ValueError("Unsupported health fields")
    if not _id(payload["healthId"]) or not _at(payload["measuredAt"]):
        raise ValueError("Invalid health ID or timestamp")
    ranges = {"batteryPercent": (0, 100), "batteryVoltage": (0, 8),
              "signalStrengthDbm": (-150, 0), "pendingUploads": (0, 100000), "queueDepth": (0, 100000)}
    for key, (low, high) in ranges.items():
        if key in payload and not _finite(payload[key], low, high):
            raise ValueError("Invalid health field: " + key)
    for key in ("pendingUploads", "queueDepth"):
        if key in payload and not isinstance(payload[key], int):
            raise ValueError("Noninteger health field: " + key)
    if "charging" in payload and not isinstance(payload["charging"], bool):
        raise ValueError("Invalid charging value")
    for key in ("storage", "sensor", "samplePump", "washPump", "valve", "cellStatus"):
        if key in payload and (not isinstance(payload[key], str) or len(payload[key]) > 40):
            raise ValueError("Invalid health state: " + key)
    for key in ("firmwareVersion", "modelVersion"):
        if key in payload and (not isinstance(payload[key], str) or len(payload[key]) > 50):
            raise ValueError("Invalid health version: " + key)
    if "errorCodes" in payload:
        codes = payload["errorCodes"]
        if not isinstance(codes, list) or len(codes) > 30 or any(not isinstance(c, str) or len(c) > 64 for c in codes):
            raise ValueError("Invalid error codes")
    return dict(payload)
