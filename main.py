"""BlueGuard Module D startup: real resident software service, no fake oil readings.

MicroPython executes this on boot. Physical modem/actuators remain electrically
gated, but their absence never prevents the local scheduler and diagnostics.
"""
from app.controller import DeviceController
from app.runtime import FirmwareRuntime, SystemClock
from config import default_config, default_hardware_config
from drivers.unbound import UnboundBoard

RUNTIME = None
PORTAL = None
CLOUD = None


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
    snapshot = RUNTIME.snapshot()
    snapshot["setupAp"] = ("ACTIVE" if PORTAL is not None and PORTAL.active
                           else "INACTIVE")
    if CLOUD is not None:
        snapshot.update(CLOUD.snapshot())
    return snapshot


def serve_forever(board=None, settings=None, hardware=None, clock=None,
                  output=print, max_ticks=None, setup_portal=None,
                  pairing_service=None, pair_input=None, cloud_service=None):
    """Run the Module D heartbeat and scheduler. Ctrl+C releases the REPL.

    max_ticks is for finite deterministic tests only; normal boot is resident.
    """
    global RUNTIME, PORTAL, CLOUD
    RUNTIME = None
    PORTAL = None
    CLOUD = None
    if settings is None:
        settings = default_config()
    startup = run(board=board, settings=settings, hardware=hardware)
    output("BlueGuard Buoy | " + startup["state"] + " | " + startup["reason"])
    if startup["state"] == "FAULT":
        return startup
    if clock is None:
        clock = SystemClock()
    RUNTIME = FirmwareRuntime(startup, settings, clock)
    output("Module D local services active | sensor=NOT_INSTALLED | modem=STARTING_IF_PROVISIONED")
    # AP is created only at real ESP32 MicroPython boot, never in desktop tests.
    # Unconfigured devices may open a short-lived password-protected setup AP.
    if setup_portal is None:
        import sys
        if sys.implementation.name == "micropython":
            try:
                from services.setup_portal import create_device_portal
                setup_portal = create_device_portal(clock)
            except Exception as exc:
                output("BlueGuard setup AP unavailable | " + type(exc).__name__)
    if setup_portal is not None:
        try:
            if setup_portal.start():
                PORTAL = setup_portal
                output("BlueGuard setup AP | SSID=" + PORTAL.ssid + " | IP=" + PORTAL.ip)
                # PROTOTYPE ONLY: physical serial is the current key handoff.
                # Production units require a protected printed manufacturing label.
                output("BlueGuard first-boot AP password (prototype serial): " + PORTAL.password)
                output("Open http://" + PORTAL.ip + "/ on a phone connected to this AP")
            else:
                output("BlueGuard local setup already saved | AP=OFF")
        except Exception as exc:
            output("BlueGuard setup AP failed | " + type(exc).__name__)
            try:
                setup_portal.close()
            except Exception:
                pass
    if cloud_service is None:
        import sys
        if sys.implementation.name == "micropython":
            try:
                from services.cellular_runtime import CellularService
                from services.provisioning import ProvisioningStore
                cloud_service = CellularService(clock, ProvisioningStore())
            except Exception as exc:
                output("BlueGuard cellular setup unavailable | " + type(exc).__name__)
    CLOUD = cloud_service
    cloud_status = None
    pairing_status = None
    if (pairing_service is None) != (pair_input is None):
        # Never activate a pairing service without a genuine physical input.
        raise ValueError("Pairing requires physical input and certified transport")
    loops = 0
    try:
        while True:
            if CLOUD is not None:
                try:
                    CLOUD.tick()
                    if CLOUD.status != cloud_status:
                        cloud_status = CLOUD.status
                        output("BlueGuard cellular | " + cloud_status)
                    # Console-only status; never expose the nonce or deviceKey.
                    current_pairing = CLOUD.snapshot().get("pairing")
                    if current_pairing and current_pairing != pairing_status:
                        pairing_status = current_pairing
                        output("BlueGuard pairing | " + pairing_status)
                except Exception as exc:
                    output("BlueGuard cellular fault | " + type(exc).__name__)
            if pairing_service is not None:
                # Explicitly attached verified GPIO/button and cloud transport.
                if pair_input.poll():
                    pairing_service.physically_pressed()
                    output("BlueGuard physical PAIR requested")
                pairing_service.tick()
            if PORTAL is not None:
                try:
                    PORTAL.tick()
                except Exception as exc:
                    output("BlueGuard setup AP stopped | " + type(exc).__name__)
                    PORTAL.close()
            event = RUNTIME.tick()
            if event:
                output(event)
            if max_ticks is not None:
                loops += 1
                if loops >= max_ticks:
                    return status()
            clock.sleep_ms(250)
    except KeyboardInterrupt:
        output("BlueGuard service stopped by operator; hardware outputs untouched")
        return status()
    finally:
        # Stop the local network listener when operator interrupts firmware.
        if PORTAL is not None:
            PORTAL.close()


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
