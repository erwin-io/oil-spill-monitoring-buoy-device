"""Stage 1 fail-closed bootstrap. No sensing, networking or scheduling yet."""
from config import default_hardware_config, validate_config, validate_hardware_config


class DeviceController:
    def __init__(self, board, settings, hardware=None):
        self.board = board
        self.settings = settings
        self.hardware = default_hardware_config() if hardware is None else hardware
        self.state = "NEW"

    def start(self):
        # Physical safety still requires a verified board driver (later stage).
        try:
            safe = self.board.set_safe_outputs()
        except Exception:
            self.state = "FAULT"
            return {"state": self.state, "reason": "SAFE_OUTPUT_FAILURE"}
        if safe is not True:
            self.state = "UNCONFIGURED"
            return {"state": self.state, "reason": "NO_VERIFIED_HARDWARE_MAPPING"}
        try:
            self.settings = validate_config(self.settings)
        except ValueError:
            self.state = "FAULT"
            return {"state": self.state, "reason": "INVALID_CONFIG"}
        try:
            self.hardware = validate_hardware_config(self.hardware)
        except ValueError:
            self.state = "FAULT"
            return {"state": self.state, "reason": "INVALID_HARDWARE_CONFIG"}
        # SAFE_IDLE is a fake-board software state only. No modem power, UART
        # or other hardware drivers are ever initialized by this controller.
        self.state = "SAFE_IDLE"
        return {"state": self.state, "reason": "STAGE1_NO_AUTOMATIC_OPERATIONS"}
