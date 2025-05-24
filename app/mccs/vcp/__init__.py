"""
This package provides the VCP (Virtual Control Panel) implementations.

It dynamically imports the appropriate VCP implementation based on the operating system.
It also re-exports key classes and exceptions from the .vcp_abc module.
"""
import sys
# Re-export VCPDefinition for convenience
from ..vcp_codes import VCPDefinition  # noqa: F401
# Re-export abstract base class and VCP-related exceptions
from .vcp_abc import (  # noqa: F401
    BaseVCP,
    VCPError,
    VCPIOError,
    VCPPermissionError,
)

# Platform-specific VCP implementation import
if sys.platform == "win32":  # Windows
    from .vcp_windows import WindowsVCP as VCP
elif sys.platform.startswith("linux"):  # Linux
    from .vcp_linux import LinuxVCP as VCP
# TODO: Add support for other platforms like macOS if necessary