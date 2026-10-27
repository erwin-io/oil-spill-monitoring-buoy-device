"""Stage 1 fail-closed bootstrap. No sensing, networking or scheduling yet."""
from config import validate_config


class DeviceController:
    def __init__(self, board, settings):
        self.board = board
        self.settings = settings
        self.state = "NEW"

    def start(self):
        # Must occur before accepting configuration or enabling services.
        # Real physical safety requires a verified board implementation (Stage 7).
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
        # SAFE_IDLE is a software state only. No physical safety claim.
        self.state = "SAFE_IDLE"
        return {"state": self.state, "reason": "STAGE1_NO_AUTOMATIC_OPERATIONS"}
