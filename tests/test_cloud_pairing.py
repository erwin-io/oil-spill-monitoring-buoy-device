"""Real API pairing contract tested with injected offline transport."""
import unittest
from services.cloud_pairing import CloudPairing


class Clock:
    def __init__(self):self.ms=0
    def ticks_ms(self):return self.ms
    def ticks_diff(self,now,before):return now-before


class StubTransport:
    def __init__(self):
        self.calls=[]
        self.responses=[
            {"status":201,"body":{"deviceId":"buoy_01","challengeId":"abc123","nonce":"once123"}},
            {"status":409,"code":"CLAIM_NOT_PENDING"},
            {"status":200,"body":{"deviceId":"buoy_01","state":"CONFIRMED","challengeId":"abc123"}}
        ]
    def request(self,method,path,headers,payload):
        self.calls.append((method,path,headers,dict(payload)))
        return self.responses.pop(0)


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock()
        self.client=StubTransport()
        self.pair=CloudPairing("buoy_01","device_upload_secret_123",
                               self.client,self.clock)

    def test_no_remote_or_setup_claim(self):
        self.assertEqual(self.pair.tick(),"IDLE")
        self.assertEqual(self.client.calls,[])
        self.assertFalse(self.pair.snapshot()["activeChallenge"])

    def test_real_button_then_pending_then_confirmed(self):
        self.assertTrue(self.pair.physically_pressed())
        self.assertEqual(self.pair.snapshot()["state"],"WAITING_FOR_APP_CLAIM")
        self.assertNotIn("nonce",str(self.pair.snapshot()))
        self.assertEqual(self.pair.tick(),"WAITING_FOR_APP_CLAIM")
        self.clock.ms+=8000
        self.assertEqual(self.pair.tick(),"CONFIRMED")
        self.assertFalse(self.pair.physically_pressed())
        self.assertEqual(self.client.calls[0][1],"/api/v1/device/pairing-challenges")
        self.assertEqual(self.client.calls[-1][1],"/api/v1/device/pairing-confirmations")
        self.assertEqual(self.client.calls[-1][3],{"challengeId":"abc123","nonce":"once123"})

    def test_expiration_never_confirms(self):
        self.assertTrue(self.pair.physically_pressed())
        self.clock.ms=300000
        self.assertEqual(self.pair.tick(),"EXPIRED")
        self.assertEqual(len(self.client.calls),1)

    def test_wrong_server_identity_fails(self):
        self.client.responses[0]["body"]["deviceId"]="wrong_buoy"
        self.assertFalse(self.pair.physically_pressed())
        self.assertEqual(self.pair.snapshot()["state"],"ERROR")

    def test_unowned_claim_not_pending_is_retryable(self):
        self.pair.physically_pressed()
        self.pair.tick()
        self.assertEqual(self.pair.state,"WAITING_FOR_APP_CLAIM")

    def test_no_pairing_without_credentials(self):
        with self.assertRaises(ValueError):
            CloudPairing("","key",self.client,self.clock)


if __name__=="__main__":
    unittest.main()
