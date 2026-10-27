"""Measurement preparation using an interchangeable sample, clock and ID source."""
from services.contracts import validate_measurement


class TelemetryService:
    def __init__(self, measurement_source, clock, ids):
        self.measurement_source = measurement_source
        self.clock = clock
        self.ids = ids

    def capture(self):
        sample = self.measurement_source.read_measurement()
        # Explicit allow-list avoids sending sensor-specific secret/debug fields.
        payload = {
            "measurementId": self.ids.next_id("m"),
            "measuredAt": self.clock.iso_now(),
            "classification": sample["classification"],
            "confidence": sample["confidence"],
            "spectral": dict(sample["spectral"]),
            "totalFluorescence": sample["totalFluorescence"],
        }
        if "qualityFlags" in sample:
            payload["qualityFlags"] = list(sample["qualityFlags"])
        return validate_measurement(payload)
