"""Cloud challenge state machine for the APPROVED physical-PAIR protocol.

Requires an injected certificate-verifying HTTPS transport and device identity.
No remote, Wi-Fi setup page, or USB command can authorize PAIR. Only
physical button events may arm a challenge. No raw nonce/secret in status.
"""
from services.pairing import PairingGate

_WAIT_MS=5*60*1000
_CONFIRM_INTERVAL_MS=8000


def _token(value,max_length=128):
    return (isinstance(value,str) and 1<=len(value)<=max_length and
            all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in value))


class CloudPairing:
    def __init__(self,device_id,device_key,transport,clock):
        if not _token(device_id,80) or not _token(device_key):
            raise ValueError("Invalid provisioned device credentials")
        if transport is None or clock is None:
            raise ValueError("Real trusted transport and clock required")
        self._id=device_id
        self._key=device_key
        self._transport=transport
        self._clock=clock
        self._gate=PairingGate()
        self._challenge=None
        self._nonce=None
        self._start_ms=None
        self._last_attempt=None
        self.state="IDLE"

    def snapshot(self):
        return {"state":self.state,"pairingAvailable":self.state not in ("ERROR","CONFIRMED"),
                "activeChallenge":self._challenge is not None}

    def _request(self,path,payload):
        # HTTPS certificate and hostname verification are transport duties.
        return self._transport.request(
            "POST",path,{"X-Device-ID":self._id,
                         "X-Device-Key":self._key,
                         "Content-Type":"application/json"},payload)

    def _clear(self):
        self._nonce=None
        self._challenge=None
        self._start_ms=None
        self._last_attempt=None

    def physically_pressed(self):
        """Caller MUST wire this exclusively to debounced physical PAIR input."""
        if self.state=="CONFIRMED":
            return False
        if not self._gate.authorize("PAIR",physically_pressed=True):
            return False
        if not self._gate.consume():
            return False
        self._clear()
        try:
            response=self._request("/api/v1/device/pairing-challenges",{})
            if not isinstance(response,dict) or response.get("status")!=201:
                self.state="ERROR"
                return False
            body=response.get("body",{})
            challenge=body.get("challengeId")
            nonce=body.get("nonce")
            if body.get("deviceId")!=self._id or not _token(challenge) or not _token(nonce):
                self.state="ERROR"
                return False
            self._challenge=challenge
            self._nonce=nonce
            self._start_ms=self._clock.ticks_ms()
            self.state="WAITING_FOR_APP_CLAIM"
            return True
        except Exception:
            self._clear()
            self.state="ERROR"
            return False

    def tick(self):
        if self.state!="WAITING_FOR_APP_CLAIM":
            return self.state
        now=self._clock.ticks_ms()
        if self._clock.ticks_diff(now,self._start_ms)>=_WAIT_MS:
            self._clear()
            self.state="EXPIRED"
            return self.state
        if self._last_attempt is not None and self._clock.ticks_diff(now,self._last_attempt)<_CONFIRM_INTERVAL_MS:
            return self.state
        self._last_attempt=now
        try:
            result=self._request("/api/v1/device/pairing-confirmations",{
                "challengeId":self._challenge,"nonce":self._nonce})
            status=result.get("status") if isinstance(result,dict) else None
            if status==200 and result.get("body",{}).get("state")=="CONFIRMED":
                self._clear()
                self.state="CONFIRMED"
            elif status in (403,404) or (status==409 and
                 result.get("code") in ("ALREADY_OWNED","CHALLENGE_EXPIRED",
                                        "INVALID_PAIRING_NONCE")):
                self._clear()
                self.state="ERROR"
            # CLAIM_NOT_PENDING 409, 429, 5xx, transient connectivity:
            # retry the SAME challenge within local time bound.
        except Exception:
            pass
        return self.state
