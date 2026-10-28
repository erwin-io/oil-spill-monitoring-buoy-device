"""BlueGuard firmware entry point. No physical hardware is activated in Stage 1."""
from app.controller import DeviceController
from config import default_config, default_hardware_config
from drivers.unbound import UnboundBoard


def run(board=None, settings=None, hardware=None):
    """Inject hardware settings without changing the API cloud config contract."""
    if board is None:
        board = UnboundBoard()
    if settings is None:
        settings = default_config()
    if hardware is None:
        hardware = default_hardware_config()
    return DeviceController(board, settings, hardware).start()


if __name__ == "__main__":
    print("BlueGuard Stage 1: " + run()["state"])
