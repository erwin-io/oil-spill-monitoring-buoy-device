"""Module D software bootstrap, independent of optional optical hardware."""
from config import default_hardware_config, validate_config, validate_hardware_config


class DeviceController:
    def __init__(self, board, settings, hardware=None):
        self.board = board
        self.settings = settings
        self.hardware = default_hardware_config() if hardware is None else hardware
        self.state = "NEW"

    def start(self):
        # Require an attempt to enter safe outputs BEFORE parsing configs.
        # UnboundBoard returns False: safe to run *software only*; never
        # activate any GPIO or misrepresent real hardware as verified.
        try:
            safe = self.board.set_safe_outputs()
        except Exception:
            self.state = "FAULT"
            return {"state": self.state, "reason": "SAFE_OUTPUT_FAILURE"}
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
        # Always available without Module E: scheduler/uptime/diagnostics.
        # Not equivalent to physical modem, cloud or oil-monitoring readiness.
        self.state = "RUNNING_OFFLINE"
        reason = "SENSOR_PENDING_HARDWARE_UNBOUND" if safe is not True else "SENSOR_PENDING"
        return {"state": self.state, "reason": reason,
                "sensor": "NOT_INSTALLED", "modem": "NOT_CONNECTED",
                "cloud": "OFFLINE", "actuators": "DISABLED"}
