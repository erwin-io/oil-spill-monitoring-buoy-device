"""Read-only D42 SIM/LTE status assessment atop the injected A7670C driver.

No credentials, APN provisioning, network attachment, socket or cloud requests.
The response only contains sanitized non-identifying modem observations.
"""
from drivers.modem_a7670c import ModemProtocolError


def _one_line(lines, prefix):
    matching = [line[len(prefix):].strip() for line in lines
                if line.startswith(prefix)]
    if len(matching) != 1:
        raise ModemProtocolError("Unexpected AT diagnostic response")
    return matching[0]


def _integer(value, low, high):
    if not value.isdigit():
        raise ModemProtocolError("Malformed cellular diagnostic number")
    number = int(value)
    if number < low or number > high:
        raise ModemProtocolError("Cellular diagnostic value out of range")
    return number


def _sim_status(lines):
    raw = _one_line(lines, "+CPIN:")
    if raw == "READY":
        return "READY"
    if raw in ("SIM PIN", "SIM PUK", "PH-NET PIN"):
        return "LOCKED"
    return "UNKNOWN"


def _registration(lines):
    fields = _one_line(lines, "+CEREG:").split(",")
    if len(fields) == 1:
        status = _integer(fields[0].strip(), 0, 10)
    else:
        # AT+CEREG? returns <n>,<stat>[,...], where trailing values
        # can contain location identifiers. They must not be reported.
        _integer(fields[0].strip(), 0, 5)
        status = _integer(fields[1].strip(), 0, 10)
    if status == 1:
        return "HOME"
    if status == 5:
        return "ROAMING"
    if status == 2:
        return "SEARCHING"
    if status == 3:
        return "DENIED"
    if status == 0:
        return "NOT_REGISTERED"
    return "UNKNOWN"


def _signal(lines):
    fields = _one_line(lines, "+CSQ:").split(",")
    if len(fields) != 2:
        raise ModemProtocolError("Malformed CSQ response")
    rssi = _integer(fields[0].strip(), 0, 99)
    ber = _integer(fields[1].strip(), 0, 99)
    if rssi > 31 and rssi != 99:
        raise ModemProtocolError("Unsupported CSQ RSSI")
    if ber > 7 and ber != 99:
        raise ModemProtocolError("Unsupported CSQ BER")
    # 99 means signal measurement unavailable, not -113 dBm.
    return None if rssi == 99 else -113 + (2 * rssi)


def _attached(lines):
    state = _one_line(lines, "+CGATT:")
    return bool(_integer(state, 0, 1))


class NetworkStatusService:
    def __init__(self, modem):
        self._modem = modem

    def snapshot(self):
        """Collect diagnostic status. Never initiates registration or data."""
        self._modem.command("AT")
        sim = _sim_status(self._modem.command("AT+CPIN?"))
        reg = _registration(self._modem.command("AT+CEREG?"))
        dbm = _signal(self._modem.command("AT+CSQ"))
        attached = _attached(self._modem.command("AT+CGATT?"))
        return {
            "sim": sim,
            "registration": reg,
            "signalStrengthDbm": dbm,
            "packetAttached": attached,
            "httpsReady": False,  # LTE status alone never proves TLS readiness.
        }
