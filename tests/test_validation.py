import unittest
from config import default_config, validate_config
from services.contracts import validate_health, validate_measurement
from tests.fakes.device import FakeClock, FakeIds, FakeMeasurementSource
from services.telemetry import TelemetryService


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.record = TelemetryService(FakeMeasurementSource(), FakeClock(), FakeIds()).capture()

    def test_default_config_valid(self):
        self.assertEqual(validate_config(default_config()), default_config())

    def test_config_rejects_unknown_fields(self):
        config = default_config()
        config["X-Device-Key"] = "SHOULD_NEVER_BE_CONFIGURED"
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_config_rejects_boolean_integer(self):
        config = default_config()
        config["samplingIntervalMinutes"] = True
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_measurement_rejects_unknown_field(self):
        self.record["uploadSecret"] = "NOT_ALLOWED"
        with self.assertRaises(ValueError):
            validate_measurement(self.record)

    def test_measurement_rejects_invalid_confidence(self):
        self.record["confidence"] = 1.5
        with self.assertRaises(ValueError):
            validate_measurement(self.record)

    def test_measurement_rejects_missing_channel(self):
        del self.record["spectral"]["f415"]
        with self.assertRaises(ValueError):
            validate_measurement(self.record)

    def test_measurement_rejects_timestampless_clock(self):
        self.record["measuredAt"] = "2026-10-28T04:13:00"
        with self.assertRaises(ValueError):
            validate_measurement(self.record)

    def test_health_rejects_unapproved_uptime_field(self):
        with self.assertRaises(ValueError):
            validate_health({"healthId": "h_SIM", "measuredAt": "2026-10-28T04:13:00+08:00", "uptime": 120})

    def test_health_rejects_bad_queue(self):
        with self.assertRaises(ValueError):
            validate_health({"healthId": "h_SIM", "measuredAt": "2026-10-28T04:13:00+08:00", "queueDepth": -1})


if __name__ == "__main__":
    unittest.main()
