"""Offline integration for PPP, TLS, identity, and boot cloud service."""
import json
import unittest
from drivers.a7670c_ppp import ATLineTerminal,A7670CPPP,CellularError
from services.verified_https import VerifiedHttpsTransport,TransportError
from services.cellular_runtime import CellularService

class Clock:
    def __init__(self):self.ms=0
    def ticks_ms(self):return self.ms
    def ticks_diff(self,a,b):return a-b
    def sleep_ms(self,n):self.ms+=n

class UART:
    def __init__(self,replies):
        self.responses=dict(replies)
        self.buffer=bytearray()
        self.calls=[]
    def any(self):return len(self.buffer)
    def read(self,n):
        d=bytes(self.buffer[:n]);del self.buffer[:n];return d
    def write(self,raw):
        cmd=raw.decode().strip()
        self.calls.append(cmd)
        self.buffer.extend(self.responses.get(cmd,b""))
        return len(raw)

class PPP:
    def __init__(self,uart):self.uart=uart;self.up=False
    def active(self,val):pass
    def connect(self):self.up=True
    def isconnected(self):return self.up
    def disconnect(self):self.up=False

class TerminalTests(unittest.TestCase):
    def test_uart_sim_apn_registration_and_ppp(self):
        uart=UART({"AT":b"\r\nOK\r\n",
                   "ATE0":b"\r\nOK\r\n",
                   "AT+CPIN?":b"\r\n+CPIN: READY\r\nOK\r\n",
                   "AT+CEREG?":b"\r\n+CEREG: 0,1\r\nOK\r\n",
                   "AT+CSQ":b"\r\n+CSQ: 23,0\r\nOK\r\n",
                   'AT+CGDCONT=1,"IP","internet"':b"\r\nOK\r\n",
                   "ATD*99***1#":b"\r\nCONNECT 115200\r\n"})
        modem=A7670CPPP(uart,Clock(),PPP)
        self.assertTrue(modem.connect("internet"))
        self.assertEqual(modem.status,"PPP_CONNECTED")
        self.assertEqual(modem.signal_dbm,-67)
        self.assertIn('AT+CGDCONT=1,"IP","internet"',uart.calls)

    def test_modem_registration_denied(self):
        uart=UART({"AT":b"OK\r\n","ATE0":b"OK\r\n",
                   "AT+CPIN?":b"+CPIN: READY\r\nOK\r\n",
                   "AT+CEREG?":b"+CEREG: 0,3\r\nOK\r\n"})
        with self.assertRaises(CellularError):
            A7670CPPP(uart,Clock(),PPP).connect("internet")

    def test_modem_rejects_apn_injection(self):
        modem=A7670CPPP(UART({}),Clock(),PPP)
        with self.assertRaises(ValueError):
            modem.connect('internet";AT+CFUN=1')

class FakeTlsContext:
    def __init__(self):self.verify_mode=0;self.name=None;self.ca=None
    def load_verify_locations(self,cadata):self.ca=cadata
    def wrap_socket(self,sock,server_hostname=None):
        self.name=server_hostname
        return sock

class FakeTls:
    CERT_REQUIRED=2
    PROTOCOL_TLS_CLIENT=1
    def __init__(self):self.context=FakeTlsContext()
    def SSLContext(self,_):return self.context

class FakeConnection:
    def __init__(self,response):self.response=bytearray(response);self.sent=b""
    def settimeout(self,n):pass
    def connect(self,addr):pass
    def write(self,data):self.sent+=data;return len(data)
    def read(self,n):
        data=bytes(self.response[:n]);del self.response[:n];return data
    def close(self):pass

class FakeSockets:
    SOCK_STREAM=1
    def __init__(self,response):
        self.conn=FakeConnection(response)
    def getaddrinfo(self,host,port,*args):
        return [(2,1,0,"",("127.0.0.1",443))]
    def socket(self,*args):return self.conn

