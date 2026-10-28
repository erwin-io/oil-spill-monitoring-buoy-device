"""Trusted factory-only provisioning for a physically attached ESP32-S3.

Requires a backend-registered device ID and its one-time-issued upload key.
Never accepts a mobile claimCode in place of the deviceKey. Never prints keys.
Example:
  py -3 tools/factory_provision.py --port COM15 --device-id buoy_001 \
      --api-host YOUR_VERIFIED_HOST --ca-der C:\\trusted\\root-ca.der
The QR v2 customer label contains ONLY the factory-registered fixed deviceId;
no long-term deviceKey, claimCode or session secret is permitted in QR.
"""
import argparse
import getpass
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
ID=re.compile(r"^[A-Za-z0-9_-]{1,80}$")
KEY=re.compile(r"^[A-Za-z0-9_-]{32,128}$")
HOST=re.compile(r"^[A-Za-z0-9.-]{4,180}$")
PORT=re.compile(r"^COM[1-9][0-9]*$",re.I)

def plan(device_id,device_key,host,ca_der):
    if not ID.fullmatch(device_id) or not KEY.fullmatch(device_key):
        raise ValueError("Invalid backend-issued device identity/secret")
    if not HOST.fullmatch(host) or "." not in host or host.startswith("."):
        raise ValueError("Invalid HTTPS hostname")
    if not isinstance(ca_der,bytes) or not 100<=len(ca_der)<=8192 or ca_der[0]!=0x30:
        raise ValueError("Expected trusted DER CA certificate")
    return (
        {"schema":1,"deviceId":device_id,"deviceKey":device_key},
        {"schema":1,"host":host,"caDerPath":"/blueguard-root-ca.der"},
    )

def _run(port,*args):
    cmd=[sys.executable,"-m","mpremote","connect",port,*args]
    result=subprocess.run(cmd,check=False,capture_output=True,timeout=45)
    if result.returncode:
        # Never print mpremote error output that might contain stored secrets.
        raise RuntimeError("Device serial operation failed; check COM port")
    return result.stdout.decode("ascii",errors="replace")

def provision(port,device_id,host,ca_path,secret):
    if not PORT.fullmatch(port):
        raise ValueError("Invalid COM port")
    ca=pathlib.Path(ca_path).read_bytes()
    identity,profile=plan(device_id,secret,host,ca)
    probe=_run(port,"exec","import sys,os; print('BLUEGUARD_BOARD',sys.implementation.name,os.uname().machine)")
    if "blueguard_board micropython" not in probe.lower():
        raise RuntimeError("Target did not identify as MicroPython")
    if "esp32s3" not in probe.lower() and "esp32-s3" not in probe.lower():
        raise RuntimeError("Target is not ESP32-S3")
    with tempfile.TemporaryDirectory(prefix="blueguard-factory-") as d:
        temp=pathlib.Path(d)
        files=[("identity.json","blueguard-identity.json",json.dumps(identity).encode()),
               ("cloud.json","blueguard-cloud.json",json.dumps(profile).encode()),
               ("ca.der","blueguard-root-ca.der",ca)]
        for local,remote,blob in files:
            name=temp/local
            with open(name,"wb") as f:
                f.write(blob)
            try:
                os.chmod(name,0o600)
            except OSError:
                pass
            _run(port,"fs","cp",str(name),":/"+remote)
    # Do not echo identity, device upload key or certificate to terminal.
    return "Factory files installed. Power-cycle board to activate cellular pairing."

def main():
    p=argparse.ArgumentParser(description="Provision backend-registered BlueGuard ESP32")
    p.add_argument("--port",required=True)
    p.add_argument("--device-id",required=True)
    p.add_argument("--api-host",required=True)
    p.add_argument("--ca-der",required=True)
    args=p.parse_args()
    key=getpass.getpass("Enter the backend-issued DEVICE UPLOAD KEY (not QR claim code): ")
    try:
        print(provision(args.port,args.device_id,args.api_host,args.ca_der,key))
    except (ValueError,OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
        # Never print key, host response, exception body or temporary path.
        print("Factory provisioning failed: "+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)

if __name__=="__main__":
    main()
