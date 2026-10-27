import unittest
from services.api_client import ApiClient
from services.telemetry import TelemetryService
from services.health import HealthService
from services.pairing import PairingGate
from tests.fakes.device import FakeClock, FakeIds, FakeMeasurementSource, FakeHealthSource, FakeTransport


class ServicesTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.ids = FakeIds()
        self.transport = FakeTransport()

    def test_capture_measurement_without_sensor(self):
        record = TelemetryService(FakeMeasurementSource(), self.clock, self.ids).capture()
        self.assertEqual(record["classification"], "NORMAL")
        self.assertEqual(record["qualityFlags"], ["SIMULATED_DO_NOT_USE_FOR_SCIENCE"])
        self.assertEqual(set(record["spectral"]), {"f415", "f445", "f480", "f515", "f555", "f590"})

    def test_fake_api_measurement_transport(self):
        record = TelemetryService(FakeMeasurementSource(), self.clock, self.ids).capture()
        response = ApiClient("buoy_SIM", "FAKE_TEST_CREDENTIAL_ONLY", self.transport).post_measurement(record)
        self.assertTrue(response["simulated"])
        self.assertEqual(self.transport.calls[0]["path"], "/api/v1/device/measurements")
        self.assertEqual(self.transport.calls[0]["headers"]["X-Device-ID"], "buoy_SIM")

    def test_health_without_hardware(self):
        report = HealthService(FakeHealthSource(), self.clock, self.ids).capture()
        self.assertEqual(report["batteryPercent"], 83)
        self.assertNotIn("uptime", report)
        self.assertEqual(ApiClient("buoy_SIM", "FAKE_TEST_CREDENTIAL_ONLY", self.transport).post_health(report)["status"], 201)
        self.assertEqual(self.transport.calls[0]["path"], "/api/v1/device/health")

    def test_pair_only_physical_event(self):
        gate = PairingGate()
        self.assertFalse(gate.authorize("RESET", True))
        self.assertFalse(gate.authorize("SETUP", True))
        self.assertFalse(gate.authorize("PAIR", False))
        self.assertTrue(gate.authorize("PAIR", True))
        self.assertTrue(gate.consume())
        self.assertFalse(gate.consume())

    def test_pair_authorization_revoked_by_other_action(self):
        gate = PairingGate()
        gate.authorize("PAIR", True)
        self.assertFalse(gate.authorize("RESET", True))
        self.assertFalse(gate.consume())


if __name__ == "__main__":
    unittest.main()
