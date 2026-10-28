"""A7670C SIM + LTE + PPP connection on the installed ESP32 UART.

UART is the modem command port until CONNECT; PPP owns it after CONNECT.
This driver never changes raw PWRKEY or touches pumps/LEDs. Serial pins are
board deployment configuration, not proof of voltage translation.
"""
from services.network import _registration, _sim_status, _attached, _signal

class CellularError(Exception):
    pass

class ATLineTerminal:
    def __init__(self, uart, clock, poll_ms=20):
        self.uart=uart
        self.clock=clock
        self.poll_ms=poll_ms
        self.pending=b""

    def _line(self, deadline_ms, start_ms):
        while self.clock.ticks_diff(self.clock.ticks_ms(),start_ms)<deadline_ms:
            if b"\n" in self.pending:
                raw,self.pending=self.pending.split(b"\n",1)
                raw=raw.strip(b"\r ")
                if raw:
                    try:
                        return raw.decode("ascii")
                    except UnicodeError:
                        raise CellularError("Invalid modem response")
            available=self.uart.any()
            if available:
                chunk=self.uart.read(min(available,96))
                if chunk:
                    self.pending+=chunk
                    if len(self.pending)>512:
                        raise CellularError("Modem line too large")
                    continue
            self.clock.sleep_ms(self.poll_ms)
        raise CellularError("Modem response timeout")

    def command(self, command, timeout_ms=5000, terminal="OK"):
        if not isinstance(command,str) or len(command)>180 or "\r" in command or "\n" in command:
            raise ValueError("Invalid AT command")
        if terminal not in ("OK","CONNECT"):
            raise ValueError("Unsupported terminal")
        self.pending=b""
        # UART may contain unsolicited registration messages from idle modem.
        remaining=512
        while self.uart.any() and remaining>0:
            block=self.uart.read(min(self.uart.any(),64))
            remaining-=len(block or b"")
        if self.uart.any():
            raise CellularError("Modem RX buffer not drained")
        payload=(command+"\r").encode()
        if self.uart.write(payload)!=len(payload):
            raise CellularError("UART write incomplete")
        start=self.clock.ticks_ms()
        answer=[]
        while True:
            line=self._line(timeout_ms,start)
            if line==command or not line:
                continue
            if line==terminal or (terminal=="CONNECT" and line.startswith("CONNECT ")):
                return answer
            if line=="ERROR" or line.startswith("+CME ERROR:") or line.startswith("+CMS ERROR:"):
                raise CellularError("Modem rejected AT command")
            if line=="OK" and terminal=="CONNECT":
                # Some modems output OK before CONNECT. Continue waiting.
                continue
            if len(answer)>=16:
                raise CellularError("Modem response exceeded bound")
            answer.append(line)

class A7670CPPP:
    """Inject uart, clock and a PPP factory (e.g. network.PPP).

    APN comes from the pre-existing local setup store. Does not invent
    configuration or modify any cloud ownership state.
    """
    def __init__(self, uart, clock, ppp_factory):
        self.uart=uart
        self.clock=clock
        self.ppp_factory=ppp_factory
        self.ppp=None
        self.signal_dbm=None
        self.status="NOT_CONNECTED"

    def connect(self, apn, register_timeout_ms=45000, ppp_timeout_ms=60000):
        from services.provisioning import validate_settings
        validate_settings({"label":"BlueGuard","apn":apn})
        if self.ppp is not None and self.ppp.isconnected():
            return True
        at=ATLineTerminal(self.uart,self.clock)
        self.status="PROBING"
        at.command("AT")
        at.command("ATE0")
        if _sim_status(at.command("AT+CPIN?"))!="READY":
            self.status="SIM_UNAVAILABLE"
            raise CellularError("SIM is not ready")
        start=self.clock.ticks_ms()
        while True:
            registration=_registration(at.command("AT+CEREG?"))
            if registration in ("HOME","ROAMING"):
                break
            if registration=="DENIED":
                self.status="REGISTRATION_DENIED"
                raise CellularError("LTE registration denied")
            if self.clock.ticks_diff(self.clock.ticks_ms(),start)>=register_timeout_ms:
                self.status="REGISTRATION_TIMEOUT"
                raise CellularError("LTE registration timeout")
            self.clock.sleep_ms(1500)
        self.signal_dbm=_signal(at.command("AT+CSQ"))
        # PDP: configure only the APN value from the approved local form.
        at.command('AT+CGDCONT=1,"IP","'+apn+'"')
        # Dial *99***1#; PPP takes over the UART after CONNECT.
        self.status="DIALING"
        at.command("ATD*99***1#",timeout_ms=30000,terminal="CONNECT")
        self.ppp=self.ppp_factory(self.uart)
        self.ppp.active(True)
        self.ppp.connect()
        start=self.clock.ticks_ms()
        while not self.ppp.isconnected():
            if self.clock.ticks_diff(self.clock.ticks_ms(),start)>=ppp_timeout_ms:
                self.disconnect()
                raise CellularError("PPP connection timeout")
            self.clock.sleep_ms(250)
        self.status="PPP_CONNECTED"
        return True

    def disconnect(self):
        if self.ppp is not None:
            try:
                self.ppp.disconnect()
            except Exception:
                pass
            try:
                self.ppp.active(False)
            except Exception:
                pass
        self.ppp=None
        self.status="NOT_CONNECTED"

def open_board_cellular(clock):
    """No PWRKEY toggle: installed modem must already be correctly powered."""
    import machine
    import network
    from config import A7670C_CONFIG
    pins=A7670C_CONFIG
    uart=machine.UART(pins["uart_id"],baudrate=pins["baudrate"],
                      tx=machine.Pin(pins["tx_pin"]),
                      rx=machine.Pin(pins["rx_pin"]),
                      timeout=0,rxbuf=1024)
    return A7670CPPP(uart,clock,network.PPP)
