"""Non-secret first-boot setup storage; no ownership or upload credential storage."""
import binascii
import json
import os

SETUP_FILE = "/blueguard-setup.json"
KEY_FILE = "/blueguard-ap-key.txt"

def _is_missing(exc):
    """MicroPython OSError often exposes errno in args[0], not .errno."""
    code = getattr(exc, "errno", None)
    if code is None:
        args = getattr(exc, "args", ())
        code = args[0] if args else None
    return code == 2



def validate_settings(data):
    if not isinstance(data, dict) or set(data) != {"label", "apn"}:
        raise ValueError("Unexpected setup fields")
    label, apn = data["label"], data["apn"]
    if not isinstance(label, str) or not 1 <= len(label) <= 30:
        raise ValueError("Invalid device label length")
    if not isinstance(apn, str) or not 1 <= len(apn) <= 64:
        raise ValueError("Invalid APN length")
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-" for c in label):
        raise ValueError("Invalid label characters")
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_" for c in apn):
        raise ValueError("Invalid APN characters")
    return {"label": label, "apn": apn}


class ProvisioningStore:
    def __init__(self, path=SETUP_FILE, key_path=KEY_FILE):
        self.path = path
        self.key_path = key_path

    def load(self):
        try:
            with open(self.path, "r") as f:
                record = json.load(f)
        except OSError as exc:
            if _is_missing(exc):
                return None
            raise
        if not isinstance(record, dict) or record.get("schema") != 1:
            raise ValueError("Corrupted provisioning record")
        return validate_settings(record.get("settings"))

    def save_once(self, settings):
        data = validate_settings(settings)
        if self.load() is not None:
            raise ValueError("Already provisioned; cannot overwrite through AP")
        temp = self.path + ".new"
        try:
            with open(temp, "w") as f:
                json.dump({"schema": 1, "settings": data}, f)
                f.flush()
            os.rename(temp, self.path)
        except Exception:
            try:
                os.remove(temp)
            except OSError:
                pass
            raise
        return data

    def password(self):
        try:
            with open(self.key_path, "r") as f:
                password = f.read().strip()
            if len(password) != 16 or any(c not in "0123456789abcdef" for c in password):
                raise ValueError("Bad stored AP password")
            return password
        except OSError as exc:
            if not _is_missing(exc):
                raise
        password = binascii.hexlify(os.urandom(8)).decode()
        temp = self.key_path + ".new"
        try:
            with open(temp, "w") as f:
                f.write(password)
                f.flush()
            os.rename(temp, self.key_path)
        except Exception:
            try:
                os.remove(temp)
            except OSError:
                pass
            raise
        return password
