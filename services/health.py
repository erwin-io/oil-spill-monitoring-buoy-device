"""Health reporting with fake or future physical reader injected."""
from services.contracts import HEALTH_OPTIONAL, validate_health


class HealthService:
    def __init__(self, health_source, clock, ids):
        self.health_source = health_source
        self.clock = clock
        self.ids = ids

    def capture(self):
        readings = self.health_source.read_health()
        payload = {"healthId": self.ids.next_id("h"), "measuredAt": self.clock.iso_now()}
        for key in HEALTH_OPTIONAL:
            if key in readings:
                payload[key] = readings[key]
        # No uptime field: backend strict health contract does not accept it.
        return validate_health(payload)
