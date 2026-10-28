"""D41/D42: hardware-free UART command and SIM/LTE diagnostic tests."""
import unittest

from drivers.modem_a7670c import (
    A7670CModem, ModemCommandError, ModemIOError,
    ModemProtocolError, ModemTimeout,
)
from services.network import NetworkStatusService
from tests.fakes.modem import FakeClock, FakeUART


def uart_for(command, response, **kwargs):
    uart = FakeUART({command: response}, **kwargs)
    return uart, A7670CModem(uart, FakeClock())


class ATDriverTests(unittest.TestCase):
    def test_basic_at_ok(self):
        uart, modem = uart_for("AT", b"\r\nOK\r\n")
        self.assertEqual(modem.command("AT"), [])
        self.assertEqual(uart.writes, [b"AT\r"])

    def test_echo_and_split_line(self):
        uart, modem = uart_for("AT+CSQ", b"AT+CSQ\r\n+CSQ: 25,0\r\nOK\r\n", chunk_size=1)
        self.assertEqual(modem.command("AT+CSQ"), ["+CSQ: 25,0"])

    def test_unsolicited_line_preserved_separately(self):
        uart, modem = uart_for("AT+CSQ", b"\r\n+CMTI: \"SM\",1\r\n+CSQ: 20,0\r\nOK\r\n")
        self.assertIn("+CSQ: 20,0", modem.command("AT+CSQ"))

    def test_stale_response_is_drained_before_command(self):
        uart, modem = uart_for("AT", b"\r\nOK\r\n", preexisting=b"\r\nERROR\r\n")
        self.assertEqual(modem.command("AT"), [])

    def test_modem_error(self):
        _, modem = uart_for("AT", b"\r\nERROR\r\n")
        with self.assertRaises(ModemCommandError):
            modem.command("AT")

    def test_extended_modem_errors_never_echo_secrets(self):
        for response in (b"+CME ERROR: SIM PIN secret\r\n",
                         b"+CMS ERROR: private_data\r\n"):
            with self.subTest(response=response):
                _, modem = uart_for("AT+CPIN?", response)
                with self.assertRaises(ModemCommandError) as caught:
                    modem.command("AT+CPIN?")
                self.assertNotIn("secret", str(caught.exception))
                self.assertNotIn("private_data", str(caught.exception))

    def test_no_response_times_out(self):
        _, modem = uart_for("AT", b"")
        with self.assertRaises(ModemTimeout):
            modem.command("AT", timeout_ms=100)

    def test_timeout_wraparound(self):
        clock = FakeClock((1 << 30) - 20)
        uart = FakeUART({"AT": b""})
        with self.assertRaises(ModemTimeout):
            A7670CModem(uart, clock).command("AT", timeout_ms=150)
        self.assertTrue(clock.now > (1 << 30))

    def test_rejects_write_and_sensitive_commands(self):
        uart, modem = uart_for("AT", b"OK\r\n")
        for command in ("AT+CFUN=1", 'AT+CGDCONT=1,"IP","private"', "AT+CPIN=0000",
                        "AT+HTTPACTION=1", "AT+CGATT=1", "AT+CMGS=123"):
            with self.subTest(command=command):
                with self.assertRaises(ValueError):
                    modem.command(command)
        self.assertEqual(uart.writes, [])

    def test_rejects_invalid_timeouts(self):
        _, modem = uart_for("AT", b"OK\r\n")
        for value in (0, 99, 15001, "100", True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    modem.command("AT", timeout_ms=value)

    def test_large_incomplete_response_fails(self):
        _, modem = uart_for("AT", b"x" * 300)
        with self.assertRaises(ModemProtocolError):
            modem.command("AT")

    def test_incomplete_uart_write_detected(self):
        class Partial(FakeUART):
            def write(self, data):
                return len(data) - 1
        with self.assertRaises(ModemIOError):
            A7670CModem(Partial({}), FakeClock()).command("AT")

    def test_non_ascii_rejected_without_echo(self):
        _, modem = uart_for("AT", b"\xff\r\nOK\r\n")
        with self.assertRaises(ModemProtocolError):
            modem.command("AT")

    def test_urc_backlog_limit(self):
        _, modem = uart_for("AT", b"OK\r\n", preexisting=b"x" * 700)
        with self.assertRaises(ModemProtocolError):
            modem.command("AT")

    def test_only_bounded_response_lines(self):
        _, modem = uart_for("AT", b"data\r\n" * 25 + b"OK\r\n")
        with self.assertRaises(ModemProtocolError):
            modem.command("AT")



class NetworkServiceTests(unittest.TestCase):
    def make_service(self, *, sim=b"+CPIN: READY\r\nOK\r\n",
                     cereg=b"+CEREG: 0,1\r\nOK\r\n",
                     csq=b"+CSQ: 20,0\r\nOK\r\n",
                     attached=b"+CGATT: 1\r\nOK\r\n"):
        uart = FakeUART({
            "AT": b"OK\r\n", "AT+CPIN?": sim,
            "AT+CEREG?": cereg, "AT+CSQ": csq,
            "AT+CGATT?": attached,
        }, chunk_size=3)
        return NetworkStatusService(A7670CModem(uart, FakeClock())), uart

    def test_successful_status_snapshot(self):
        service, uart = self.make_service()
        self.assertEqual(service.snapshot(), {
            "sim": "READY", "registration": "HOME",
            "signalStrengthDbm": -73, "packetAttached": True,
            "httpsReady": False,
        })
        self.assertEqual(uart.writes, [
            b"AT\r", b"AT+CPIN?\r", b"AT+CEREG?\r",
            b"AT+CSQ\r", b"AT+CGATT?\r",
        ])

    def test_roaming_no_signal_no_attach(self):
        service, _ = self.make_service(
            sim=b"+CPIN: SIM PIN\r\nOK\r\n",
            cereg=b'+CEREG: 2,5,"ABCD","12345"\r\nOK\r\n',
            csq=b"+CSQ: 99,99\r\nOK\r\n",
            attached=b"+CGATT: 0\r\nOK\r\n")
        value = service.snapshot()
        self.assertEqual(value["sim"], "LOCKED")
        self.assertEqual(value["registration"], "ROAMING")
        self.assertIsNone(value["signalStrengthDbm"])
        self.assertFalse(value["packetAttached"])
        self.assertNotIn("ABCD", str(value))

    def test_searching_registration(self):
        service, _ = self.make_service(cereg=b"+CEREG: 0,2\r\nOK\r\n")
        self.assertEqual(service.snapshot()["registration"], "SEARCHING")

    def test_bad_signal_is_rejected(self):
        service, _ = self.make_service(csq=b"+CSQ: 40,0\r\nOK\r\n")
        with self.assertRaises(ModemProtocolError):
            service.snapshot()

    def test_bad_registration_is_rejected(self):
        service, _ = self.make_service(cereg=b"+CEREG: 0,garbled\r\nOK\r\n")
        with self.assertRaises(ModemProtocolError):
            service.snapshot()

    def test_missing_response_is_rejected(self):
        service, _ = self.make_service(sim=b"OK\r\n")
        with self.assertRaises(ModemProtocolError):
            service.snapshot()

    def test_at_error_blocks_status(self):
        service, _ = self.make_service(sim=b"ERROR\r\n")
        with self.assertRaises(ModemCommandError):
            service.snapshot()


if __name__ == "__main__":
    unittest.main()
