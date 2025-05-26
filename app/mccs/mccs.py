import enum
from dataclasses import dataclass, field


@enum.unique
class ColorPreset(enum.Enum):
    """Monitor color presets."""

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
    """Monitor power modes."""

    #: On.
    POWER_MODE_ON = 0x01
    #: Standby.
    POWER_MODE_STANDBY = 0x02
    #: Suspend.
    POWER_MODE_SUSPEND = 0x03
    #: Software power off.
    POWER_MODE_SOFT_OFF = 0x04
    #: Hardware power off.
    POWER_MODE_HARD_OFF = 0x05


@enum.unique
class InputSource(enum.Enum):
    """Monitor input sources."""

    INPUT_SOURCE_OFF = 0x00
    INPUT_SOURCE_ANALOG1 = 0x01
    INPUT_SOURCE_ANALOG2 = 0x02
    INPUT_SOURCE_DVI1 = 0x03
    INPUT_SOURCE_DVI2 = 0x04
    INPUT_SOURCE_COMPOSITE1 = 0x05
    INPUT_SOURCE_COMPOSITE2 = 0x06
    INPUT_SOURCE_SVIDEO1 = 0x07
    INPUT_SOURCE_SVIDEO2 = 0x08
    INPUT_SOURCE_TUNER1 = 0x09
    INPUT_SOURCE_TUNER2 = 0x0A
    INPUT_SOURCE_TUNER3 = 0x0B
    INPUT_SOURCE_CMPONENT1 = 0x0C
    INPUT_SOURCE_CMPONENT2 = 0x0D
    INPUT_SOURCE_CMPONENT3 = 0x0E
    INPUT_SOURCE_DP1 = 0x0F
    INPUT_SOURCE_DP2 = 0x10
    INPUT_SOURCE_HDMI1 = 0x11
    INPUT_SOURCE_HDMI2 = 0x12


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


class ReadWriteFlag(enum.Flag):
    """
    Read/Write flag for VCP codes.
    """

    NONE = 0
    READ = enum.auto()
    WRITE = enum.auto()


class VCPType(enum.Enum):
    """
    VCP type.  This is used to determine the type of VCP code.
    """

    CONTINUOUS = enum.auto()
    NONCONTINUOUS = enum.auto()


@dataclass(frozen=True)
class VCPDefinition:
    name: str
    code: int
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
    
    def __repr__(self):
        """Return the string representation of the VCP definition."""
        return f"0x{self.code:02X} ({self.name})"

    def __eq__(self, value):
        """Check if the value is equal to the VCP value."""
        if value is None:
            return False
        elif isinstance(value, str):
            return self.name == value
        elif isinstance(value, int):
            return self.code == value
        elif isinstance(value, VCPDefinition):
            return self.code == value.code
        elif isinstance(value, MCCSCommand):
            return self.code == value.value.code

        raise TypeError(f"Unsupported type for value: {type(value)}")


class MCCSCommand(enum.Enum):
    """
    VESA Monitor Control Command Set (MCCS) commands.
    These are the VCP codes used to control the monitor.
    """

    @staticmethod
    def from_code(value: int) -> "MCCSCommand":
        """
        Get the VCP code from the value.

        Args:
            value: The value of the VCP code.

        Returns:
            The VCP code.
        """
        for code in MCCSCommand:
            if code.value == value:
                return code
        raise ValueError(f"Invalid MCCS code value: {value}")

    @staticmethod
    def from_name(name: str) -> "MCCSCommand":
        """
        Get the VCP code from the name.

        Args:
            name: The name of the VCP code.

        Returns:
            The VCP code.
        """
        for code in MCCSCommand:
            if code.name == name:
                return code
        raise ValueError(f"Invalid MCCS code name: {name}")

    RESTORE_FACTOR_DEFAULTS = VCPDefinition(
        name="Restore factory defaults",
        code=0x04,
        rw=ReadWriteFlag.WRITE,
        type=VCPType.NONCONTINUOUS,
    )

    RESTORE_FACTORY_LUMINANCE_CONTRAST = VCPDefinition(
        name="Restore factory luminance / contrast values",
        code=0x05,
        rw=ReadWriteFlag.WRITE,
        type=VCPType.NONCONTINUOUS,
    )

    RESTORE_FACTORY_TV_DEFAULTS = VCPDefinition(
        name="Restore factory TV defaults",
        code=0x06,
        rw=ReadWriteFlag.WRITE,
        type=VCPType.NONCONTINUOUS,
    )

    DEGAUSS = VCPDefinition(
        name="Degauss",
        code=0x01,
        rw=ReadWriteFlag.WRITE,
        type=VCPType.NONCONTINUOUS,
    )

    AUTO_SETUP_ON_OFF = VCPDefinition(
        name="Auto setup on/off",
        code=0xA2,
        rw=ReadWriteFlag.WRITE,
        type=VCPType.NONCONTINUOUS,
    )

    CLOCK = VCPDefinition(
        name="Clock",
        code=0x0E,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    CLOCK_PHASE = VCPDefinition(
        name="Clock phase",
        code=0x3E,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    LUMINANCE = VCPDefinition(
        name="Luminance",
        code=0x10,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    BACKLIGHT_LEVEL_WHITE = VCPDefinition(
        name="Backlight level: White",
        code=0x6B,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    BACKLIGHT_LEVEL_RED = VCPDefinition(
        name="Backlight level: Red",
        code=0x6D,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    BACKLIGHT_LEVEL_GREEN = VCPDefinition(
        name="Backlight level: Green",
        code=0x6F,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    BACKLIGHT_LEVEL_BLUE = VCPDefinition(
        name="Backlight level: Blue",
        code=0x71,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )

    CONTRAST = VCPDefinition(
        name="Contrast",
        code=0x12,
        rw=ReadWriteFlag.READ | ReadWriteFlag.WRITE,
        type=VCPType.CONTINUOUS,
    )
