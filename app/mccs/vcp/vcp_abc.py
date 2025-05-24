"""
This module defines the abstract base class (ABC) for VCP (Virtual Control Panel)
implementations and common VCP-related exceptions.

All platform-specific VCP implementations should inherit from `BaseVCP`
and implement its abstract methods.
"""
import abc
from types import TracebackType
from typing import Type


class VCPError(Exception):
    """Base class for all VCP (Virtual Control Panel) related errors."""

    pass


class VCPIOError(VCPError):
    """
    Raised on VCP (Virtual Control Panel) Input/Output errors.

    This typically indicates a problem communicating with the monitor.
    """

    pass


class VCPPermissionError(VCPError):
    """
    Raised on VCP (Virtual Control Panel) permission errors.

    This may indicate that the user does not have the necessary permissions
    to control monitor settings.
    """

    pass


class BaseVCP(abc.ABC):
    """
    Abstract Base Class for VCP (Virtual Control Panel) implementations.

    This class defines the interface that all platform-specific VCP classes
    must implement. It also provides a context manager interface.
    """

    @abc.abstractmethod
    def __enter__(self):
        """
        Enters the runtime context related to this object.

        This method is called when entering a `with` statement.
        It should handle any necessary setup for the VCP interaction.
        """
        pass

    @abc.abstractmethod
    def __exit__(
        self,
        exception_type: Type[BaseException] | None,
        exception_value: BaseException | None,
        exception_traceback: TracebackType | None,
    ) -> bool | None:
        """
        Exits the runtime context related to this object.

        This method is called when exiting a `with` statement.
        It should handle any necessary cleanup, such as releasing resources.
        The arguments describe the exception that caused the context to be exited.
        If no exception occurred, all three arguments are None.
        Returning True from this method will suppress any exception raised in the `with` block.
        """
        pass

    @abc.abstractmethod
    def set_vcp_feature(self, code: int, value: int):
        """
        Sets the value of a feature on the virtual control panel.

        Args:
            code: Feature code.
            value: Feature value.

        Raises:
            VCPError: Failed to set VCP feature.
        """
        pass

    @abc.abstractmethod
    def get_vcp_feature(self, code: int) -> tuple[int, int]:
        """
        Gets the value of a feature from the virtual control panel.

        Args:
            code: Feature code.

        Returns:
            Current feature value, maximum feature value.

        Raises:
            VCPError: Failed to get VCP feature.
        """
        pass

    @abc.abstractmethod
    def get_vcp_capabilities(self) -> str:
        """
        Gets the VCP capabilities string from the monitor.

        This string contains information about the monitor's supported features.

        Returns:
            The VCP capabilities string.

        Raises:
            VCPError: Failed to get VCP capabilities.
        """
        pass

    @staticmethod
    @abc.abstractmethod
    def get_vcps() -> list["BaseVCP"]:
        """
        Gets a list of all available VCPs (monitors).

        This is a static method, as it's used to discover monitors
        before a specific VCP instance is created.

        Returns:
            A list of VCP instances, one for each detected monitor.

        Raises:
            VCPError: Failed to list VCPs.
        """
        pass
