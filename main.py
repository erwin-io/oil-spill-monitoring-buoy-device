"""BlueGuard Module D startup: real resident software service, no fake oil readings.

MicroPython executes this on boot. Physical modem/actuators remain electrically
gated, but their absence never prevents the local scheduler and diagnostics.
"""
from app.controller import DeviceController
from app.runtime import FirmwareRuntime, SystemClock
from config import default_config, default_hardware_config
from drivers.unbound import UnboundBoard

RUNTIME = None


def run(board=None, settings=None, hardware=None):
    """Validate and start services without requiring a Module E optical sensor."""
    if board is None:
        board = UnboundBoard()
    if settings is None:
        settings = default_config()
    if hardware is None:
        hardware = default_hardware_config()
    return DeviceController(board, settings, hardware).start()


def status():
    """Inspection from Thonny after Ctrl+C; never triggers hardware activity."""
    if RUNTIME is None:
        return {"state": "NOT_STARTED"}
    return RUNTIME.snapshot()


def serve_forever(board=None, settings=None, hardware=None, clock=None,
                  output=print, max_ticks=None):
    """Run the Module D heartbeat and scheduler. Ctrl+C releases the REPL.

    max_ticks is for finite deterministic tests only; normal boot is resident.
    """
    global RUNTIME
    RUNTIME = None
    if settings is None:
        settings = default_config()
    startup = run(board=board, settings=settings, hardware=hardware)
    output("BlueGuard Buoy | " + startup["state"] + " | " + startup["reason"])
    if startup["state"] == "FAULT":
        return startup
    if clock is None:
        clock = SystemClock()
    RUNTIME = FirmwareRuntime(startup, settings, clock)
    output("Module D services active | sensor=NOT_INSTALLED | modem=NOT_CONNECTED")
    loops = 0
    try:
        while True:
            event = RUNTIME.tick()
            if event:
                output(event)
            if max_ticks is not None:
                loops += 1
                if loops >= max_ticks:
                    return RUNTIME.snapshot()
            clock.sleep_ms(250)
    except KeyboardInterrupt:
        output("BlueGuard service stopped by operator; hardware outputs untouched")
        return RUNTIME.snapshot()


if __name__ == "__main__":
    # CPython on the developer PC does not enter an unbounded loop.
    try:
        import sys
        if sys.implementation.name == "micropython":
            serve_forever()
        else:
            print("BlueGuard Buoy | " + run()["state"])
    except Exception:
        # Startup failures are not allowed to initiate any physical actions.
        print("BlueGuard Buoy | FAULT | SOFTWARE_STARTUP_FAILURE")
        raise
