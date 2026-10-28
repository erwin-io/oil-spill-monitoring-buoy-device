# Hardware mapping — pending verification

The sole source-controlled hardware pin-configuration location is `config.py`:
- `BOARD_CONFIG["model"]`: `ESP32-S3-N16R8`.
- `A7670C_CONFIG["uart_id"]`: `1` (provisional UART assignment).
- `A7670C_CONFIG["baudrate"]`: `115200` (provisional; modem firmware must be probed).
- `A7670C_CONFIG["tx_pin"]`, `["rx_pin"]`, `["pwrkey_pin"]` and `["reset_pin"]` remain `None`.
- `A7670C_CONFIG["enabled"]` remains `False`. Stage 1 validation rejects attempts to enable the modem.

A UART number and baud rate are not approved wiring. No ESP32-S3 GPIO allocations, modem logic levels, SIM power supply, PWRKEY polarity, RESET drive, PAIR/SETUP switch wiring, actuator polarity, watchdog behavior or safe output defaults have been verified. Assignments may be recorded in config.py after inspecting the actual board, but activation requires separate real-driver review.

Some bare SIMCom modules use modem-side UART voltages different from ESP32-S3 3.3 V logic. Verify the actual A7670C carrier board, regulator, UART level shifting, power supply transient capability and PWRKEY/RESET drive circuitry *before attaching UART/control signals*. Never drive a bare module's UART or VBAT based solely on a pin-name match.

Boot remains passive, and the default UnboundBoard never toggles a GPIO. This refactor adds only public defaults and side-effect-free validation. Before real drivers are enabled, record actual regulator, peak current, module variant and pin assignments with Module F/G owners.

Do not treat FakeBoard SAFE_IDLE or passing desktop tests as physical safety evidence.
