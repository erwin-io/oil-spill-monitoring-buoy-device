"""Stage 1 passive boot hook. No GPIO, filesystem, radio or modem initialization."""


def preflight():
    """Report only software bootstrap readiness; not a hardware self-test."""
    return {"stage": 1, "hardware_initialized": False, "network_initialized": False}
