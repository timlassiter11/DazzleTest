"""
This package provides a Python interface for controlling monitor settings using MCCS (Monitor Control Command Set).

It includes functionality for:
    - Discovering connected monitors.
    - Getting and setting VCP (Virtual Control Panel) codes.
    - High-level abstractions for common monitor settings.
"""
from .mccs import Monitor, get_monitors
from .vcp import VCP, VCPDefinition, VCPError, VCPIOError, VCPPermissionError
