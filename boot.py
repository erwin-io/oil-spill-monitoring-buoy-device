"""Module D passive boot hook; no GPIO, UART or Wi-Fi side effects."""


def preflight():
    """Software boot hook only; not proof of any peripheral."""
    return {"stage": "MODULE_D", "hardware_initialized": False,
            "network_initialized": False}
