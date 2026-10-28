"""Autonomous BlueGuard cellular, HTTPS, health & physical PAIR lifecycle.

Never synthesizes oil measurements. On-device first boot still runs offline if
credentials, modem or TLS are unavailable. Service retries bounded failures.
"""
import time
from services.api_client import ApiClient
from services.cloud_pairing import CloudPairing
from services.device_identity import load_identity, IdentityNotProvisioned
from services.verified_https import load_cloud_profile, create_verified_transport, TransportError
from drivers.a7670c_ppp import open_board_cellular

RETRY_MS=120000
HEALTH_MS=60000
FIRMWARE_VERSION="D-E-2026.10.28"


def _timestamp_utc():
    stamp=time.gmtime()
    if not 2026<=stamp[0]<=2036:
        raise ValueError("RTC not synchronized")
    return "%04d-%02d-%02dT%02d:%02d:%02dZ"%tuple(stamp[:6])


def synchronize_time():
    """Public NTP only establishes a plausible clock; TLS still verifies certs."""
    import ntptime
    ntptime.settime()
    _timestamp_utc()


class CellularService:
    def __init__(self,clock,local_store,cellular_factory=open_board_cellular,
                 identity_loader=load_identity,profile_loader=load_cloud_profile,
                 transport_factory=create_verified_transport,
                 pair_button_factory=None,time_sync=synchronize_time):
        self.clock=clock
        self.store=local_store
        self.cellular_factory=cellular_factory
        self.identity_loader=identity_loader
        self.profile_loader=profile_loader
        self.transport_factory=transport_factory
        self.pair_button_factory=pair_button_factory
        self.time_sync=time_sync
        self.cellular=None
        self.pair=None
        self.button=None
        self.client=None
        self.last_retry_ms=None
        self.last_health_ms=None
        self.status="WAITING_FOR_PROVISIONING"
        self.health_count=0

    def _reset_connection(self):
        if self.cellular is not None:
            try:self.cellular.disconnect()
            except Exception:pass
        self.cellular=None
        self.pair=None
        self.button=None
        self.client=None

    def _start(self):
        local=self.store.load()
        if local is None:
            self.status="LOCAL_SETUP_REQUIRED"
            return
        try:
            identity=self.identity_loader()
        except (IdentityNotProvisioned,ValueError,OSError):
            self.status="DEVICE_IDENTITY_MISSING"
            return
        try:
            profile=self.profile_loader()
        except (TransportError,ValueError,OSError):
            self.status="TLS_PROFILE_MISSING"
            return
        self.status="MODEM_CONNECTING"
        self.cellular=self.cellular_factory(self.clock)
        self.cellular.connect(local["apn"])
        self.status="TIME_SYNCING"
        self.time_sync()
        transport=self.transport_factory(profile)
        self.client=ApiClient(identity["deviceId"],identity["deviceKey"],transport)
        self.pair=CloudPairing(identity["deviceId"],identity["deviceKey"],
                               transport,self.clock)
        if self.pair_button_factory is None:
            from drivers.physical_pair_button import create_physical_pair_button
            self.button=create_physical_pair_button(self.clock)
        else:
            self.button=self.pair_button_factory(self.clock)
        self.status="CLOUD_READY"
        self.last_health_ms=None

    def tick(self):
        now=self.clock.ticks_ms()
        if self.status!="CLOUD_READY":
            if self.last_retry_ms is None or self.clock.ticks_diff(now,self.last_retry_ms)>=RETRY_MS:
                self.last_retry_ms=now
                try:
                    self._start()
                except Exception:
                    self._reset_connection()
                    self.status="CONNECTIVITY_RETRY_PENDING"
            return
        if self.cellular is None or self.cellular.ppp is None or not self.cellular.ppp.isconnected():
            self._reset_connection()
            self.status="CONNECTIVITY_RETRY_PENDING"
            self.last_retry_ms=now
            return
        if self.button.poll():
            self.pair.physically_pressed()
        self.pair.tick()
        if self.last_health_ms is None or self.clock.ticks_diff(now,self.last_health_ms)>=HEALTH_MS:
            self.last_health_ms=now
            try:
                import os
                uid="health_"+''.join("%02x"%n for n in os.urandom(12))
                report={"healthId":uid,"measuredAt":_timestamp_utc(),
                        "sensor":"NOT_INSTALLED","storage":"NOT_VERIFIED",
                        "samplePump":"OFF","washPump":"OFF",
                        "valve":"CLOSED","firmwareVersion":FIRMWARE_VERSION}
                if self.cellular.signal_dbm is not None:
                    report["signalStrengthDbm"]=self.cellular.signal_dbm
                response=self.client.post_health(report)
                if response.get("status") in (200,201):
                    self.health_count+=1
                elif response.get("status") in (401,403):
                    self.status="DEVICE_AUTH_REJECTED"
                    self._reset_connection()
            except Exception:
                # A transport failure is not falsely reported as successful health.
                self._reset_connection()
                self.status="CONNECTIVITY_RETRY_PENDING"

    def snapshot(self):
        return {"cellular":self.status,
                "pairing":self.pair.snapshot()["state"] if self.pair else "INACTIVE",
                "healthUploadsAccepted":self.health_count}
