# BlueGuard Module D cellular, secure HTTPS and physical PAIR

Software implemented; REAL modem, certificate and phone acceptance outstanding.

## Auto boot, no F5

After AP setup stores the label and APN, main.py automatically starts
CellularService on the ESP32-S3. If factory provisioned device identity, API
host and trusted DER CA are present, it configures UART1 GPIO17 TX and GPIO18 RX,
probes A7670C with AT, checks SIM and LTE registration, uses the saved Smart
APN, dials ATD*99***1#, and creates a MicroPython network.PPP interface.
It synchronizes UTC using NTP, then connects to the exact HTTPS host with
MicroPython ssl.CERT_REQUIRED and server_hostname verification and reviewed
root CA. No trust-all SSL or plaintext HTTP fallback exists.
After this, physical GPIO15 PAIR button triggers the approved cloud challenge,
and real health reports are uploaded without made-up UV data.
On failure, firmware remains operational locally and attempts recovery.

The code does NOT power-cycle or assert GPIO47 PWRKEY; it expects the installed
modem to be independently powered. Do not wire raw PWRKEY directly to ESP32.

## One-time factory provisioning (not a boot-time manual command)

An authorized backend administrator must register the buoy using
POST /api/v1/devices, obtaining the deviceId, one-time deviceKey and distinct
claimCode. Existing active IDs/keys must not be recreated or rotated casually.
The firmware cannot invent or obtain the admin-issued upload key.

Obtain a reviewed DER CA certificate for the actual HTTPS API certificate
chain. Do not blindly trust an arbitrary downloaded CA. From PowerShell,
after closing Thonny COM port:

    py -3 tools/factory_provision.py --port COM15 --device-id BACKEND_DEVICE_ID --api-host ACTUAL_API_HOST --ca-der C:\trusted\ca.der

The tool prompts securely for the backend-issued deviceKey. It installs
three files outside Git/deployment manifest:
 /blueguard-identity.json: schema, deviceId and deviceKey
 /blueguard-cloud.json: schema, host and caDerPath
 /blueguard-root-ca.der: approved root certificate

Do not copy deviceKey into the protected QR, local Wi-Fi AP form or logs.
The mobile app protected internal QR must instead contain JSON fields:
v:1, deviceId, claimCode. The claimCode is server-generated and different
from the deviceKey. Plain MicroPython filesystem is not encrypted by default:
hardware-backed secure boot/flash encryption and production manufacturing
provisioning remain security requirements.

## Hardware pairing acceptance

Power-cycle ESP32. A connected, registered SIM should progress to
MODEM_CONNECTING, TIME_SYNCING and CLOUD_READY (actual device log evidence).
The GPIO15 physical PAIR button must be a distinct switch to GND with a
suitable pull-up. Press it to initiate the device-authenticated 5-min pairing
challenge. In the BlueGuard mobile app with internet, Add Device, scan the
protected internal QR or enter the correct ID + claimCode. Device confirms
the candidate through authenticated HTTPS with the server nonce.
Cloud Owner assignment is server-authoritative, not set by local Wi-Fi AP.
After success the app refreshes My Buoys. Real health is viewable independently
of UV sensor installation; no artificial petroleum measurements are uploaded.

## Mandatory physical/production acceptance, not proven by desktop CI

- A7670C must truly respond on wired ESP32 UART; SIM and LTE must register
  and network.PPP must connect on installed MicroPython firmware.
- ESP32 MicroPython SSL implementation must verify DER CA, time and hostname.
  Test wrong-host, expired and untrusted server certificates; all MUST fail.
- Confirm Smart data plan/APN, power/level shifting and physically connected
  PAIR button. Never toggle unverified GPIO47/PWRKEY.
- Actual backend-created device identity and reviewed CA are necessary.
- Real pairing confirmation and health acceptance must be observed in the
  API/mobile app, not inferred from fake CI results.
- No Module E UV/AS7341 optical equipment is necessary for cloud pairing.
