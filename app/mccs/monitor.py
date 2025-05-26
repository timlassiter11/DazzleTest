import logging
from dataclasses import dataclass
from venv import logger

import pyparsing

from .mccs import MCCSCommand, ReadWriteFlag, VCPDefinition, VCPType
from .vcp import BaseVCP, VCPError

logger = logging.getLogger(__name__)


@dataclass
class Capabilities:
    """
    Class to hold the capabilities of a monitor.
    """

    protocol: str | None
    type: str | None
    model: str | None
    mccs_version: str | None
    vcps: list[VCPDefinition]
    vcp_names: dict[int, str]


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

    def __init__(self, vcp: BaseVCP):
        self._vcp = vcp
        self._code_maximum: dict[int, int] = {}
        self._capabilities: Capabilities | None = None

    @property
    def vcp(self) -> BaseVCP:
        """
        The virtual control panel for the monitor.

        Returns:
            The virtual control panel for the monitor.
        """
        return self._vcp

    @property
    def capabilities(self) -> Capabilities:
        if self._capabilities is None:
            with self.vcp:
                cap_str = self.vcp.get_vcp_capabilities()
                self._capabilities = _parse_capabilities(cap_str)
        return self._capabilities

    @property
    def luminance(self) -> int:
        return self._get_vcp_value(MCCSCommand.LUMINANCE)

    @luminance.setter
    def luminance(self, value: int):
        self._set_vcp_value(MCCSCommand.LUMINANCE, value)

    @property
    def luminance_maximum(self) -> int:
        return self._get_vcp_maximum(MCCSCommand.LUMINANCE)

    @property
    def contrast(self) -> int:
        return self._get_vcp_value(MCCSCommand.CONTRAST)

    @contrast.setter
    def contrast(self, value: int):
        self._set_vcp_value(MCCSCommand.CONTRAST, value)

    @property
    def contrast_maximum(self) -> int:
        return self._get_vcp_maximum(MCCSCommand.CONTRAST)

    @property
    def backlight(self) -> int:
        return self._get_vcp_value(MCCSCommand.BACKLIGHT_LEVEL_WHITE)

    @backlight.setter
    def backlight(self, value: int):
        self._set_vcp_value(MCCSCommand.BACKLIGHT_LEVEL_WHITE, value)

    @property
    def backlight_maximum(self) -> int:
        return self._get_vcp_maximum(MCCSCommand.BACKLIGHT_LEVEL_WHITE)

    def supports_vcp(self, code: int | str | VCPDefinition | MCCSCommand) -> bool:
        """
        Checks if the monitor supports a given VCP code.

        Args:
            code: Feature code definition class or value.

        Returns:
            True if the monitor supports the VCP code, False otherwise.
        """
        if isinstance(code, MCCSCommand):
            code = code.value

        try:
            return code in self.capabilities.vcps
        except VCPError:
            return False

    def _get_vcp_maximum(self, definition: VCPDefinition | MCCSCommand) -> int:
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

        if isinstance(definition, MCCSCommand):
            definition = definition.value

        if not definition.readable:
            raise TypeError(f"code is not readable: {definition.name}")

        if definition.code in self._code_maximum:
            return self._code_maximum[definition.code]
        else:
            with self.vcp:
                _, maximum = self.vcp.get_vcp_feature(definition.code)

            self._code_maximum[definition.code] = maximum
            return maximum

    def _set_vcp_value(self, definition: VCPDefinition | MCCSCommand, value: int):
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

        if isinstance(definition, MCCSCommand):
            definition = definition.value

        if not definition.writeable:
            raise TypeError(f"cannot write read-only code: {definition.name}")
        elif definition.type == VCPType.CONTINUOUS:
            maximum = self._get_vcp_maximum(definition)
            if value > maximum:
                raise ValueError(f"value of {value} exceeds code maximum of {maximum}")

        with self.vcp:
            self.vcp.set_vcp_feature(definition.code, value)

    def _get_vcp_value(self, definition: VCPDefinition | MCCSCommand) -> int:
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

        if isinstance(definition, MCCSCommand):
            definition = definition.value

        if not definition.readable:
            raise TypeError(f"cannot read write-only code: {definition.name}")

        with self.vcp:
            current, maximum = self.vcp.get_vcp_feature(definition.code)
            if definition.type == VCPType.CONTINUOUS:
                self._code_maximum[definition.code] = maximum

        return current


def _parse_capabilities(caps_str: str) -> Capabilities:
    """
    Converts the capabilities string into a nice dict
    """

    protocol: str | None = None
    type: str | None = None
    model = None
    mccs_version = None
    cmds: list[int] = []
    vcps: list[VCPDefinition] = []
    vcp_names: dict[int, str] = {}

    cap_pattern = pyparsing.Word(pyparsing.alphanums + "_") + pyparsing.nested_expr()
    for result, start, end in cap_pattern.scan_string(caps_str):
        key = result[0]
        value = result[1][0]

        if key == "prot":
            protocol = value
        elif key == "type":
            type = value
        elif key == "model":
            model = value
        elif key == "mccs_ver":
            mccs_version = value
        elif key == "cmds":
            for cmd in result[1]:
                cmds.append(int(cmd, 16))
        elif key == "vcp":
            last_definition = None
            for vcp in result[1]:
                if isinstance(vcp, pyparsing.ParseResults) and last_definition:
                    last_definition.values.extend(vcp.as_list())
                else:
                    code = int(vcp, 16)
                    try:
                        last_definition = MCCSCommand.from_code(code).value
                    except ValueError:
                        last_definition = VCPDefinition(
                            name=f"VCP {vcp} (unknown)",
                            code=code,
                            rw=ReadWriteFlag.NONE,
                            type=VCPType.NONCONTINUOUS,
                        )
                    vcps.append(last_definition)
        elif key == "vcpname":
            # TODO: Handle vcpname parsing
            pass

    if protocol is None:
        logger.warning("prot missing from capabilities string")
    if type is None:
        logger.warning("type missing from capabilities string")
    if model is None:
        logger.warning("model missing from capabilities string")
    if mccs_version is None:
        logger.warning("mccs_ver missing from capabilities string")
    if vcps is None:
        logger.warning("vcps missing from capabilities string")

    return Capabilities(
        protocol=protocol or "",
        type=type or "",
        model=model or "",
        mccs_version=mccs_version or "",
        vcps=vcps or [],
        vcp_names={},
    )
