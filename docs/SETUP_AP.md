# BlueGuard first-boot Wi-Fi AP setup (ESP32-S3, Module D)

This is a working-code milestone awaiting physical browser testing, not a production acceptance claim.

## Device setup flow

1. With an unprovisioned ESP32-S3, upload firmware via the unchanged upload-firmware.bat command, then power-cycle. MicroPython main.py autonomously starts the resident firmware and a temporary Wi-Fi setup AP. No F5 is necessary.
2. Read the unique startup SSID BlueGuard-XXXXXX and unique WPA2 password from the physical USB serial console. This is a development-only credential handoff. Production hardware requires a protected factory label, not a serial console.
3. On a phone, join the BlueGuard hotspot. It will report no internet, which is expected. Open http://192.168.4.1/ in the normal phone browser. No captive portal pop-up is guaranteed.
4. Enter a local device label and your SIM operator's actual APN, then press Save. The page confirms local storage. The AP closes after a short grace period.
5. On the next boot, the AP does not reopen because a valid local settings record exists. The main scheduler still operates without Module E. Re-entry via a distinct verified physical SETUP button is a future electrical and security milestone.

Local files on flash: /blueguard-setup.json contains ONLY local label and APN, with a versioned schema. /blueguard-ap-key.txt contains a generated per-board AP password outside Git. Neither is added to the firmware upload manifest or returned by the HTTP service. Do not erase these to defeat cloud ownership; local setup is not cloud ownership.

## Security and limitations

- The AP is time-bounded (15 minutes on first boot) and WPA2-protected with a unique credential; the HTTP listener permits small, validated requests with Host, Origin, and CSRF checks.
- Local setup does not accept or show X-Device-Key, claimCode, SIM PIN, QR payload or pairing nonce. It never confers Owner or Viewer permissions, never changes the backend's ownership, and does not connect to production services.
- Saved APN is not yet applied to the A7670C; modem power, serial voltage compatibility, LTE registration and TLS remain pending. The UV/AS7341 sensor is not required for setup.
- The portal is local HTTP inside WPA2, not end-to-end HTTPS. Avoid use in hostile radio environments, and do not ship as a fully trusted production provisioning system until the physical SETUP button, per-device label, secure manufacturing and storage security are verified.
- A configured buoy no longer automatically opens the AP. If local settings are invalid/corrupt, the code fails closed. Hardware SETUP and controlled recovery need implementation before field deployment.

## Troubleshooting

If you see SETUP_AP_FAILED or the hotspot is not visible, capture the status/error class without sharing your unique Wi-Fi password. Check MicroPython WLAN AP support and exact firmware version. The scheduler should continue even if AP initialization fails. Confirm that the firmware is launched by /main.py at a power-on reset rather than only through Thonny F5.
