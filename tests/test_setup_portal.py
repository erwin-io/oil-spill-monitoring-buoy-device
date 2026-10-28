"""Device setup AP: pure desktop fakes, no real Wi-Fi or cloud traffic."""
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from services.provisioning import ProvisioningStore, validate_settings
from services.setup_portal import SetupPortal, parse_form, AP_TIMEOUT_MS, SAVED_GRACE_MS


class Clock:
    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, later, earlier):
        return later - earlier


class FakeAP:
    def __init__(self, fail=False):
        self.on = False
        self.configured = None
        self.calls = []
        self.fail = fail
    def config(self, **kwargs):
        if self.fail:
            raise RuntimeError("WiFi unavailable")
        self.configured = kwargs
        self.calls.append(kwargs)
    def active(self, on=None):
        if on is not None:
            self.on = on
        return self.on
    def ifconfig(self):
        return ("192.168.4.1", "255.255.255.0", "192.168.4.1", "192.168.4.1")


class Client:
    def __init__(self, request):
        self.request = bytearray(request)
        self.response = b""
        self.closed = False
    def settimeout(self, amount):
        self.timeout = amount
    def recv(self, amount):
        part = bytes(self.request[:amount])
        del self.request[:amount]
        return part
    def sendall(self, data):
        self.response += data
    def close(self):
        self.closed = True


class Listener:
    def __init__(self, clients):
        self.clients = clients
        self.closed = False
    def setsockopt(self, *args):
        pass
    def bind(self, address):
        self.address = address
    def listen(self, count):
        self.limit = count
    def setblocking(self, flag):
        self.nonblocking = not flag
    def accept(self):
        if not self.clients:
            raise OSError(11, "Would block")
        return self.clients.pop(0), ("192.168.4.2", 1000)
    def close(self):
        self.closed = True


class FakeSockets:
    SOL_SOCKET = 1
    SO_REUSEADDR = 2
    def __init__(self):
        self.clients = []
        self.listener = Listener(self.clients)
    def socket(self):
        return self.listener


