"""Debounced physical PAIR input, no machine import and no synthetic button."""
class PairButton:
    """Active-low physical momentary switch; require RELEASE before first press.

    pin.value() from a verified GPIO input with external/pullup bias.
    """
    def __init__(self,pin,clock,debounce_ms=60):
        if type(debounce_ms)!=int or not 30<=debounce_ms<=500:
            raise ValueError("Invalid pair debounce")
        self.pin=pin
        self.clock=clock
        self.debounce_ms=debounce_ms
        self._raw=1 if pin.value() else 0
        self._stable=self._raw
        self._changed=clock.ticks_ms()
        self._armed=(self._raw==1)

    def poll(self):
        raw=1 if self.pin.value() else 0
        now=self.clock.ticks_ms()
        if raw!=self._raw:
            self._raw=raw
            self._changed=now
        if raw==self._stable or self.clock.ticks_diff(now,self._changed)<self.debounce_ms:
            return False
        self._stable=raw
        if raw==1:
            self._armed=True
            return False
        if self._armed and raw==0:
            self._armed=False
            return True
        return False


def create_physical_pair_button(clock,pin_number=15):
    """Call only after network credentials+verified cloud transport are ready."""
    import machine
    return PairButton(machine.Pin(pin_number,machine.Pin.IN,machine.Pin.PULL_UP),clock)
