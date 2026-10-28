"""Resident BlueGuard Module D heartbeat, scheduling and status service.

No UART/ADC/I2C/SPI/machine/network import, GPIO, filesystem write or cloud
upload. This runs on a bare ESP32-S3 while Module E is absent. A later module
can attach real drivers only after electrical verification and durable queue.
"""
import time

from app.scheduler import PeriodicScheduler


class SystemClock:
    def ticks_ms(self):
        if hasattr(time, "ticks_ms"):
            return time.ticks_ms()
        return int(time.monotonic() * 1000)

    def ticks_diff(self, now, before):
        if hasattr(time, "ticks_diff"):
            return time.ticks_diff(now, before)
        return now - before

    def sleep_ms(self, ms):
        if hasattr(time, "sleep_ms"):
            return time.sleep_ms(ms)
        return time.sleep(ms / 1000.0)


class FirmwareRuntime:
    def __init__(self, startup, settings, clock, heartbeat_ms=60000):
        if startup["state"] != "RUNNING_OFFLINE":
            raise ValueError("Cannot start scheduler from a non-running state")
        if type(heartbeat_ms) is not int or heartbeat_ms < 1000:
            raise ValueError("Invalid heartbeat interval")
        self.startup = dict(startup)
        self.clock = clock
        self.started_ms = clock.ticks_ms()
        self.last_heartbeat_ms = self.started_ms
        self.heartbeat_ms = heartbeat_ms
        self.schedule = PeriodicScheduler(
            clock, settings["samplingIntervalMinutes"] * 60000)
        self.heartbeat_count = 0
        self.skipped_sensor_cycles = 0

    def tick(self):
        """Call frequently from the main loop; return message on a milestone."""
        if self.schedule.due():
            # Safety: no UV-OFF/ON calibration means NO measurement, upload,
            # false oil detection, classification or synthetic scientific data.
            self.skipped_sensor_cycles += 1
            return "Measurement scheduled: SKIPPED_SENSOR_UNAVAILABLE"
        now = self.clock.ticks_ms()
        if self.clock.ticks_diff(now, self.last_heartbeat_ms) >= self.heartbeat_ms:
            self.last_heartbeat_ms = now
            self.heartbeat_count += 1
            return "BlueGuard heartbeat | RUNNING_OFFLINE | sensor=NOT_INSTALLED"
        return None

    def snapshot(self):
        uptime_ms = self.clock.ticks_diff(self.clock.ticks_ms(), self.started_ms)
        return {
            "state": self.startup["state"],
            "reason": self.startup["reason"],
            "sensor": "NOT_INSTALLED",
            "modem": "NOT_CONNECTED",
            "cloud": "OFFLINE",
            "actuators": "DISABLED",
            "uptimeSeconds": max(0, uptime_ms // 1000),
            "heartbeatCount": self.heartbeat_count,
            "skippedSensorCycles": self.skipped_sensor_cycles,
            "scientificMeasurements": 0,
        }