def http(method, path, body=b"", host="192.168.4.1", origin=None,
         content_type="application/x-www-form-urlencoded"):
    headers = ("%s %s HTTP/1.1\r\nHost: %s\r\n" % (method, path, host))
    if origin is not None:
        headers += "Origin: %s\r\n" % origin
    if method == "POST":
        headers += ("Content-Type: %s\r\nContent-Length: %d\r\n" %
                    (content_type, len(body)))
    return headers.encode() + b"\r\n" + body


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = ProvisioningStore(str(self.root / "settings.json"),
                                       str(self.root / "access.key"))

    def test_first_boot_unprovisioned(self):
        self.assertIsNone(self.store.load())

    def test_ap_key_generated_and_persists(self):
        password = self.store.password()
        self.assertEqual(len(password), 16)
        self.assertEqual(self.store.password(), password)
        self.assertNotIn("password", str(self.store.load()))

    def test_settings_saved_and_loaded_once(self):
        desired = {"label": "North Buoy", "apn": "internet.globe.com.ph"}
        self.store.save_once(desired)
        self.assertEqual(self.store.load(), desired)
        with self.assertRaises(ValueError):
            self.store.save_once({"label": "Hacked", "apn": "evil"})

    def test_invalid_apn_and_credential_fields_rejected(self):
        for settings in (
            {"label": "test", "apn": "bad;command"},
            {"label": "<script>", "apn": "internet"},
            {"label": "test", "apn": "ok", "deviceKey": "secret"},
            {"label": "test", "apn": ""},
        ):
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):
                    validate_settings(settings)

    def test_corrupted_record_does_not_reopen_provisioning(self):
        (self.root / "settings.json").write_text("corrupted")
        with self.assertRaises(ValueError):
            self.store.load()


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.page = self.root / "setup.html"
        self.page.write_text("<h1>{{SSID}}</h1><input value='{{TOKEN}}'>")
        self.store = ProvisioningStore(str(self.root / "settings.json"),
                                       str(self.root / "ap.key"))
        self.ap = FakeAP()
        self.sockets = FakeSockets()
        self.clock = Clock()
        self.portal = SetupPortal(self.ap, self.sockets, self.clock,
                                  b"\x12\x34\x56\x78",
                                  store=self.store, template_path=str(self.page))

    def send(self, request):
        client = Client(request)
        self.sockets.clients.append(client)
        self.portal.tick()
        self.assertTrue(client.closed)
        return client.response

    def test_start_first_boot_uses_protected_unique_hotspot(self):
        self.assertTrue(self.portal.start())
        self.assertEqual(self.portal.ssid, "BlueGuard-345678")
        self.assertTrue(self.ap.on)
        self.assertTrue(any(call.get("authmode") == 3 and
                            call.get("password") == self.portal.password
                            for call in self.ap.calls))
        self.assertEqual(self.sockets.listener.address, ("0.0.0.0", 80))

    def test_http_setup_page_and_status(self):
        self.portal.start()
        page = self.send(http("GET", "/"))
        self.assertIn(b"200 OK", page)
        self.assertIn(self.portal.ssid.encode(), page)
        self.assertIn(self.portal.token.encode(), page)
        self.assertNotIn(self.portal.password.encode(), page)
        health = self.send(http("GET", "/status"))
        self.assertIn(b'NOT_CONNECTED', health)

    def test_save_form_and_reboot_cannot_reopen(self):
        self.portal.start()
        form = urlencode({"token": self.portal.token,
                          "label": "Cebu Buoy", "apn": "internet.globe.com.ph"}).encode()
        reply = self.send(http("POST", "/save", form))
        self.assertIn(b"200 OK", reply)
        self.assertEqual(self.store.load(), {
            "label": "Cebu Buoy", "apn": "internet.globe.com.ph"})
        self.clock.now += SAVED_GRACE_MS
        self.portal.tick()
        self.assertFalse(self.ap.on)
        new_ap = FakeAP()
        again = SetupPortal(new_ap, FakeSockets(), self.clock, b"\x12\x34\x56\x78",
                            store=self.store, template_path=str(self.page))
        self.assertFalse(again.start())
        self.assertFalse(new_ap.on)

    def test_cannot_save_without_csrf(self):
        self.portal.start()
        request = http("POST", "/save",
                       b"label=BlueGuard&apn=internet&token=wrong")
        self.assertIn(b"403 Forbidden", self.send(request))
        self.assertIsNone(self.store.load())

    def test_cannot_save_from_foreign_origin(self):
        self.portal.start()
        form = urlencode({"label": "Safe", "apn": "internet",
                          "token": self.portal.token}).encode()
        result = self.send(http("POST", "/save", form,
                                origin="http://evil.example"))
        self.assertIn(b"403 Forbidden", result)
        self.assertIsNone(self.store.load())

    def test_dns_rebinding_blocked(self):
        self.portal.start()
        self.assertIn(b"403 Forbidden",
                      self.send(http("GET", "/", host="malicious.test")))

    def test_unknown_fields_not_accepted(self):
        self.portal.start()
        form = urlencode({"token": self.portal.token, "label": "Safe",
                          "apn": "internet", "claimCode": "secret"}).encode()
        self.assertIn(b"400 Bad Request", self.send(http("POST", "/save", form)))
        self.assertIsNone(self.store.load())

    def test_oversized_request_rejected(self):
        self.portal.start()
        response = self.send(http("POST", "/save", b"x" * 600))
        self.assertIn(b"413 Payload Too Large", response)

    def test_expiration_turns_wifi_off(self):
        self.portal.start()
        self.clock.now = AP_TIMEOUT_MS
        self.portal.tick()
        self.assertFalse(self.ap.on)
        self.assertTrue(self.sockets.listener.closed)

    def test_bad_wlan_configuration_fails_closed(self):
        self.portal.ap = FakeAP(fail=True)
        with self.assertRaises(RuntimeError):
            self.portal.start()
        self.assertFalse(self.portal.ap.on)

    def test_bad_form_percent_escape_rejected(self):
        with self.assertRaises(ValueError):
            parse_form(b"apn=%QQ&label=Safe&token=123")

    def test_new_device_without_modem_never_calls_cloud(self):
        self.portal.start()
        self.assertFalse(hasattr(self.portal, "api_client"))
        self.assertFalse(hasattr(self.portal, "device_key"))


if __name__ == "__main__":
    unittest.main()
