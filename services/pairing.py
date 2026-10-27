"""Stage 1 policy boundary, NOT a cloud pairing implementation.

A future pairing service may call the backend only after separate physical PAIR.
The local SETUP and RESET actions cannot unlock pairing here.
"""


class PairingGate:
    def __init__(self):
        self._armed = False

    def authorize(self, action, physically_pressed=False):
        self._armed = (action == "PAIR" and physically_pressed is True)
        return self._armed

    def consume(self):
        was_armed = self._armed
        self._armed = False
        return was_armed
