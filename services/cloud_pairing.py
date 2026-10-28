"""BlueGuard QR v2 pairing, started only by a debounced physical PAIR event.

The phone creates an authenticated pair intent *before* this device receives
the physical button event. Device identity is factory-provisioned; only the
device can initiate a challenge over certificate-verified HTTPS. This module
never imports machine, starts networking, reads a QR, or persists a nonce.
"""
import time
from services.pairing import PairingGate

PROTOCOL=2
MAX_PAIR_SECONDS=300
RETRY_INTERVAL_MS=12000
_TERMINAL=("CONFIRMED","EXPIRED","CONFLICT","INTENT_REQUIRED",
           "PROTOCOL_ERROR","AUTH_FAILED","REJECTED","UNVERIFIED")

def _id(value,low=1,high=80):
    return (isinstance(value,str) and low<=len(value)<=high and
            all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for c in value))

def _is_leap(year):
    return year%4==0 and (year%100!=0 or year%400==0)

def _seconds_utc(parts):
    """Gregorian UTC seconds since 1970; consistent on CPython and MicroPython."""
    if not isinstance(parts,(tuple,list)) or len(parts)<6:
        raise ValueError("Invalid UTC")
    y,m,d,hh,mm,ss=parts[:6]
    if any(type(v)!=int for v in (y,m,d,hh,mm,ss)) or not 2020<=y<=2099 or not 1<=m<=12:
        raise ValueError("Invalid UTC")
    mdays=(31,29 if _is_leap(y) else 28,31,30,31,30,31,31,30,31,30,31)
    if not (1<=d<=mdays[m-1] and 0<=hh<24 and 0<=mm<60 and 0<=ss<60):
        raise ValueError("Invalid UTC")
    days=sum(366 if _is_leap(n) else 365 for n in range(1970,y))
    days+=sum(mdays[:m-1])+d-1
    return ((days*24+hh)*60+mm)*60+ss

def _expiry_seconds(value):
    # Firebase Date.toISOString(): YYYY-MM-DDTHH:MM:SS.sssZ, always UTC.
    if not isinstance(value,str) or len(value)!=24 or value[10]!="T" or value[19]!="." or value[-1]!="Z":
        raise ValueError("Invalid server pairing expiry")
    for i,c in enumerate(value):
        if i in (4,7):
            if c!="-": raise ValueError("Invalid date punctuation")
        elif i in (13,16):
            if c!=":": raise ValueError("Invalid time punctuation")
        elif i not in (10,19,23) and not c.isdigit():
            raise ValueError("Invalid timestamp")
    return _seconds_utc((int(value[:4]),int(value[5:7]),int(value[8:10]),
                         int(value[11:13]),int(value[14:16]),int(value[17:19])))

def _error_code(response):
    if not isinstance(response,dict):
        return None
    code=response.get("code")
    if code is None and isinstance(response.get("body"),dict):
        error=response["body"].get("error")
        if isinstance(error,dict):
            code=error.get("code")
    # No remote text is exposed to status or serial.
    allowed=("DEVICE_AUTH_FAILED","DEVICE_DISABLED","INVALID_PAIRING_NONCE",
             "DEVICE_NOT_FOUND","NOT_FOUND","PAIR_INTENT_REQUIRED",
             "PAIRING_CONFLICT","PAIRING_PROTOCOL_CONFLICT",
             "PAIRING_NOT_PENDING","CHALLENGE_EXPIRED","ALREADY_OWNED",
             "INVALID_PAIRING_PROTOCOL","VALIDATION_ERROR","RATE_LIMITED")
    return code if isinstance(code,str) and code in allowed else None

