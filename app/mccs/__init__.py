from .monitor import Monitor, Capabilities
from .mccs import MCCSCommand, ColorPreset, PowerMode, InputSource
from .vcp import VCP, VCPError, VCPIOError, VCPPermissionError


def get_monitors() -> list[Monitor]:
    """
    Creates a list of all monitors.

    Returns:
        List of monitors in a closed state.

    Raises:
        VCPError: Failed to list VCPs.

    Example:
        Setting the power mode of all monitors to standby::

            for monitor in get_monitors():
                with monitor:
                    monitor.set_power_mode("standby")

        Setting all monitors to the maximum brightness using the
        context manager::

            for monitor in get_monitors():
                with monitor:
                    monitor.set_luminance(100)
    """
    return [Monitor(v) for v in VCP.get_vcps()]
