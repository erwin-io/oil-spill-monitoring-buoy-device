"""Module D independent startup and long-running software runtime tests."""
import unittest

import main
from app.runtime import FirmwareRuntime
from config import default_config
from tests.fakes.device import FakeBoard


class Clock:
    def __init__(self):
        self.now = 0
    def ticks_ms(self):
        return self.now
    def ticks_diff(self, now, before):
        return now - before
    def sleep_ms(self, ms):
        self.now += ms


class ModuleDRuntimeTests(unittest.TestCase):
    def test_no_sensor_startup_runs_offline(self):
        result = main.run()
        self.assertEqual(result["state"], "RUNNING_OFFLINE")
        self.assertEqual(result["sensor"], "NOT_INSTALLED")
        self.assertEqual(result["actuators"], "DISABLED")

    def test_software_startup_does_not_need_verified_board(self):
        result = main.run(board=FakeBoard(False))
        self.assertEqual(result["reason"], "SENSOR_PENDING_HARDWARE_UNBOUND")
        self.assertEqual(result["state"], "RUNNING_OFFLINE")

    def test_resident_service_reports_live_status(self):
        messages = []
        status = main.serve_forever(clock=Clock(), output=messages.append, max_ticks=5)
        self.assertEqual(status["state"], "RUNNING_OFFLINE")
        self.assertEqual(status["scientificMeasurements"], 0)
        self.assertIn("services active", messages[1])
        self.assertEqual(main.status()["state"], "RUNNING_OFFLINE")

    def test_real_timer_reports_heartbeat_without_cloud(self):
        clock = Clock()
        runtime = FirmwareRuntime(main.run(), default_config(), clock, heartbeat_ms=1000)
        clock.now = 1000
        self.assertIn("heartbeat", runtime.tick())
        self.assertEqual(runtime.snapshot()["heartbeatCount"], 1)
        self.assertEqual(runtime.snapshot()["uptimeSeconds"], 1)

    def test_measurement_due_is_skipped_without_module_e(self):
        clock = Clock()
        settings = default_config()
        settings["samplingIntervalMinutes"] = 1
        runtime = FirmwareRuntime(main.run(), settings, clock)
        clock.now = 60000
        self.assertEqual(runtime.tick(), "Measurement scheduled: SKIPPED_SENSOR_UNAVAILABLE")
        self.assertEqual(runtime.snapshot()["skippedSensorCycles"], 1)
        self.assertEqual(runtime.snapshot()["scientificMeasurements"], 0)

    def test_no_catchup_burst_after_long_downtime(self):
        clock = Clock()
        settings = default_config()
        settings["samplingIntervalMinutes"] = 1
        runtime = FirmwareRuntime(main.run(), settings, clock)
        clock.now = 3600000
        self.assertTrue(runtime.tick())
        runtime.tick()  # A heartbeat may be emitted; do not duplicate a sample.
        self.assertEqual(runtime.skipped_sensor_cycles, 1)

    def test_tick_does_not_generate_fake_measurement(self):
        clock = Clock()
        runtime = FirmwareRuntime(main.run(), default_config(), clock)
        for _ in range(2):
            clock.now += 900000
            runtime.tick()
        self.assertEqual(runtime.snapshot()["scientificMeasurements"], 0)
        self.assertEqual(runtime.snapshot()["skippedSensorCycles"], 2)

    def test_finite_loop_writes_no_flash_files(self):
        events = []
        main.serve_forever(clock=Clock(), output=events.append, max_ticks=2)
        self.assertFalse(any("uploaded" in x.lower() for x in events))

    def test_bad_heartbeat_rejected(self):
        with self.assertRaises(ValueError):
            FirmwareRuntime(main.run(), default_config(), Clock(), heartbeat_ms=0)

    def test_invalid_cloud_config_faults_even_without_hardware(self):
        settings = default_config()
        settings["samplingIntervalMinutes"] = 0
        result = main.run(settings=settings)
        self.assertEqual(result["state"], "FAULT")
        self.assertEqual(result["reason"], "INVALID_CONFIG")

    def test_service_does_not_run_on_fault(self):
        settings = default_config()
        settings["samplingIntervalMinutes"] = 0
        events = []
        result = main.serve_forever(settings=settings, output=events.append,
                                    clock=Clock(), max_ticks=3)
        self.assertEqual(result["state"], "FAULT")
        self.assertIsNone(main.RUNTIME)

    def test_keyboard_interrupt_returns_to_repl(self):
        class StopClock(Clock):
            def sleep_ms(self, ms):
                raise KeyboardInterrupt()
        status = main.serve_forever(clock=StopClock(), output=lambda msg: None)
        self.assertEqual(status["state"], "RUNNING_OFFLINE")


if __name__ == "__main__":
    unittest.main()
