"""BlueGuard firmware entry point. Hardware operation is disabled in Stage 1."""
from app.controller import DeviceController
from config import default_config
from drivers.unbound import UnboundBoard


def run(board=None, settings=None):
    """Wire dependencies explicitly. An absent real board stays UNCONFIGURED."""
    if board is None:
        board = UnboundBoard()
    if settings is None:
        settings = default_config()
    return DeviceController(board, settings).start()


if __name__ == "__main__":
    print("BlueGuard Stage 1: " + run()["state"])
