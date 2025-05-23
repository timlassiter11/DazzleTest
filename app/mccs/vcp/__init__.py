import sys
from ..vcp_codes import VCPDefinition  # noqa: F401
from .vcp_abc import (  # noqa: F401
    BaseVCP,
    VCPError,
    VCPIOError,
    VCPPermissionError,
)

if sys.platform == "win32":
    from .vcp_windows import WindowsVCP as VCP
elif sys.platform.startswith("linux"):
    from .vcp_linux import LinuxVCP as VCP