"""A7670C AT-command boundary, safe for import without machine/UART hardware.

D41 implementation slice: bounded synchronous request/response, injected UART,
timeouts and read-only diagnostics. Not a modem power or HTTPS controller.
Construct only with a verified externally created UART and injected clock.
"""
_ALLOWED_COMMANDS = (
    "AT", "AT+CPIN?", "AT+CEREG?", "AT+CSQ", "AT+CGATT?",
)
_MAX_RESPONSE_BYTES = 2048
_MAX_RESPONSE_LINES = 24
_MAX_LINE_BYTES = 192
_DRAIN_LIMIT = 512


class ModemError(Exception):
    """Modem command was unsuccessful; raw responses are never exposed."""


class ModemTimeout(ModemError):
    pass


class ModemCommandError(ModemError):
    pass


class ModemProtocolError(ModemError):
    pass


class ModemIOError(ModemError):
    pass


class A7670CModem:
    """Injected UART: any(), read(n), write(bytes).

    Clock: ticks_ms(), ticks_diff(now, before), sleep_ms(ms).
    The physical creator must configure UART timeout=0 (non-blocking),
    appropriate baud/voltage conversion, and verified electrical supply.
    """

    def __init__(self, uart, clock, poll_ms=10):
        if uart is None or clock is None:
            raise ValueError("UART and monotonic clock must be injected")
        if type(poll_ms) is not int or not 1 <= poll_ms <= 100:
            raise ValueError("Invalid UART polling interval")
        self._uart = uart
        self._clock = clock
        self._poll_ms = poll_ms

    def _read_available(self):
        try:
            available = self._uart.any()
            if isinstance(available, bool) or not isinstance(available, int) or available < 0:
                raise ModemIOError("Invalid UART.available result")
            if available == 0:
                return b""
            data = self._uart.read(min(available, 128))
        except ModemError:
            raise
        except Exception:
            # Do not log untrusted exception text or possible SIM/credential output.
            raise ModemIOError("UART read failed") from None
        if data is None:
            return b""
        if not isinstance(data, bytes):
            raise ModemIOError("Invalid UART response type")
        return data

    def _drain_stale(self):
        """Discard bounded previous unsolicited/stale input before a new command."""
        total = 0
        while total < _DRAIN_LIMIT:
            data = self._read_available()
            if not data:
                return
            total += len(data)
        if self._uart.any():
            raise ModemProtocolError("UART receive backlog exceeded safe bound")

    def command(self, command, timeout_ms=2500):
        """Issue one allowlisted AT probe and return response lines before OK.

        No arbitrary commands, SIM PIN, APN or HTTP content may pass here.
        A command terminal is OK, ERROR, +CME ERROR or +CMS ERROR.
        """
        if command not in _ALLOWED_COMMANDS:
            raise ValueError("Unapproved AT diagnostic command")
        if type(timeout_ms) is not int or not 100 <= timeout_ms <= 15000:
            raise ValueError("Timeout outside safe diagnostic bounds")
        self._drain_stale()
        wire = (command + "\r").encode()
        try:
            written = self._uart.write(wire)
        except Exception:
            raise ModemIOError("UART write failed") from None
        if written != len(wire):
            raise ModemIOError("Incomplete UART write")

        start = self._clock.ticks_ms()
        pending = b""
        lines = []
        seen_bytes = 0
        while self._clock.ticks_diff(self._clock.ticks_ms(), start) < timeout_ms:
            data = self._read_available()
            if not data:
                self._clock.sleep_ms(self._poll_ms)
                continue
            seen_bytes += len(data)
            if seen_bytes > _MAX_RESPONSE_BYTES:
                raise ModemProtocolError("AT response exceeded byte limit")
            pending += data
            # Normalize CR/LF while retaining incomplete bytes for next read.
            pending = pending.replace(b"\r", b"\n")
            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                if len(raw) > _MAX_LINE_BYTES:
                    raise ModemProtocolError("AT response line too long")
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    line = raw.decode("ascii")
                except (UnicodeError, ValueError):
                    raise ModemProtocolError("Non-ASCII modem response") from None
                if line == command:  # modem echo
                    continue
                if line == "OK":
                    return lines
                if (line == "ERROR" or line.startswith("+CME ERROR:") or
                        line.startswith("+CMS ERROR:")):
                    raise ModemCommandError("Modem returned an AT error")
                lines.append(line)
                if len(lines) > _MAX_RESPONSE_LINES:
                    raise ModemProtocolError("Too many AT response lines")
            if len(pending) > _MAX_LINE_BYTES:
                raise ModemProtocolError("Incomplete AT line too long")
        raise ModemTimeout("Timed out waiting for AT terminal response")
