# BlueGuard Module D — QR v2 firmware / Smart LTE pairing

**Status:** QR v2 firmware protocol implemented in software; end-to-end physical ESP32-S3 + A7670C + Android + Firebase acceptance NOT established by CI.

**Authoritative implementation:** [API QR v2 contract](https://github.com/erwin-io/oil-spill-monitoring-buoy-api/blob/main/docs/QR_V2_DEVICE_PAIRING_CONTRACT.md). Mobile and API QR v2 software is already completed; do not reimplement their frozen contracts in the firmware repository.

## Simple customer journey (no claim code)

1. BlueGuard app → Add Device → Scan fixed ID-only QR, such as:
   \`{"v":2,"deviceId":"BG-000124"}\`
2. Mobile authenticates to API using Firebase, creates a five-minute pair intent for that exact ID, and displays "Press PAIR".
3. User physically presses the *separate* GPIO15 active-low PAIR button on that buoy. The firmware has no software/remote/API route that simulates this button.
4. ESP32-S3 authenticates to API through its independently provisioned A7670C LTE and certificate/hostname-verifying HTTPS, sending exactly \`{"protocol":2}\` to \`POST /api/v1/device/pairing-challenges\`.
5. API binds exactly one eligible waiting intent. Firmware validates the returned \`protocol,deviceId,intentId,challengeId,nonce,expiresAt\`; it never exposes the nonce to the phone or logs.
6. Firmware sends \`{"protocol":2,"intentId":"...","challengeId":"...","nonce":"..."}\` to \`POST /api/v1/device/pairing-confirmations\`, and accepts success only on HTTP 200 matching all correlation fields and \`state:"CONFIRMED"\`.
7. Firebase atomically assigns one owner; mobile sees CONFIRMED on its *own* authenticated intent status poll. There is NO direct phone-to-buoy link, BLE, or customer Wi-Fi AP setup.

The public QR can be created with an ordinary online QR generator, using the fixed *already-registered* device ID. Never place a private upload key, SIM credential or nonce into QR.

## Factory provisioning is DIFFERENT from customer pairing

The buoy requires a factory-issued permanent deviceId and deviceKey stored on-device, along with an approved HTTPS CA and configured SIM/APN. These are not short-lived pairing keys. This step is performed by an authorized factory operator once, separately from the customer scan/PAIR experience, and the device must never self-register with an invented secret.

With Thonny COM released on Windows, the existing device factory utility can provision identity and verified CA files:

    py -3 tools/factory_provision.py --port COM15 --device-id BACKEND_DEVICE_ID --api-host YOUR_APPROVED_API_HOST --ca-der C:\trusted\root-ca.der

The utility securely prompts for the one-time backend-issued \`deviceKey\`; it never writes it to Git or QR. These files remain outside firmware-manifest.json:

- \`/blueguard-identity.json\` — permanent device ID and upload key
- \`/blueguard-cloud.json\` — HTTPS host and CA path
- \`/blueguard-root-ca.der\` — approved public CA

Ordinary MicroPython flash is not guaranteed hardware-secret-protected. Production secure boot, flash encryption and a safe manufacturing/reprovisioning process remain separate acceptance gates.

The existing first-boot *factory/prototype* local setup portal saves only label and APN. It is NOT part of QR v2 customer pairing, never accepts ownership, and is retained pending separate authorized factory-setup deprecation. Its use does not prove cloud readiness.

## Autonomous A7670C connection

On normal MicroPython cold boot, the resident CellularService loads factory identity and verified trust config, then initializes ESP32 UART1 on proposed GPIO17 TX / GPIO18 RX, polls AT/SIM/LTE registration, uses the saved Smart SIM APN, dials PPP, synchronizes UTC and activates verified HTTPS communication and the physical PAIR GPIO15 input. Normal monitoring and health logic remain independent of Module E optics; no fabricated petroleum data is uploaded.

Modem PWRKEY on proposed GPIO47 is **not driven**: modem must be externally supplied/controlled safely. Do not directly connect GPIO47 to raw PWRKEY.

### Safe diagnostic states (sanitized serial output)

- Cellular: \`DEVICE_IDENTITY_MISSING\`, \`TLS_PROFILE_MISSING\`, \`MODEM_CONNECTING\`, \`TIME_SYNCING\`, \`CLOUD_READY\`, \`CONNECTIVITY_RETRY_PENDING\`.
- Pairing: \`IDLE\`, \`REQUESTING_CHALLENGE\`, \`INTENT_REQUIRED\`, \`CONFLICT\`, \`PROTOCOL_ERROR\`, \`CONFIRMING\`, \`RETRYING\`, \`EXPIRED\`, \`CONFIRMED\`, \`UNVERIFIED\`, \`REJECTED\`, \`AUTH_FAILED\`.

A missing intent or conflict does not cause fake ownership. \`UNVERIFIED\` means the confirmation response might have been lost; the phone/server has the authoritative answer. \`ALREADY_OWNED\` is not proof that this physical attempt succeeded.

### Test and deployment

From a Windows clone of the firmware repository:

    py -3 -m unittest discover -s tests -v
    py -3 tools/simulate.py
    py -3 main.py

After GitHub main/CI checks pass, close Thonny COM and run:

    .\upload-firmware.bat

The uploader synchronizes GitHub main and SHA-256 verifies manifest-listed files. Do NOT claim the physical board is current until this operation actually succeeds. The firmware manifest contains the cloud pairing, modem, TLS, health and physical PAIR drivers.

### Hardware acceptance still required

- UART voltage compatibility, SIM/LTE network registration, APN, PPP Internet connectivity, DNS and NTP clock.
- Valid CA and certificate hostname verification with negative tests (wrong host, expired/untrusted chain rejected).
- Actual GPIO15 PAIR wiring/debounce; no SETUP/RESET impersonation.
- API server authentication and real Firebase ownership confirmation on mobile Add Device.
- LED indicator can only be enabled after the board's actual LED GPIO and active level are verified; unknown RGB pins or pumps/UV must not be energized.
- Cross-device concurrency, competing intents, expiring intents, replay, mobile cancellation and loss of LTE must be checked using real equipment.
- Security limitation: public ID-only QR plus physical PAIR **does not prove phone proximity**. A malicious remote pre-intent may win if it is the sole waiting intent; competing intents fail closed but this risk remains until stronger local possession proof is approved.
