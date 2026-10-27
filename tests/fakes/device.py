"""Deterministic components used only in desktop and CI tests."""


class FakeBoard:
    def __init__(self, safe=True):
        self.safe = safe
        self.calls = []

    def set_safe_outputs(self):
        self.calls.append("set_safe_outputs")
        return self.safe


class FakeClock:
    def iso_now(self):
        return "2026-10-28T04:13:00+08:00"


class FakeIds:
    def __init__(self):
        self.count = 0

    def next_id(self, prefix):
        self.count += 1
        return prefix + "_SIM_" + str(self.count)


class FakeMeasurementSource:
    def read_measurement(self):
        return {
            "classification": "NORMAL", "confidence": 0.9,
            "spectral": {"f415": 1.0, "f445": 2.0, "f480": 1.3,
                         "f515": 0.8, "f555": 0.7, "f590": 0.4},
            "totalFluorescence": 6.2,
            "qualityFlags": ["SIMULATED_DO_NOT_USE_FOR_SCIENCE"],
        }


class FakeHealthSource:
    def read_health(self):
        return {"batteryPercent": 83, "charging": False,
                "signalStrengthDbm": -85, "sensor": "SIMULATED",
                "storage": "SIMULATED", "samplePump": "OFF", "washPump": "OFF",
                "valve": "CLOSED", "pendingUploads": 0}


class FakeTransport:
    """No sockets or calls to external APIs. Returns fixed test responses."""
    def __init__(self):
        self.calls = []

    def request(self, method, path, headers, payload):
        self.calls.append({"method": method, "path": path,
                           "headers": dict(headers), "payload": dict(payload)})
        # Return a synthetic response, never a claim of external acceptance.
        return {"status": 201, "simulated": True, "accepted": True}


class FailIfContactedTransport:
    def request(self, *args):
        raise AssertionError("Unexpected external transport call")
