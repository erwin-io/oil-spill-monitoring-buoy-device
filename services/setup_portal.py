"""Time-limited, WPA2, first-boot ESP32 setup AP + lightweight HTTP server.

This portal cannot pair/claim devices, retrieve device keys or start the LTE modem.
Hardware imports occur only inside create_device_portal().
"""
import binascii
import os
from services.provisioning import ProvisioningStore, validate_settings
from config import SETUP_AP_CONFIG

AP_TIMEOUT_MS = SETUP_AP_CONFIG["session_ms"]
SAVED_GRACE_MS = SETUP_AP_CONFIG["save_grace_ms"]
MAX_HEADER = 1400
MAX_FORM = 512


def _unquote(value):
    value = value.replace("+", " ")
    out = []
    i = 0
    while i < len(value):
        if value[i] == "%":
            if i + 2 >= len(value):
                raise ValueError("Bad escape sequence")
            try:
                out.append(chr(int(value[i + 1:i + 3], 16)))
            except ValueError:
                raise ValueError("Bad escape sequence") from None
            i += 3
        else:
            out.append(value[i])
            i += 1
    text = "".join(out)
    if any(ord(c) < 32 or ord(c) > 126 for c in text):
        raise ValueError("Invalid form character")
    return text


def parse_form(body):
    if len(body) > MAX_FORM:
        raise ValueError("Form exceeds safe size")
    try:
        fields = body.decode("ascii").split("&")
    except UnicodeError:
        raise ValueError("Form must be ASCII") from None
    if len(fields) != 3:
        raise ValueError("Unexpected form fields")
    result = {}
    for field in fields:
        if "=" not in field:
            raise ValueError("Malformed form field")
        key, value = field.split("=", 1)
        if key not in ("token", "label", "apn") or key in result:
            raise ValueError("Unexpected form field")
        result[key] = _unquote(value)
    if set(result) != {"token", "label", "apn"}:
        raise ValueError("Missing setup fields")
    return result


