"""QR v2 exact API contract, state machine, deadline and security regression."""
import unittest
from services.cloud_pairing import CloudPairing, _expiry_seconds

DEVICE="BG-000124"
KEY="K"*48
INTENT="i"*48
CHALLENGE="c"*48
NONCE="n"*48
EXPIRY="2026-10-29T03:04:00.000Z"

class FakeClock:
    def __init__(self):
        self.ms=0
        self.utc=(2026,10,29,3,0,0)
    def ticks_ms(self):return self.ms
    def ticks_diff(self,now,before):return now-before
    def advance(self,ms):self.ms+=ms

class FakeTransport:
    def __init__(self,replies=None):
        self.replies=list(replies if replies is not None else [])
        self.calls=[]
    def request(self,method,path,headers,payload):
        self.calls.append((method,path,dict(headers),dict(payload)))
        if not self.replies:
            raise AssertionError("Unexpected network request")
        reply=self.replies.pop(0)
        if isinstance(reply,Exception):raise reply
        return reply

def challenge(**changes):
    result={"protocol":2,"deviceId":DEVICE,"intentId":INTENT,
            "challengeId":CHALLENGE,"nonce":NONCE,"expiresAt":EXPIRY}
    result.update(changes)
    return {"status":201,"body":result}

def confirmation(**changes):
    result={"protocol":2,"deviceId":DEVICE,"intentId":INTENT,
            "challengeId":CHALLENGE,"state":"CONFIRMED"}
    result.update(changes)
    return {"status":200,"body":result}

def error(status,code):
    return {"status":status,"body":{"error":{"code":code}}}

