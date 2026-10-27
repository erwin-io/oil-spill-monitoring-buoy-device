# Hardware mapping — pending verification

No ESP32-S3 GPIO allocations, electrical pin levels, modem UART pins, PAIR/SETUP switch wiring, actuator polarity, watchdog behavior, or safe output defaults have been confirmed by physical inspection. Stage 1 intentionally imports no machine module and never toggles unknown pins.

Before real drivers are enabled, record board revision, A7670C module/firmware variant, actual regulator supply and peak load, schematic/photos, pin polarity, safety interlocks and validated boot safe states with Module F/G owners.

Do not treat FakeBoard or the Stage 1 SAFE_IDLE software state as physical safety evidence.
