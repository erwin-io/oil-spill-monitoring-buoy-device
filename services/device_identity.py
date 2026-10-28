"""Read trusted factory-provisioned device identity outside the upload manifest.

Upload key is PRIVATE and must never be shared through local AP, mobile QR,
serial logs or Git. MicroPython flash lacks guaranteed encryption by default;
real shipping requires flash encryption/secure boot + protected provisioning.
"""
import json

DEFAULT_PATH="/blueguard-identity.json"


class IdentityNotProvisioned(ValueError):
    pass


def load_identity(path=DEFAULT_PATH):
    try:
        with open(path,"r") as f:
            body=f.read(640)
            if len(body)>=640 or f.read(1):
                raise IdentityNotProvisioned("Identity record too large")
        data=json.loads(body)
    except (OSError,ValueError):
        raise IdentityNotProvisioned("Identity not provisioned/invalid")
    if not isinstance(data,dict) or set(data)!={"schema","deviceId","deviceKey"} or data["schema"]!=1:
        raise IdentityNotProvisioned("Identity not provisioned/invalid")
    device_id=data["deviceId"]
    key=data["deviceKey"]
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    if not isinstance(device_id,str) or not 1<=len(device_id)<=80 or any(c not in alphabet for c in device_id):
        raise IdentityNotProvisioned("Invalid device identity")
    if not isinstance(key,str) or not 32<=len(key)<=128 or any(c not in alphabet for c in key):
        raise IdentityNotProvisioned("Invalid device upload credential")
    return {"deviceId":device_id,"deviceKey":key}
