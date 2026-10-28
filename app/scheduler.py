"""Periodic monotonic scheduler for Module D without a hardware requirement.

No measurements are synthesized. A missed due event while the sensor is
unavailable counts as SKIPPED_SENSOR_UNAVAILABLE, not a cloud measurement.
"""


class PeriodicScheduler:
    def __init__(self, clock, interval_ms):
        if type(interval_ms) is not int or interval_ms < 1000:
            raise ValueError("Invalid scheduling interval")
        self.clock = clock
        self.interval_ms = interval_ms
        self.last_due_ms = clock.ticks_ms()

    def due(self):
        now = self.clock.ticks_ms()
        if self.clock.ticks_diff(now, self.last_due_ms) < self.interval_ms:
            return False
        # No catch-up burst after long downtime; one opportunity per tick.
        self.last_due_ms = now
        return True