class SetupPortal:
    def __init__(self, ap, socket_module, clock, uid, store=None, template_path="/web/setup.html"):
        self.ap = ap
        self.socket_module = socket_module
        self.clock = clock
        self.store = store if store is not None else ProvisioningStore()
        self.template_path = template_path
        self.ssid = "BlueGuard-" + binascii.hexlify(uid).decode()[-6:].upper()
        self.password = None
        self.token = None
        self.ip = None
        self.listener = None
        self.started_at = None
        self.saved_at = None
        self.active = False
        self.last_error = None

    def start(self):
        if self.store.load() is not None:
            return False
        if SETUP_AP_CONFIG["first_boot_enabled"] is not True:
            return False
        self.password = self.store.password()
        self.token = binascii.hexlify(os.urandom(16)).decode()
        try:
            try:
                self.ap.config(essid=self.ssid, password=self.password, authmode=3)
            except (TypeError, ValueError, OSError):
                # Newer WLAN option names: still require password + WPA2.
                self.ap.config(ssid=self.ssid, key=self.password, security=3)
            self.ap.active(True)
            try:
                self.ap.config(max_clients=SETUP_AP_CONFIG["max_clients"])
            except (TypeError, ValueError, OSError):
                pass  # Not exposed on every MicroPython WLAN revision.
            try:
                self.ip = self.ap.ifconfig()[0]
            except AttributeError:
                self.ip = self.ap.ipconfig("addr4")[0]
            listener = self.socket_module.socket()
            if hasattr(self.socket_module, "SO_REUSEADDR"):
                listener.setsockopt(self.socket_module.SOL_SOCKET,
                                    self.socket_module.SO_REUSEADDR, 1)
            listener.bind(("0.0.0.0", 80))
            listener.listen(2)
            listener.setblocking(False)
            self.listener = listener
            self.started_at = self.clock.ticks_ms()
            self.active = True
            return True
        except Exception:
            self.close()
            raise

    def close(self):
        self.active = False
        if self.listener is not None:
            try:
                self.listener.close()
            except OSError:
                pass
            self.listener = None
        try:
            self.ap.active(False)
        except OSError:
            pass

    def tick(self):
        if not self.active:
            return
        now = self.clock.ticks_ms()
        if self.saved_at is not None:
            if self.clock.ticks_diff(now, self.saved_at) >= SAVED_GRACE_MS:
                self.close()
                return
        elif self.clock.ticks_diff(now, self.started_at) >= AP_TIMEOUT_MS:
            self.close()
            return
        try:
            client, _ = self.listener.accept()
        except OSError:
            return
        try:
            client.settimeout(0.8)
            self._serve(client)
        except (OSError, ValueError):
            self.last_error = "REQUEST_REJECTED"
        finally:
            try:
                client.close()
            except OSError:
                pass

    def _reply(self, client, status, body, mime="text/html; charset=utf-8"):
        payload = body.encode("utf-8")
        title = {200: "OK", 400: "Bad Request", 403: "Forbidden",
                 404: "Not Found", 413: "Payload Too Large"}.get(status, "Error")
        header = ("HTTP/1.1 %d %s\r\nContent-Type: %s\r\n"
                  "Content-Length: %d\r\nConnection: close\r\n"
                  "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
                  "X-Frame-Options: DENY\r\nContent-Security-Policy: "
                  "default-src 'none'; style-src 'unsafe-inline'; "
                  "form-action 'self'; frame-ancestors 'none'\r\n\r\n"
                  % (status, title, mime, len(payload)))
        client.sendall(header.encode() + payload)

    def _serve(self, client):
        received = b""
        while b"\r\n\r\n" not in received and len(received) < MAX_HEADER:
            piece = client.recv(min(256, MAX_HEADER - len(received)))
            if not piece:
                break
            received += piece
        if b"\r\n\r\n" not in received:
            self._reply(client, 413, "Header too large")
            return
        head, body = received.split(b"\r\n\r\n", 1)
        try:
            lines = head.decode("ascii").split("\r\n")
            method, path, version = lines[0].split(" ")
            if version not in ("HTTP/1.0", "HTTP/1.1"):
                raise ValueError("Unsupported HTTP version")
            headers = {}
            for line in lines[1:]:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                if key in headers:
                    raise ValueError("Duplicate header")
                headers[key] = value.strip()
            host = headers.get("host", "")
            if host not in (self.ip, self.ip + ":80"):
                self._reply(client, 403, "Invalid local host")
                return
            origin = headers.get("origin")
            if origin is not None and origin != "http://" + self.ip:
                self._reply(client, 403, "Invalid request origin")
                return
            if method == "GET" and path == "/":
                with open(self.template_path, "r") as f:
                    html = f.read()
                html = html.replace("{{SSID}}", self.ssid)
                html = html.replace("{{TOKEN}}", self.token)
                self._reply(client, 200, html)
                return
            if method == "GET" and path == "/status":
                self._reply(client, 200,
                            '{"setup":"UNPROVISIONED","modem":"NOT_CONNECTED",'
                            '"sensor":"NOT_INSTALLED"}',
                            "application/json")
                return
            if method != "POST" or path != "/save":
                self._reply(client, 404, "Unsupported route")
                return
            if self.saved_at is not None:
                self._reply(client, 403, "Setup already saved")
                return
            if headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
                self._reply(client, 400, "Unsupported content type")
                return
            if "transfer-encoding" in headers:
                self._reply(client, 400, "Chunked request unsupported")
                return
            size = int(headers.get("content-length", "-1"))
            if size < 1 or size > MAX_FORM:
                self._reply(client, 413, "Invalid form length")
                return
            while len(body) < size:
                part = client.recv(min(256, size - len(body)))
                if not part:
                    raise ValueError("Incomplete form")
                body += part
            if len(body) != size:
                raise ValueError("Extra body bytes")
            data = parse_form(body)
            if data["token"] != self.token:
                self._reply(client, 403, "Invalid setup authorization")
                return
            approved = validate_settings({"label": data["label"], "apn": data["apn"]})
            self.store.save_once(approved)
            self.saved_at = self.clock.ticks_ms()
            self._reply(client, 200,
                        "<h1>BlueGuard setup saved</h1><p>Local settings were stored. "
                        "The hotspot will close shortly. LTE modem communication "
                        "is not active yet. Use the official app and physical PAIR "
                        "for cloud ownership after connectivity is available.</p>")
        except (ValueError, UnicodeError, IndexError):
            self._reply(client, 400, "Invalid setup request")


def create_device_portal(clock):
    # Only called on physical MicroPython startup, never desktop test import.
    import machine
    import network
    import socket
    interface = getattr(network, "AP_IF", None)
    if interface is None:
        interface = network.WLAN.IF_AP
    return SetupPortal(network.WLAN(interface), socket, clock, machine.unique_id())
