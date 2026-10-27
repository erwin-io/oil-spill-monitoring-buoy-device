"""Thin authenticated API boundary. HTTP transport is ALWAYS injected.

Stage 1 uses fake transport exclusively; no socket/requests implementation exists.
Payload durability, LTE/TLS and backoff are separate later-stage obligations.
"""
from services.contracts import validate_health, validate_measurement


class ApiClient:
    def __init__(self, device_id, device_key, transport):
        self._id = device_id
        self._key = device_key
        self._transport = transport
        if not isinstance(device_id, str) or not device_id or not isinstance(device_key, str) or not device_key:
            raise ValueError("Missing device identity or test credential")

    def _post(self, endpoint, payload):
        headers = {"X-Device-ID": self._id, "X-Device-Key": self._key,
                   "Content-Type": "application/json"}
        # Never log headers, payload or transport errors containing credentials.
        return self._transport.request("POST", "/api/v1/device/" + endpoint, headers, payload)

    def post_measurement(self, payload):
        return self._post("measurements", validate_measurement(payload))

    def post_health(self, payload):
        return self._post("health", validate_health(payload))
