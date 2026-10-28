# ESP32-S3 N16R8 GPIO allocation — PROPOSED, NOT WIRED

Recorded 2026-10-28 for the BlueGuard Buoy hardware audit. All component settings are centralized in config.py with enabled=False. No pump, UV LED, valve, modem or GPIO is initialized by current Stage 1 firmware. This is **not** an electrical certificate or approval to attach modules without verifying the actual hardware.

## 23 unique direct GPIO allocations

| ESP32 GPIO | Interface | Component or signal | Physical implementation assumption |
|---:|---|---|---|
| 1 | ADC1 input | Battery sense | Calibrated voltage divider, RC filter |
| 2 | ADC1 input | Solar/charger input sense | Divider matched to highest expected panel voltage |
| 4 | Output | Sample peristaltic pump | Protected MOSFET driver with hardware OFF default |
| 5 | Output | Wash pump | Protected MOSFET driver with hardware OFF default |
| 6 | Output | Cleaner dosing pump | Protected MOSFET driver with hardware OFF default |
| 7 | Output | Normally-closed intake valve | Flyback-protected driver with hardware OFF |
| 8 | I2C0 SDA | AS7341 and DS3231 | Shared 3.3 V bus, suitable pullups |
| 9 | I2C0 SCL | AS7341 and DS3231 | AS7341=0x39, DS3231=0x68 |
| 10 | SPI CS | microSD | Card-select line |
| 11 | SPI MOSI | microSD | MCU to card |
| 12 | SPI SCK | microSD | Card clock |
| 13 | SPI MISO | microSD | Card to MCU |
| 14 | Output | Normally-closed wash valve | Flyback-protected driver, safe OFF |
| 15 | RTC-capable button input | Physical PAIR | Separate cloud ownership confirmation action |
| 16 | RTC-capable button input | Physical SETUP | Authorizes local Wi-Fi AP, not cloud ownership |
| 17 | UART1 TX | A7670C RXD | Validate breakout UART voltage conversion |
| 18 | UART1 RX | A7670C TXD | Validate modem-output logic level |
| 21 | Output/PWM | 365 nm UV excitation LED driver | External constant-current driver, hardware OFF |
| 39 | Digital input, JTAG-shared | Leak detection | Optional verified dry-contact/level-shifted signal |
| 40 | Digital input, JTAG-shared | microSD card-detect | Only if socket has a detect switch |
| 41 | Digital input, JTAG-shared | Logical RESET button | Different from MCU EN hard-reset switch |
| 42 | Digital input, JTAG-shared | Flow pulse sensor | Reserved pending Module F sensor selection |
| 47 | Output | A7670C PWRKEY control | Transistor/open-drain interface; not raw direct wiring |

### Pin audit and alternatives

- All 23 assigned physical GPIO numbers are unique; the two I2C devices deliberately share **one** SDA and **one** SCL connection, not independent pins. Neither AS7341 INT nor RTC alarm is required for first iteration; both are polled. Deep-sleep scheduling can use an ESP32 timer with DS3231 timestamp checks. If an external DS3231 alarm interrupt later becomes mandatory, this exact allocation must be revised to dedicate a spare RTC-capable GPIO.
- GPIO15 and GPIO16 can participate in ESP32-S3 RTC wake, keeping physical PAIR/SETUP usable from sleep subject to MicroPython support. RESET on GPIO41 is a software-handled maintenance action while the MCU is awake. The existing EN button is an independent reset that uses no GPIO allocation.
- GPIO39–42 have external JTAG alternate functions, so this plan assigns them **inputs only**; USB Serial/JTAG is preserved on GPIO19/20. If external JTAG via pads 39–42 is required, use a GPIO expander or a different mapping.
- GPIO38/48 are reserved for the DevKitC board-revision-dependent RGB LED; GPIO0,3,45,46 are boot straps; GPIO19/20 are USB; GPIO43/44 are UART0; GPIO26–37 are not allocated to peripherals because of internal flash/Octal PSRAM. Do not assume GPIO22–25 are normal exposed S3 header pins.
- A 4-point passive seawater intake manifold and the coconut-husk/charcoal treatment do not use GPIOs unless additional powered valves or level sensors are actually specified. No independent GPS is required by Module D #47. Firmware scheduling, ML and watchdog need no extra signal pins.
- Extra I2C temperature, current or fuel-gauge modules may share GPIO8/9 if addresses, 3.3 V levels and pullups are verified. Additional powered valves, a dedicated A7670C RESET, RTC SQW wake or more flow/level sensors would consume further I/O or justify a protected expander.

## Hardware verification blockers (do NOT bypass)

1. **Actual N16R8 carrier:** identify exact ESP32-S3 dev board revision and breakouts; RGB LED may be GPIO38 or GPIO48. Audit USB bridge, headers, flash/PSRAM and debug port availability.
2. **Actual A7670C carrier:** determine regulator input, 1.8 V raw UART vs 3.3 V translated UART, PWRKEY transistor behavior, supported firmware baud, separate ampere-class LTE peak supply and bulk capacitors. GPIO47 must never connect directly to a raw modem PWRKEY.
3. **UV/pumps/valves:** use separately rated LED constant-current driver, MOSFET/relay driver, flyback protection and external biasing that forces all loads OFF through ESP32 reset, bootloader, brownout, USB upload, or deep sleep. High-current loads must not draw from an ESP32 I/O pin.
4. **Sensing:** do not directly expose ESP32 ADC to the battery or panel. Confirm nominal and maximum voltage, divider tolerance, 0.1 uF filtering and calibrated ADC results. Protect leak/flow input levels and cable noise.
5. **I2C/SPI:** AS7341 and DS3231 are address-distinct on one bus (0x39 vs 0x68), but actual module pullups and RTC breakout charge behavior must be checked. SD needs true 3.3 V signals and a tested MicroPython SPI SDCard(slot=2) configuration. Card-detect GPIO40 is a reservation, not a promise your socket has a switch.
6. **Original ownership protocol:** PAIR, SETUP, RESET remain physically and logically distinct; neither SETUP nor RESET can bypass a server-confirmed claim.

This plan alone does not verify supply current, solar battery chemistry/charging, sleep power, modem TLS, or water ingress. The approved hardware build and E/F/G electrical/optical tests remain separate.

## Firmware guard

All non-board configs in config.py remain enabled=False. validate_hardware_config checks schema, exact shared I2C pins, unique physical GPIOs, reserved-pin exclusions, ADC1 usage, RTC-capable physical buttons and no actuator/JTAG-output collision. drivers/unbound.py still returns False; the default boot remains UNCONFIGURED. The firmware manifest needs no update: config.py is already tracked.

## References

- Espressif DevKitC-1 v1.1: https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html
- Espressif ESP32-S3 GPIO limitations: https://docs.espressif.com/projects/esp-idf/en/v5.1/esp32s3/api-reference/peripherals/gpio.html
- MicroPython SDCard for ESP32-S3 custom pins: https://docs.micropython.org/en/latest/library/machine.SDCard.html
- SIMCom A7670X hardware design: https://datasheet.lcsc.com/lcsc/2403041653_SIMCom-Wireless-Solutions-A7670C-LNNV_C21264492.pdf
- Adafruit AS7341 bus breakout reference: https://learn.adafruit.com/adafruit-as7341-10-channel-light-color-sensor-breakout/pinouts
