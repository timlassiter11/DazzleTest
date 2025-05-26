import sys
from dataclasses import dataclass, field
from enum import Enum, Flag, auto


class VCPError(Exception):
    """Base class for all VCP related errors."""

    pass


class VCPIOError(VCPError):
    """Raised on VCP IO errors."""

    pass


class VCPPermissionError(VCPError):
    """Raised on VCP permission errors."""

    pass


from .basevcp import BaseVCP

if sys.platform == "win32":
    from .windowsvcp import WindowsVCP as VCP
elif sys.platform.startswith("linux"):
    from .vcp_linux import LinuxVCP as VCP
