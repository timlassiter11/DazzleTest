from dataclasses import dataclass, field
from enum import Enum, Flag, auto


class VCPType(Enum):
    """
    VCP type.  This is used to determine the type of VCP code.
    """

    CONTINUOUS = auto()
    NONCONTINUOUS = auto()


class ReadWriteFlag(Flag):
    """
    Read/Write flag for VCP codes.
    """
    NONE = 0
    READ = auto()
    WRITE = auto()


@dataclass(frozen=True)
class VCPDefinition:
    name: str
    value: int
    rw: ReadWriteFlag
    type: VCPType
    values: list[int] = field(default_factory=list)

    @property
    def readable(self) -> bool:
        """Returns true if the code can be read."""
        return ReadWriteFlag.READ in self.rw

    @property
    def writeable(self) -> bool:
        """Returns true if the code can be written."""
        return ReadWriteFlag.WRITE in self.rw
    
    def __eq__(self, value):
        """Check if the value is equal to the VCP value."""
        if isinstance(value, int):
            return self.value == value
        elif isinstance(value, str):
            return self.name == value
        elif isinstance(value, VCPDefinition):
            return self.value == value.value
        return False
