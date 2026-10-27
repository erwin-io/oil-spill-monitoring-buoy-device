"""Default board boundary: cannot energize unspecified pins or peripherals."""


class UnboundBoard:
    def set_safe_outputs(self):
        # GPIO mapping is not approved; do not import machine or set pins.
        return False
