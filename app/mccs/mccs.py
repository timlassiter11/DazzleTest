"""
This module defines the high-level interface for interacting with monitors.

It includes:
    - `Monitor` class: Represents a physical monitor and provides methods to control its settings.
    - `VCPDefinitions` enum: Defines known VCP codes.
    - `ColorPreset`, `PowerMode`, `InputSource` enums: Define common monitor settings.
    - `Capabilities` dataclass: Holds monitor capability information.
    - `get_monitors()`: Function to discover and initialize connected monitors.
    - `_parse_capabilities()`: Helper function to parse the capabilities string.
"""
import enum
import logging
import re
from dataclasses import dataclass
from types import TracebackType
from typing import Type

import pyparsing

from app.mccs.vcp_codes import ReadWriteFlag, VCPDefinition, VCPType

from . import vcp
from .vcp import VCP

logger = logging.getLogger(__file__)


class VCPDefinitions(enum.Enum):
    """
    Enumeration of known VCP (Virtual Control Panel) codes.

    Each member is a `VCPDefinition` object containing information about the code,
    such as its name, value, read/write status, and type.
    """

    @staticmethod
    def from_value(value: int) -> VCPDefinition:
        """
        Get the VCP definition from its hexadecimal value.

        Args:
            value: The value of the VCP code.

        Returns:
            The VCP code.
        """
        for code in VCPDefinitions:
            if code.value == value:
                return code.value
        raise ValueError(f"Invalid VCP code value: {value}")

    @staticmethod
    def from_name(name: str) -> VCPDefinition:
        """
        Get the VCP definition from its name.

        Args:
            name: The name of the VCP code.

        Returns:
            The VCP code.
        """
        for code in VCPDefinitions:
            if code.name == name:
                return code.value
        raise ValueError(f"Invalid VCP code name: {name}")

    RESTORE_FACTOR_DEFAULTS = VCPDefinition(
        name="Restore factory defaults",
        value=0x04,
        rw=ReadWriteFlag.WRITE,
        type=VCPType.NONCONTINUOUS,
    )

    RESTORE_FACTORY_LUMINANCE_CONTRAST = VCPDefinition(
        name="Restore factory luminance / contrast values",
        value=0x05,
        rw=ReadWriteFlag.WRITE,
        type=VCPType.NONCONTINUOUS,
    )

    RESTORE_FACTORY_TV_DEFAULTS = VCPDefinition(
        name="Restore factory TV defaults",
        value=0x06,
        rw=ReadWriteFlag.WRITE,
        type=VCPType.NONCONTINUOUS,
    )

    DEGAUSS = VCPDefinition(
        name="Degauss",
        value=0x01,
        rw=ReadWriteFlag.WRITE,
        type=VCPType.NONCONTINUOUS,
    )

    AUTO_SETUP_ON_OFF = VCPDefinition(
        name="Auto setup on/off",
        value=0xA2,
        rw=ReadWriteFlag.WRITE,
        type=VCPType.NONCONTINUOUS,
    )

    CLOCK = VCPDefinition(
        name="Clock",
        value=0x0E,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    CLOCK_PHASE = VCPDefinition(
        name="Clock phase",
        value=0x3E,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    LUMINANCE = VCPDefinition(
        name="Luminance",
        value=0x10,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    BACKLIGHT_LEVEL_WHITE = VCPDefinition(
        name="Backlight level: White",
        value=0x6B,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    BACKLIGHT_LEVEL_RED = VCPDefinition(
        name="Backlight level: Red",
        value=0x6D,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    BACKLIGHT_LEVEL_GREEN = VCPDefinition(
        name="Backlight level: Green",
        value=0x6F,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    BACKLIGHT_LEVEL_BLUE = VCPDefinition(
        name="Backlight level: Blue",
        value=0x71,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    CONTRAST = VCPDefinition(
        name="contrast",
        value=0x12,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )


@enum.unique
class ColorPreset(enum.Enum):
    """
    Monitor color presets.

    These values correspond to the VCP code 0x14 (Select color preset).
    """

    COLOR_TEMP_4000K = 0x03
    COLOR_TEMP_5000K = 0x04
    COLOR_TEMP_6500K = 0x05
    COLOR_TEMP_7500K = 0x06
    COLOR_TEMP_8200K = 0x07
    COLOR_TEMP_9300K = 0x08
    COLOR_TEMP_10000K = 0x09
    COLOR_TEMP_11500K = 0x0A
    COLOR_TEMP_USER1 = 0x0B
    COLOR_TEMP_USER2 = 0x0C
    COLOR_TEMP_USER3 = 0x0D


@enum.unique
class PowerMode(enum.Enum):
    """
    Monitor power modes.

    These values correspond to the VCP code 0xD6 (Power mode).
    """

    #: On.
    on = 0x01
    #: Standby.
    standby = 0x02
    #: Suspend.
    suspend = 0x03
    #: Software power off.
    off_soft = 0x04
    #: Hardware power off.
    off_hard = 0x05


@enum.unique
class InputSource(enum.Enum):
    """
    Monitor input sources.

    These values correspond to the VCP code 0x60 (Input Source).
    """

    OFF = 0x00
    ANALOG1 = 0x01
    ANALOG2 = 0x02
    DVI1 = 0x03
    DVI2 = 0x04
    COMPOSITE1 = 0x05
    COMPOSITE2 = 0x06
    SVIDEO1 = 0x07
    SVIDEO2 = 0x08
    TUNER1 = 0x09
    TUNER2 = 0x0A
    TUNER3 = 0x0B
    CMPONENT1 = 0x0C
    CMPONENT2 = 0x0D
    CMPONENT3 = 0x0E
    DP1 = 0x0F
    DP2 = 0x10
    HDMI1 = 0x11
    HDMI2 = 0x12


class InputSourceValueError(ValueError):
    """
    Raised upon an invalid (out of spec) input source value.

    https://github.com/newAM/monitorcontrol/issues/93

    Attributes:
        value (int): The value of the input source that was invalid.
    """

    def __init__(self, message: str, value: int):
        super().__init__(message)
        self.value = value


@dataclass
class Capabilities:
    """
    Class to hold the capabilities of a monitor.

    This dataclass stores information about a monitor's protocol, type, model,
    MCCS version, supported VCP codes, and VCP code names.
    """

    protocol: str
    type: str
    model: str
    mccs_version: str
    vcps: list[VCPDefinition]
    vcp_names: dict[int, str]

    def __contains__(self, item: int | str | VCPDefinition | VCPDefinitions) -> bool:
        """Checks if a VCP code is supported by the monitor."""
        if isinstance(item, VCPDefinitions):
            item = item.value  # Get the VCPDefinition object from the enum member

        return item in self.vcps


class Monitor:
    """
    A physical monitor attached to a Virtual Control Panel (VCP).

    Typically, you do not use this class directly and instead use
    :py:meth:`get_monitors` to get a list of initialized monitors.

    All class methods must be called from within a context manager unless
    otherwise stated.

    Args:
        vcp: Virtual control panel for the monitor.
    """

    def __init__(self, vcp: vcp.BaseVCP):
        self.vcp = vcp
        self.code_maximum: dict[int, int] = {}  # Cache for VCP code maximum values
        self._in_ctx = False  # Flag to ensure methods are called within a context manager
        self._capabilities: Capabilities | None = None  # Cache for monitor capabilities

    def __enter__(self):
        """Enters the runtime context related to this object."""
        self.vcp.__enter__()
        self._in_ctx = True
        return self

    def __exit__(
        self,
        exception_type: Type[BaseException] | None,
        exception_value: BaseException | None,
        exception_traceback: TracebackType | None,
    ) -> bool | None:
        """Exits the runtime context related to this object."""
        try:
            # Delegate to the VCP's __exit__ method
            return self.vcp.__exit__(
                exception_type, exception_value, exception_traceback
            )
        finally:
            self._in_ctx = False  # Reset context flag

    def _get_vcp_maximum(self, code: VCPDefinition | VCPDefinitions) -> int:
        """
        Gets the maximum values for a given code, and caches in the
        class dictionary if not already found.

        Args:
            code: Feature code definition class.

        Returns:
            Maximum value for the given code.

        Raises:
            TypeError: Code is write only.
        """

        if isinstance(code, VCPDefinitions):
            code = code.value # Get the VCPDefinition object from the enum member

        assert self._in_ctx, "This function must be run within the context manager"
        if not code.readable:
            raise TypeError(f"code is not readable: {code.name}")

        # Check if the maximum value is already cached
        if code.value in self.code_maximum:
            return self.code_maximum[code.value]
        else:
            # Get the maximum value from the VCP and cache it
            _, maximum = self.vcp.get_vcp_feature(code.value)
            self.code_maximum[code.value] = maximum
            return maximum

    def _set_vcp_value(self, code: VCPDefinition | VCPDefinitions, value: int):
        """
        Sets the value of a feature on the virtual control panel.

        Args:
            code: Feature code.
            value: Feature value.

        Raises:
            TypeError: Code is ready only.
            ValueError: Value is greater than the maximum allowable.
            VCPError: Failed to get VCP feature.
        """

        if isinstance(code, VCPDefinitions):
            code = code.value # Get the VCPDefinition object from the enum member

        assert self._in_ctx, "This function must be run within the context manager"
        if not code.writeable:
            raise TypeError(f"cannot write read-only code: {code.name}")
        # For continuous VCP codes, ensure the value does not exceed the maximum
        elif code.type == VCPType.CONTINUOUS:
            maximum = self._get_vcp_maximum(code)
            if value > maximum:
                raise ValueError(f"value of {value} exceeds code maximum of {maximum}")

        self.vcp.set_vcp_feature(code.value, value)

    def _get_vcp_value(self, code: VCPDefinition | VCPDefinitions) -> int:
        """
        Gets the value of a feature from the virtual control panel.

        Args:
            code: Feature code.

        Returns:
            Current feature value.

        Raises:
            TypeError: Code is write only.
            VCPError: Failed to get VCP feature.
        """

        if isinstance(code, VCPDefinitions):
            code = code.value # Get the VCPDefinition object from the enum member

        assert self._in_ctx, "This function must be run within the context manager"
        if not code.readable:
            raise TypeError(f"cannot read write-only code: {code.name}")

        # Get the current value from the VCP
        current, _ = self.vcp.get_vcp_feature(code.value) # We don't need the maximum here
        return current

    def get_vcp_capabilities(self) -> Capabilities:
        """
        Gets the capabilities of the monitor

        Returns:
            Dictionary of capabilities in the following example format::

                {
                    "prot": "monitor",
                    "type": "LCD",
                    "cmds": {
                            1: [],
                            2: [],
                            96: [15, 17, 18],
                    },
                    "inputs": [
                        InputSource.DP1,
                        InputSource.HDMI1,
                        InputSource.HDMI2
                        # this may return integers for out-of-spec values,
                        # such as USB Type-C monitors
                    ],
                }
        """
        assert self._in_ctx, "This function must be run within the context manager"

        cap_str = self.vcp.get_vcp_capabilities()
        # Parse the raw capabilities string
        res = _parse_capabilities(cap_str)
        return res

    @property
    def capabilities(self) -> Capabilities:
        """Gets the monitor's capabilities, caching the result."""
        if self._capabilities is None:
            self._capabilities = self.get_vcp_capabilities()
        return self._capabilities


    @property
    def luminance(self) -> int:
        """Current luminance value of the monitor."""
        return self._get_vcp_value(VCPDefinitions.LUMINANCE)

    @luminance.setter
    def luminance(self, value: int):
        """Sets the luminance value of the monitor."""
        self._set_vcp_value(VCPDefinitions.LUMINANCE, value)

    @property
    def luminance_maximum(self) -> int:
        """Maximum luminance value of the monitor."""
        return self._get_vcp_maximum(VCPDefinitions.LUMINANCE)

    @property
    def contrast(self) -> int:
        """Current contrast value of the monitor."""
        return self._get_vcp_value(VCPDefinitions.CONTRAST)

    @contrast.setter
    def contrast(self, value: int):
        """Sets the contrast value of the monitor."""
        self._set_vcp_value(VCPDefinitions.CONTRAST, value)

    @property
    def contrast_maximum(self) -> int:
        """Maximum contrast value of the monitor."""
        return self._get_vcp_maximum(VCPDefinitions.CONTRAST)

    @property
    def backlight(self) -> int:
        """Current backlight level (white) of the monitor."""
        return self._get_vcp_value(VCPDefinitions.BACKLIGHT_LEVEL_WHITE)

    @backlight.setter
    def backlight(self, value: int):
        """Sets the backlight level (white) of the monitor."""
        self._set_vcp_value(VCPDefinitions.BACKLIGHT_LEVEL_WHITE, value)

    @property
    def backlight_maximum(self) -> int:
        """Maximum backlight level (white) of the monitor."""
        return self._get_vcp_maximum(VCPDefinitions.BACKLIGHT_LEVEL_WHITE)


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


def _parse_capabilities(caps_str: str) -> Capabilities:
    """
    Parses the VCP capabilities string returned by the monitor.

    The capabilities string is a DDC/CI (Display Data Channel Command Interface)
    string that describes the monitor's features. This function parses this
    string and extracts relevant information into a `Capabilities` object.

    Args:
        caps_str: The raw capabilities string from the monitor.

    Returns:
        A `Capabilities` object containing the parsed information.
    """

    protocol: str | None = None
    type: str | None = None
    model = None
    mccs_version = None
    cmds: list[int] = []
    vcps: list[VCPDefinition] = []
    vcp_names: dict[int, str] = {}

    # Define a pyparsing pattern to match key-value pairs in the capabilities string.
    # Example: "prot(monitor)" or "vcp(02 04 05 06 08 10 12 ...)"
    cap_pattern = pyparsing.Word(pyparsing.alphanums + "_") + pyparsing.nested_expr()
    # Iterate over matches found in the capabilities string
    for result, start, end in cap_pattern.scan_string(caps_str):
        key = result[0]
        value = result[1][0] # First element of the nested expression

        # Populate capabilities based on the key
        if key == "prot":
            protocol = value
        elif key == "type":
            type = value
        elif key == "model":
            model = value
        elif key == "mccs_ver":
            mccs_version = value
        elif key == "cmds":
            # Supported MCCS commands (not directly used yet)
            for cmd in result[1]:
                cmds.append(int(cmd, 16))
        elif key == "vcp":
            # Supported VCP codes
            last_definition = None
            for vcp_item in result[1]:
                if isinstance(vcp_item, pyparsing.ParseResults) and last_definition:
                    # This handles cases where VCP code values are nested
                    # e.g. vcp((01 02)(03 04))
                    last_definition.values.extend(vcp_item.as_list())
                else:
                    code = int(vcp_item, 16)
                    try:
                        # Try to find a known VCP definition
                        last_definition = VCPDefinitions.from_value(code)
                    except ValueError:
                        # If not found, create a generic VCPDefinition
                        last_definition = VCPDefinition(
                            name=f"VCP {vcp_item} (unknown)",
                            value=code,
                            rw=ReadWriteFlag.NONE, # Assume no read/write if unknown
                            type=VCPType.NONCONTINUOUS, # Assume non-continuous if unknown
                        )
                    vcps.append(last_definition)
        elif key == "vcpname":
            # VCP code names (not directly used yet, could be used to populate vcp_names)
            pass # TODO: Potentially parse vcpname if needed in the future

    # Log warnings if essential capability fields are missing
    if protocol is None:
        logger.warning("prot missing from capabilities string")
    if type is None:
        logger.warning("type missing from capabilities string")
    if model is None:
        logger.warning("model missing from capabilities string")
    if mccs_version is None:
        logger.warning("mccs_ver missing from capabilities string")
    if not vcps: # Check if the list is empty
        logger.warning("vcps missing from capabilities string")

    return Capabilities(
        protocol=protocol or "", # Use empty string as default if None
        type=type or "",
        model=model or "",
        mccs_version=mccs_version or "",
        vcps=vcps or [], # Use empty list as default if None
        vcp_names={}, # Initialize as empty, to be populated if vcpname is parsed
    )