class CloudPairing:
    def __init__(self,device_id,device_key,transport,clock,utc_now=None):
        if not _id(device_id) or not _id(device_key,32,128):
            raise ValueError("Factory device identity is missing or invalid")
        if transport is None or clock is None:
            raise ValueError("Secure transport and clock required")
        self._id=device_id
        self._key=device_key
        self._transport=transport
        self._clock=clock
        self._utc_now=utc_now if utc_now is not None else time.gmtime
        self._gate=PairingGate()
        self._intent=None
        self._challenge=None
        self._nonce=None
        self._started_ms=None
        self._budget_ms=None
        self._last_attempt=None
        self._retry_ms=RETRY_INTERVAL_MS
        self.state="IDLE"
        self.last_error="NONE"

    def snapshot(self):
        return {"state":self.state,"protocol":PROTOCOL,
                "activeChallenge":self._nonce is not None,
                "pairingAvailable":self.state not in ("CONFIRMED","UNVERIFIED"),
                "lastError":self.last_error}

    def _request(self,path,payload):
        return self._transport.request("POST",path,{
            "X-Device-ID":self._id,"X-Device-Key":self._key,
            "Content-Type":"application/json"},payload)

    def _clear(self):
        self._nonce=None
        self._intent=None
        self._challenge=None
        self._started_ms=None
        self._budget_ms=None
        self._last_attempt=None

    def _fail(self,state,code="NONE"):
        self._clear()
        self.state=state
        self.last_error=code
        return False

    def _classify(self,status,code):
        if status==401 or code=="DEVICE_AUTH_FAILED":
            return "AUTH_FAILED"
        if status==403 or status==404:
            return "REJECTED"
        if status==422 or code in ("PAIRING_PROTOCOL_CONFLICT",
                                   "INVALID_PAIRING_PROTOCOL","VALIDATION_ERROR"):
            return "PROTOCOL_ERROR"
        if code=="PAIR_INTENT_REQUIRED":
            return "INTENT_REQUIRED"
        if code=="PAIRING_CONFLICT":
            return "CONFLICT"
        if code=="CHALLENGE_EXPIRED":
            return "EXPIRED"
        if code=="ALREADY_OWNED":
            # Another user, or our successful response was lost. Do not infer.
            return "UNVERIFIED"
        if code=="PAIRING_NOT_PENDING":
            return "REJECTED"
        return "REJECTED"

    def physically_pressed(self):
        """Only call from a genuine debounced GPIO15 physical-input event."""
        if self.state in ("CONFIRMING","RETRYING","CONFIRMED","UNVERIFIED"):
            return False
        if not self._gate.authorize("PAIR",physically_pressed=True):
            return False
        if not self._gate.consume():
            return False
        self._clear()
        self.last_error="NONE"
        self.state="REQUESTING_CHALLENGE"
        try:
            response=self._request("/api/v1/device/pairing-challenges",
                                   {"protocol":PROTOCOL})
        except Exception:
            return self._fail("RETRY_REQUIRED","NETWORK_UNCERTAIN")
        if not isinstance(response,dict):
            return self._fail("PROTOCOL_ERROR","MALFORMED_RESPONSE")
        code=_error_code(response)
        status=response.get("status")
        if status!=201:
            return self._fail(self._classify(status,code),code or "SERVER_REJECTED")
        body=response.get("body")
        required={"protocol","deviceId","intentId","challengeId","nonce","expiresAt"}
        if (not isinstance(body,dict) or set(body)!=required or
                type(body.get("protocol"))!=int or body["protocol"]!=PROTOCOL or
                body.get("deviceId")!=self._id or
                not _id(body.get("intentId")) or
                not _id(body.get("challengeId")) or
                not _id(body.get("nonce"),32,128)):
            return self._fail("PROTOCOL_ERROR","MALFORMED_RESPONSE")
        try:
            now=_seconds_utc(self._utc_now())
            expires=_expiry_seconds(body["expiresAt"])
        except (TypeError,ValueError,OverflowError):
            return self._fail("PROTOCOL_ERROR","INVALID_EXPIRY")
        remaining=expires-now
        if not 0<remaining<=MAX_PAIR_SECONDS+5:
            return self._fail("EXPIRED","INVALID_EXPIRY")
        self._intent=body["intentId"]
        self._challenge=body["challengeId"]
        self._nonce=body["nonce"]
        self._started_ms=self._clock.ticks_ms()
        self._budget_ms=min(MAX_PAIR_SECONDS,remaining)*1000
        self.state="CONFIRMING"
        return True

    def tick(self):
        if self.state not in ("CONFIRMING","RETRYING"):
            return self.state
        now=self._clock.ticks_ms()
        if self._clock.ticks_diff(now,self._started_ms)>=self._budget_ms:
            self._fail("EXPIRED","CHALLENGE_EXPIRED")
            return self.state
        if (self._last_attempt is not None and
                self._clock.ticks_diff(now,self._last_attempt)<self._retry_ms):
            return self.state
        self._last_attempt=now
        self._retry_ms=RETRY_INTERVAL_MS
        self.state="CONFIRMING"
        try:
            response=self._request("/api/v1/device/pairing-confirmations",{
                "protocol":PROTOCOL,"intentId":self._intent,
                "challengeId":self._challenge,"nonce":self._nonce})
        except Exception:
            self.state="RETRYING"
            self.last_error="NETWORK_UNCERTAIN"
            return self.state
        if not isinstance(response,dict):
            self._fail("PROTOCOL_ERROR","MALFORMED_RESPONSE")
            return self.state
        status=response.get("status")
        code=_error_code(response)
        if status==200:
            body=response.get("body")
            if (not isinstance(body,dict) or
                    set(body)!={"protocol","deviceId","intentId","challengeId","state"} or
                    type(body.get("protocol"))!=int or body["protocol"]!=PROTOCOL or
                    body.get("deviceId")!=self._id or
                    body.get("intentId")!=self._intent or
                    body.get("challengeId")!=self._challenge or
                    body.get("state")!="CONFIRMED"):
                self._fail("PROTOCOL_ERROR","MALFORMED_RESPONSE")
                return self.state
            self._clear()
            self.state="CONFIRMED"
            self.last_error="NONE"
        elif status==429 or isinstance(status,int) and 500<=status<=599:
            self.state="RETRYING"
            self.last_error="RATE_LIMITED" if status==429 else "SERVER_UNAVAILABLE"
            if status==429:
                # Transport may expose a bounded Retry-After seconds value.
                delay=response.get("retryAfter")
                if type(delay)==int and 1<=delay<=300:
                    self._retry_ms=max(RETRY_INTERVAL_MS,delay*1000)
                else:
                    self._retry_ms=60000
        else:
            self._fail(self._classify(status,code),code or "SERVER_REJECTED")
        return self.state
