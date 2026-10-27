"""Offline-only desktop demo. No sockets, hardware or production integration."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import run
from services.api_client import ApiClient
from services.health import HealthService
from services.telemetry import TelemetryService
from tests.fakes.device import (
    FakeBoard, FakeClock, FakeIds, FakeTransport, FakeHealthSource, FakeMeasurementSource
)


def simulate():
    clock, ids, transport = FakeClock(), FakeIds(), FakeTransport()
    state = run(board=FakeBoard())["state"]
    measurement = TelemetryService(FakeMeasurementSource(), clock, ids).capture()
    health = HealthService(FakeHealthSource(), clock, ids).capture()
    client = ApiClient("buoy_SIM", "FAKE_TEST_CREDENTIAL_ONLY", transport)
    client.post_measurement(measurement)
    client.post_health(health)
    return {"environment": "SIMULATED_DO_NOT_USE_FOR_SCIENCE", "state": state,
            "fake_requests": len(transport.calls), "endpoints": [r["path"] for r in transport.calls]}


if __name__ == "__main__":
    print(simulate())