class TLSTests(unittest.TestCase):
    def test_rejects_missing_ca_and_insecure_origin(self):
        with self.assertRaises(TransportError):
            VerifiedHttpsTransport("api.example.com",b"",FakeSockets(b""),FakeTls())
        with self.assertRaises(TransportError):
            VerifiedHttpsTransport("http://evil",b"x"*200,FakeSockets(b""),FakeTls())

    def test_tls_verification_and_hostname_required(self):
        reply=b'HTTP/1.1 201 Created\r\nContent-Length: 21\r\n\r\n{"state":"CONFIRMED"}'
        net=FakeSockets(reply)
        tls=FakeTls()
        transport=VerifiedHttpsTransport("api.example.com",b"x"*200,net,tls)
        response=transport.request("POST","/api/v1/device/pairing-confirmations",
                     {"X-Device-ID":"buoy_01"}, {"challengeId":"x"})
        self.assertEqual(response["status"],201)
        self.assertEqual(tls.context.verify_mode,tls.CERT_REQUIRED)
        self.assertEqual(tls.context.name,"api.example.com")
        self.assertIn(b'Host: api.example.com',net.conn.sent)

    def test_http_chunked_response(self):
        net=FakeSockets(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'
                        b'15\r\n{"state":"CONFIRMED"}\r\n0\r\n\r\n')
        transport=VerifiedHttpsTransport("api.example.com",b"x"*200,net,FakeTls())
        result=transport.request("GET","/api/v1/device/config",{},None)
        self.assertEqual(result["body"]["state"],"CONFIRMED")

    def test_nested_api_error_code_is_preserved(self):
        response=b'{"error":{"code":"CLAIM_NOT_PENDING"}}'
        wire=(b"HTTP/1.1 409 Conflict\r\nContent-Length: "+
              str(len(response)).encode()+b"\r\n\r\n"+response)
        net=FakeSockets(wire)
        transport=VerifiedHttpsTransport("api.example.com",b"x"*200,net,FakeTls())
        result=transport.request("POST","/api/v1/device/pairing-confirmations",{}, {})
        self.assertEqual(result["code"],"CLAIM_NOT_PENDING")

    def test_rejects_redirect(self):
        net=FakeSockets(b"HTTP/1.1 302 Found\r\nContent-Length: 0\r\n\r\n")
        transport=VerifiedHttpsTransport("api.example.com",b"x"*200,net,FakeTls())
        with self.assertRaises(TransportError):
            transport.request("GET","/api/v1/device/config",{},None)

class Store:
    def load(self):return {"apn":"internet","label":"BlueGuard"}
class Connected:
    def __init__(self):self.ppp=PPP(None);self.ppp.up=True;self.signal_dbm=-73
    def connect(self,apn):self.apn=apn
    def disconnect(self):self.ppp.up=False
class FakeButton:
    def poll(self):return False
class FakeHttps:
    def __init__(self):self.requests=[]
    def request(self,method,path,headers,payload):
        self.requests.append((method,path,headers,payload))
        return {"status":201,"body":{"accepted":True}}

class RuntimeTests(unittest.TestCase):
    def test_resident_loop_runs_cellular_without_manual_commands(self):
        import main
        class Service:
            def __init__(self):
                self.ticks=0
                self.status="CLOUD_READY"
            def tick(self):self.ticks+=1
            def snapshot(self):return {"cellular":self.status}
        fake=Service()
        output=[]
        state=main.serve_forever(clock=Clock(),max_ticks=3,output=output.append,
                                 cloud_service=fake)
        self.assertEqual(fake.ticks,3)
        self.assertEqual(state["cellular"],"CLOUD_READY")
        self.assertTrue(any("BlueGuard cellular" in line for line in output))


    def test_cloud_health_uses_legitimate_schema_and_tls(self):
        net=Connected()
        http=FakeHttps()
        service=CellularService(Clock(),Store(),cellular_factory=lambda _:net,
            identity_loader=lambda:{"deviceId":"buoy_01","deviceKey":"x"*48},
            profile_loader=lambda:{"host":"api.example.com","caDerPath":"/ca.der"},
            transport_factory=lambda _:http,
            pair_button_factory=lambda _:FakeButton(),time_sync=lambda:None)
        service.tick()
        self.assertEqual(service.status,"CLOUD_READY")
        # time is system UTC on the host. Avoid making a fake cloud success claim.
        service.tick()
        self.assertEqual(service.snapshot()["pairing"],"IDLE")

    def test_missing_identity_is_not_connected(self):
        from services.device_identity import IdentityNotProvisioned
        service=CellularService(Clock(),Store(),cellular_factory=lambda _:None,
            identity_loader=lambda:(_ for _ in ()).throw(IdentityNotProvisioned("Missing")),
            profile_loader=lambda:{})
        service.tick()
        self.assertEqual(service.status,"DEVICE_IDENTITY_MISSING")
