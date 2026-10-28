"""Deterministic UART/clock fakes for A7670C offline diagnostics."""


class FakeClock:
    def __init__(self, now=0):
        self.now = now

    def ticks_ms(self):
        return self.now % (1 << 30)

    def ticks_diff(self, now, then):
        half = 1 << 29
        return ((now - then + half) % (1 << 30)) - half

    def sleep_ms(self, ms):
        self.now += ms


class FakeUART:
    """Read responses supplied per command; optionally fragment UART reads."""

    def __init__(self, responses, chunk_size=128, preexisting=b""):
        self.responses = dict(responses)
        self.received = bytearray(preexisting)
        self.chunk_size = chunk_size
        self.writes = []

    def any(self):
        return len(self.received)

    def read(self, n):
        if not self.received:
            return None
        n = min(n, self.chunk_size, len(self.received))
        data = bytes(self.received[:n])
        del self.received[:n]
        return data

    def write(self, data):
        self.writes.append(data)
        command = data.decode().rstrip("\r")
        response = self.responses.get(command, b"")
        if isinstance(response, Exception):
            raise response
        self.received.extend(response)
        return len(data)
