"""
This module defines the data structures and enumerations used to represent
VCP (Virtual Control Panel) codes and their properties.

It includes:
    - `VCPType`: Enum for VCP code types (Continuous or NonContinuous).
    - `ReadWriteFlag`: Enum for VCP code read/write permissions.
    - `VCPDefinition`: Dataclass to store information about a specific VCP code.
"""
from dataclasses import dataclass, field
from enum import Enum, Flag, auto


class VCPType(Enum):
    """
    Enumeration for VCP (Virtual Control Panel) code types.

    VCP codes can be either Continuous (their value can be set within a range)
    or NonContinuous (their value must be one of a predefined set).
    """

    CONTINUOUS = auto()  # Represents a continuous VCP code
    NONCONTINUOUS = auto()  # Represents a non-continuous VCP code


class ReadWriteFlag(Flag):
    """
    Enumeration for VCP (Virtual Control Panel) code read/write permissions.

    Indicates whether a VCP code is readable, writable, both, or neither.
    """
    NONE = 0  # No read or write permission
    READ = auto()  # Read permission
    WRITE = auto()  # Write permission


@dataclass(frozen=True)
class VCPDefinition:
    """
    Dataclass representing a VCP (Virtual Control Panel) code definition.

    This class stores all relevant information about a VCP code, including its
    name, hexadecimal value, read/write permissions, type (continuous or
    non-continuous), and a list of possible values for non-continuous codes.

    Attributes:
        name: Human-readable name of the VCP code.
        value: Hexadecimal value of the VCP code.
        rw: ReadWriteFlag indicating the read/write permissions.
        type: VCPType indicating if the code is continuous or non-continuous.
        values: Optional list of allowed integer values for non-continuous codes.
    """
    name: str
    value: int
    rw: ReadWriteFlag
    type: VCPType
    values: list[int] = field(default_factory=list)  # Default to an empty list for continuous or unpopulated NC codes

    @property
    def readable(self) -> bool:
        """Returns true if the code can be read."""
        return ReadWriteFlag.READ in self.rw

    @property
    def writeable(self) -> bool:
        """Returns true if the code can be written."""
        return ReadWriteFlag.WRITE in self.rw
    
    def __eq__(self, other_value):
        """
        Custom equality check for VCPDefinition.

        Allows comparison with an integer (compares with VCP code value),
        a string (compares with VCP code name), or another VCPDefinition instance
        (compares VCP code values).

        Args:
            other_value: The value to compare against.

        Returns:
            True if the values are considered equal, False otherwise.
        """
        if isinstance(other_value, int):
            return self.value == other_value
        elif isinstance(other_value, str):
            return self.name == other_value
        elif isinstance(other_value, VCPDefinition):
            return self.value == other_value.value
        return False  # Not comparable with other types