class QrV2PairingTests(unittest.TestCase):
    def create(self,replies=None):
        clock=FakeClock()
        transport=FakeTransport(replies)
        pair=CloudPairing(DEVICE,KEY,transport,clock,utc_now=lambda:clock.utc)
        return pair,clock,transport

    def test_success_exact_v2_paths_payloads_auth_and_server_match(self):
        pair,clock,transport=self.create([challenge(),confirmation()])
        self.assertEqual(pair.tick(),"IDLE")
        self.assertEqual(transport.calls,[])
        self.assertTrue(pair.physically_pressed())
        self.assertEqual(pair.state,"CONFIRMING")
        self.assertEqual(pair.tick(),"CONFIRMED")
        self.assertFalse(pair.snapshot()["activeChallenge"])
        self.assertFalse(pair.snapshot()["pairingAvailable"])
        self.assertEqual(pair.snapshot()["protocol"],2)
        self.assertEqual(len(transport.calls),2)
        self.assertEqual(transport.calls[0][0:2],("POST","/api/v1/device/pairing-challenges"))
        self.assertEqual(transport.calls[0][3],{"protocol":2})
        self.assertEqual(transport.calls[1][0:2],("POST","/api/v1/device/pairing-confirmations"))
        self.assertEqual(transport.calls[1][3],{"protocol":2,"intentId":INTENT,
                                               "challengeId":CHALLENGE,"nonce":NONCE})
        for _,_,headers,_ in transport.calls:
            self.assertEqual(headers["X-Device-ID"],DEVICE)
            self.assertEqual(headers["X-Device-Key"],KEY)
            self.assertEqual(headers["Content-Type"],"application/json")
        self.assertFalse(pair.physically_pressed())

    def test_no_pairing_until_explicit_physical_event(self):
        pair,clock,transport=self.create([])
        clock.advance(120000)
        self.assertEqual(pair.tick(),"IDLE")
        self.assertEqual(transport.calls,[])
        self.assertFalse(pair.snapshot()["activeChallenge"])

    def test_no_phone_intent_requires_new_real_button_press(self):
        pair,_,transport=self.create([error(409,"PAIR_INTENT_REQUIRED"),challenge()])
        self.assertFalse(pair.physically_pressed())
        self.assertEqual(pair.state,"INTENT_REQUIRED")
        self.assertEqual(pair.tick(),"INTENT_REQUIRED")
        self.assertEqual(len(transport.calls),1)
        self.assertTrue(pair.physically_pressed())

    def test_another_user_competes_fail_closed(self):
        pair,_,t=self.create([error(409,"PAIRING_CONFLICT")])
        self.assertFalse(pair.physically_pressed())
        self.assertEqual(pair.state,"CONFLICT")
        self.assertFalse(pair.snapshot()["activeChallenge"])

    def test_reject_legacy_protocol_conflict_without_fallback(self):
        pair,_,t=self.create([error(409,"PAIRING_PROTOCOL_CONFLICT")])
        self.assertFalse(pair.physically_pressed())
        self.assertEqual(pair.state,"PROTOCOL_ERROR")
        self.assertEqual(t.calls[0][3],{"protocol":2})

    def test_wrong_device_and_mismatched_response_refused(self):
        for field,value in (("deviceId","BG-OTHER"),("protocol",1),
                            ("intentId","bad?"),("challengeId","bad?"),
                            ("nonce","short")):
            with self.subTest(field=field):
                pair,_,t=self.create([challenge(**{field:value})])
                self.assertFalse(pair.physically_pressed())
                self.assertEqual(pair.state,"PROTOCOL_ERROR")
                self.assertEqual(len(t.calls),1)

    def test_extra_challenge_field_is_refused(self):
        pair,_,t=self.create([challenge(claimCode="unexpected")])
        self.assertFalse(pair.physically_pressed())
        self.assertEqual(pair.state,"PROTOCOL_ERROR")

    def test_server_expired_and_unplausible_deadlines_refused(self):
        for expiry in ("2026-10-29T02:59:00.000Z",
                       "2026-10-29T03:06:01.000Z",
                       "2026-02-30T03:01:00.000Z",
                       "2026-10-29T03:01:00Z",1234):
            with self.subTest(expiry=expiry):
                pair,_,t=self.create([challenge(expiresAt=expiry)])
                self.assertFalse(pair.physically_pressed())
                self.assertIn(pair.state,("EXPIRED","PROTOCOL_ERROR"))

    def test_deadline_enforced_without_attempt_after_expiry(self):
        pair,clock,t=self.create([challenge()])
        self.assertTrue(pair.physically_pressed())
        clock.advance(240000)
        self.assertEqual(pair.tick(),"EXPIRED")
        self.assertEqual(len(t.calls),1)
        self.assertFalse(pair.snapshot()["activeChallenge"])

    def test_confirmation_response_must_match_entire_transaction(self):
        for field,value in (("protocol",1),("deviceId","BG-OTHER"),
                            ("intentId","wrong"),("challengeId","wrong"),
                            ("state","PENDING")):
            with self.subTest(field=field):
                pair,_,t=self.create([challenge(),confirmation(**{field:value})])
                self.assertTrue(pair.physically_pressed())
                self.assertEqual(pair.tick(),"PROTOCOL_ERROR")
                self.assertFalse(pair.snapshot()["activeChallenge"])

    def test_extra_confirmation_field_rejected(self):
        pair,_,t=self.create([challenge(),confirmation(nonce="SHOULD_NOT_ECHO")])
        pair.physically_pressed()
        self.assertEqual(pair.tick(),"PROTOCOL_ERROR")

    def test_confirmation_auth_and_nonce_rejection(self):
        for status,code,wanted in (
                (401,"DEVICE_AUTH_FAILED","AUTH_FAILED"),
                (403,"DEVICE_DISABLED","REJECTED"),
                (403,"INVALID_PAIRING_NONCE","REJECTED"),
                (404,"DEVICE_NOT_FOUND","REJECTED"),
                (409,"PAIRING_NOT_PENDING","REJECTED"),
                (409,"PAIRING_CONFLICT","CONFLICT"),
                (409,"CHALLENGE_EXPIRED","EXPIRED"),
                (422,"INVALID_PAIRING_PROTOCOL","PROTOCOL_ERROR")):
            with self.subTest(code=code):
                pair,_,t=self.create([challenge(),error(status,code)])
                pair.physically_pressed()
                self.assertEqual(pair.tick(),wanted)
                self.assertFalse(pair.snapshot()["activeChallenge"])

    def test_lost_confirm_response_never_inferred_success(self):
        pair,clock,t=self.create([challenge(),OSError("secret internal error"),
                                  error(409,"ALREADY_OWNED")])
        self.assertTrue(pair.physically_pressed())
        self.assertEqual(pair.tick(),"RETRYING")
        self.assertEqual(pair.snapshot()["lastError"],"NETWORK_UNCERTAIN")
        self.assertNotIn("secret",str(pair.snapshot()))
        clock.advance(12000)
        self.assertEqual(pair.tick(),"UNVERIFIED")
        self.assertNotEqual(pair.state,"CONFIRMED")
        self.assertFalse(pair.snapshot()["activeChallenge"])

    def test_retry_sends_exact_same_nonce_not_new_challenge(self):
        pair,clock,t=self.create([challenge(),error(503,"UNAVAILABLE"),confirmation()])
        pair.physically_pressed()
        self.assertEqual(pair.tick(),"RETRYING")
        clock.advance(11999)
        self.assertEqual(pair.tick(),"RETRYING")
        clock.advance(1)
        self.assertEqual(pair.tick(),"CONFIRMED")
        self.assertEqual(len(t.calls),3)
        self.assertEqual(t.calls[1][3],t.calls[2][3])

    def test_429_honors_bounded_retry_after(self):
        pair,clock,t=self.create([challenge(),{"status":429,"retryAfter":35,
                    "body":{"error":{"code":"RATE_LIMITED"}}},confirmation()])
        pair.physically_pressed()
        self.assertEqual(pair.tick(),"RETRYING")
        clock.advance(34999)
        self.assertEqual(pair.tick(),"RETRYING")
        clock.advance(1)
        self.assertEqual(pair.tick(),"CONFIRMED")

    def test_429_without_retry_after_is_conservative(self):
        pair,clock,t=self.create([challenge(),error(429,"RATE_LIMITED"),confirmation()])
        pair.physically_pressed()
        self.assertEqual(pair.tick(),"RETRYING")
        clock.advance(59999)
        self.assertEqual(pair.tick(),"RETRYING")
        clock.advance(1)
        self.assertEqual(pair.tick(),"CONFIRMED")

    def test_no_rearm_in_retry_loop_or_after_unverified_ownership(self):
        pair,clock,t=self.create([challenge(),TimeoutError("lost"),
                                 error(409,"ALREADY_OWNED")])
        pair.physically_pressed()
        pair.tick()
        self.assertFalse(pair.physically_pressed())
        clock.advance(12000)
        self.assertEqual(pair.tick(),"UNVERIFIED")
        self.assertFalse(pair.physically_pressed())
        self.assertEqual(len(t.calls),3)

    def test_network_failure_start_never_autocreates_new_challenge(self):
        pair,clock,t=self.create([OSError("no LTE"),challenge()])
        self.assertFalse(pair.physically_pressed())
        self.assertEqual(pair.state,"RETRY_REQUIRED")
        self.assertEqual(pair.tick(),"RETRY_REQUIRED")
        self.assertEqual(len(t.calls),1)
        self.assertTrue(pair.physically_pressed())
        self.assertEqual(len(t.calls),2)

    def test_invalid_model_auth_has_no_network_calls(self):
        with self.assertRaises(ValueError):
            CloudPairing(DEVICE,"short",FakeTransport(),FakeClock())

    def test_gregorian_expiry_parser(self):
        self.assertGreater(_expiry_seconds("2028-02-29T00:00:00.000Z"),
                           _expiry_seconds("2028-02-28T00:00:00.000Z"))
        with self.assertRaises(ValueError):
            _expiry_seconds("2027-02-29T00:00:00.000Z")
        with self.assertRaises(ValueError):
            _expiry_seconds("2026-13-01T00:00:00.000Z")

if __name__=="__main__":
    unittest.main()
