"""
This module provides the Windows-specific implementation of the VCP (Virtual Control Panel) interface.

It uses the Windows API (dxva2.dll and user32.dll) via ctypes to communicate with monitors
and control their settings using DDC/CI (Display Data Channel Command Interface).
"""
from .vcp_abc import BaseVCP, VCPError
from types import TracebackType
from typing import Type, Literal
import ctypes
import logging
import sys

# hide the Windows code from Linux CI coverage
if sys.platform == "win32":
    from ctypes.wintypes import (
        DWORD,
        RECT,
        BOOL,
        HMONITOR,
        HDC,
        LPARAM,
        HANDLE,
        BYTE,
        WCHAR,
    )

    # structure type for a physical monitor
    class PhysicalMonitor(ctypes.Structure):
        """
        Represents a physical monitor connected to the system.

        This structure is used by Windows API functions to provide information
        about physical monitors.

        Fields:
            handle (HANDLE): A handle to the physical monitor.
            description (WCHAR[128]): A string describing the physical monitor.
        """
        _fields_ = [
            ("handle", HANDLE),  # Physical monitor handle
            ("description", WCHAR * 128)  # Monitor description string
        ]

    class WindowsVCP(BaseVCP):
        """
        Windows API access to a monitor's virtual control panel (VCP).

        This class implements the `BaseVCP` interface for Windows systems.
        It uses functions from `dxva2.dll` (Windows Display Driver Model)
        to interact with monitors that support DDC/CI.

        References:
            - Microsoft documentation on Monitor Configuration:
              https://docs.microsoft.com/en-us/windows/win32/monitor/monitor-configuration
            - Relevant StackOverflow discussion: https://stackoverflow.com/questions/16588133/
        """

        def __init__(self, hmonitor: HMONITOR):
            """
            Args:
                hmonitor: logical monitor handle
            """
            """
            Initializes the WindowsVCP instance.

            Args:
                hmonitor: A handle to a logical monitor (HMONITOR).
                          This handle is typically obtained from EnumDisplayMonitors.
            """
            self.logger = logging.getLogger(__name__)
            self.hmonitor = hmonitor  # Handle to the logical monitor
            self.handle: HANDLE | None = None  # Will store the physical monitor handle
            self.description: str | None = None # Description of the physical monitor

        def __enter__(self):
            """
            Acquires a handle to the physical monitor associated with the logical monitor.

            This method uses `GetNumberOfPhysicalMonitorsFromHMONITOR` and
            `GetPhysicalMonitorsFromHMONITOR` to get a physical monitor handle.

            Raises:
                VCPError: If any Windows API call fails or no physical monitor is found.

            Returns:
                self: The `WindowsVCP` instance with an active physical monitor handle.
            """
            num_physical = DWORD()
            self.logger.debug(f"GetNumberOfPhysicalMonitorsFromHMONITOR for HMONITOR {self.hmonitor}")
            try:
                # Get the number of physical monitors associated with this logical monitor handle
                if not ctypes.windll.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(
                    self.hmonitor, ctypes.byref(num_physical)
                ):
                    error_msg = f"GetNumberOfPhysicalMonitorsFromHMONITOR failed: {ctypes.FormatError()}"
                    self.logger.error(error_msg)
                    raise VCPError(error_msg)
            except OSError as e:
                raise VCPError("GetNumberOfPhysicalMonitorsFromHMONITOR call failed due to OSError") from e

            self.logger.debug(f"Found {num_physical.value} physical monitor(s).")
            if num_physical.value == 0:
                raise VCPError("No physical monitor found for the given HMONITOR.")
            # This implementation currently supports only one physical monitor per HMONITOR.
            # Multiple physical monitors for a single logical monitor handle is rare but possible
            # in some virtualized or specialized display setups.
            elif num_physical.value > 1:
                # TODO: Potentially extend to support multiple physical monitors if a use case arises.
                # This would require a mechanism to select or iterate over them.
                self.logger.warning(
                    f"Found {num_physical.value} physical monitors for HMONITOR {self.hmonitor}. "
                    "Using the first one."
                )
                # For now, we proceed with the first monitor, but this behavior might need refinement.

            # Create an array to hold the PhysicalMonitor structures
            physical_monitors_array = (PhysicalMonitor * num_physical.value)()
            self.logger.debug(f"GetPhysicalMonitorsFromHMONITOR for HMONITOR {self.hmonitor}")
            try:
                # Get the physical monitor(s)
                if not ctypes.windll.dxva2.GetPhysicalMonitorsFromHMONITOR(
                    self.hmonitor, num_physical.value, physical_monitors_array
                ):
                    error_msg = f"GetPhysicalMonitorsFromHMONITOR failed: {ctypes.FormatError()}"
                    self.logger.error(error_msg)
                    raise VCPError(error_msg)
            except OSError as e:
                raise VCPError("GetPhysicalMonitorsFromHMONITOR call failed due to OSError") from e

            # Store the handle and description of the first physical monitor
            self.handle = physical_monitors_array[0].handle
            self.description = physical_monitors_array[0].description
            self.logger.info(f"Acquired physical monitor: {self.description} (Handle: {self.handle})")
            return self

        def __exit__(
            self,
            exception_type: Type[BaseException] | None,
            exception_value: BaseException | None,
            exception_traceback: TracebackType | None,
        ) -> Literal[False]:
            """
            Releases the handle to the physical monitor.

            This method calls `DestroyPhysicalMonitor` to free the monitor handle.

            Returns:
                False, to indicate that any exceptions should not be suppressed.
            """
            if self.handle:
                self.logger.debug(f"DestroyPhysicalMonitor for handle {self.handle}")
                try:
                    if not ctypes.windll.dxva2.DestroyPhysicalMonitor(self.handle):
                        error_msg = f"DestroyPhysicalMonitor failed: {ctypes.FormatError()}"
                        self.logger.error(error_msg)
                        # Non-critical if an exception is already being handled,
                        # but log it as it might indicate a resource leak.
                        if exception_type is None: # Only raise if not already exiting due to an error
                            raise VCPError(error_msg)
                except OSError as e:
                    # Similar to above, log but only raise if not already handling an exception.
                    self.logger.error(f"DestroyPhysicalMonitor call failed due to OSError: {e}")
                    if exception_type is None:
                        raise VCPError("DestroyPhysicalMonitor call failed due to OSError") from e
                finally:
                    self.handle = None # Ensure handle is marked as released
            return False # Do not suppress exceptions from the 'with' block

        def set_vcp_feature(self, code: int, value: int):
            """
            Sets the value of a feature on the virtual control panel.

            Args:
                code: Feature code.
                value: Feature value.

            Raises:
                VCPError: Failed to set VCP feature.
            """
            """
            Sets the value of a VCP feature on the physical monitor.

            Args:
                code: The VCP code of the feature to set.
                value: The value to set for the feature.

            Raises:
                VCPError: If the `SetVCPFeature` Windows API call fails.
            """
            if self.handle is None:
                raise VCPError("Physical monitor handle is not initialized. Call __enter__ first.")

            self.logger.debug(f"SetVCPFeature(Handle={self.handle}, Code={code}, Value={value})")
            try:
                # Call the Windows API function SetVCPFeature
                if not ctypes.windll.dxva2.SetVCPFeature(
                    self.handle,  # Pass the physical monitor handle
                    BYTE(code),    # VCP feature code
                    DWORD(value)   # Value to set
                ):
                    error_msg = f"SetVCPFeature failed for code {code}, value {value}: {ctypes.FormatError()}"
                    self.logger.error(error_msg)
                    raise VCPError(error_msg)
            except OSError as e: # This can happen if the handle is invalid or other system issues
                raise VCPError(f"SetVCPFeature call failed due to OSError for code {code}") from e

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
            """
            Gets the current and maximum value of a VCP feature from the physical monitor.

            Args:
                code: The VCP code of the feature to get.

            Returns:
                A tuple containing the current value and the maximum value of the feature.

            Raises:
                VCPError: If the `GetVCPFeatureAndVCPFeatureReply` Windows API call fails.
            """
            if self.handle is None:
                raise VCPError("Physical monitor handle is not initialized. Call __enter__ first.")

            feature_current = DWORD()  # To store the current value
            feature_max = DWORD()      # To store the maximum value
            # pvctCodeType is not used for standard VCP codes, so it's passed as None (NULL).
            # For some specific VCP codes it might be needed, but not for common ones like brightness/contrast.
            self.logger.debug(
                f"GetVCPFeatureAndVCPFeatureReply(Handle={self.handle}, Code={code}, CodeType=None, ...)"
            )
            try:
                # Call the Windows API function GetVCPFeatureAndVCPFeatureReply
                if not ctypes.windll.dxva2.GetVCPFeatureAndVCPFeatureReply(
                    self.handle,                # Physical monitor handle
                    BYTE(code),                  # VCP feature code
                    None,                        # Pointer to VCP code type (pvctCodeType), not used here
                    ctypes.byref(feature_current), # Pointer to receive current value
                    ctypes.byref(feature_max)      # Pointer to receive maximum value
                ):
                    error_msg = f"GetVCPFeatureAndVCPFeatureReply failed for code {code}: {ctypes.FormatError()}"
                    self.logger.error(error_msg)
                    raise VCPError(error_msg)
            except OSError as e: # This can happen if the handle is invalid or other system issues
                raise VCPError(f"GetVCPFeatureAndVCPFeatureReply call failed due to OSError for code {code}") from e

            self.logger.debug(
                f"GetVCPFeatureAndVCPFeatureReply for code {code} -> "
                f"Current: {feature_current.value}, Max: {feature_max.value}"
            )
            return feature_current.value, feature_max.value

        def get_vcp_capabilities(self) -> str:
            """
            Gets capabilities string from the virtual control panel

            Returns:
                One long capabilities string in the format:
                "(prot(monitor)type(LCD)model(ACER VG271U)cmds(01 02 03 07 0C)"

                No error checking for the string being valid. String can have
                bit errors or dropped characters.

            Raises:
                VCPError: Failed to get VCP feature.
            """

            """
            Gets the VCP capabilities string from the physical monitor.

            This string describes the features and VCP codes supported by the monitor.

            Returns:
                The VCP capabilities string (ASCII decoded).

            Raises:
                VCPError: If any of the Windows API calls for capabilities fail.
            """
            if self.handle is None:
                raise VCPError("Physical monitor handle is not initialized. Call __enter__ first.")

            cap_length = DWORD()
            self.logger.debug(f"GetCapabilitiesStringLength for handle {self.handle}")
            try:
                # First, get the length of the capabilities string
                if not ctypes.windll.dxva2.GetCapabilitiesStringLength(
                    self.handle, ctypes.byref(cap_length)
                ):
                    error_msg = f"GetCapabilitiesStringLength failed: {ctypes.FormatError()}"
                    self.logger.error(error_msg)
                    raise VCPError(error_msg)

                if cap_length.value == 0:
                    self.logger.warning("Capabilities string length is 0.")
                    return ""

                # Allocate a buffer for the capabilities string (it's an ASCII string)
                cap_string_buffer = (ctypes.c_char * cap_length.value)()
                self.logger.debug(
                    f"CapabilitiesRequestAndCapabilitiesReply for handle {self.handle}, Length: {cap_length.value}"
                )
                # Now, get the capabilities string itself
                if not ctypes.windll.dxva2.CapabilitiesRequestAndCapabilitiesReply(
                    self.handle, cap_string_buffer, cap_length
                ):
                    error_msg = (f"CapabilitiesRequestAndCapabilitiesReply failed: "
                                 f"{ctypes.FormatError()}")
                    self.logger.error(error_msg)
                    raise VCPError(error_msg)
            except OSError as e: # This can happen if the handle is invalid or other system issues
                raise VCPError("Capabilities retrieval call failed due to OSError") from e

            decoded_caps_string = cap_string_buffer.value.decode("ascii")
            self.logger.debug(f"Retrieved capabilities string: {decoded_caps_string}")
            return decoded_caps_string

        @staticmethod
        def get_vcps() -> list[BaseVCP]:
            """
            Opens handles to all physical VCPs.

            Returns:
                List of all VCPs detected.

            Raises:
                VCPError: Failed to enumerate VCPs.
            """
            """
            Enumerates all display monitors and creates `WindowsVCP` instances for them.

            This method uses `EnumDisplayMonitors` from `user32.dll` to find all
            active logical monitors, then creates a `WindowsVCP` object for each.
            The actual physical monitor handle is acquired when the `WindowsVCP`
            object's context is entered (`__enter__`).

            Returns:
                A list of `WindowsVCP` instances, one for each detected logical monitor.

            Raises:
                VCPError: If the `EnumDisplayMonitors` Windows API call fails.
            """
            vcps: list[BaseVCP] = []
            hmonitors_collected: list[HMONITOR] = [] # Temp list to store HMONITOR handles

            # Define the callback function type for EnumDisplayMonitors
            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                BOOL,      # Return type: BOOL (True to continue enumeration)
                HMONITOR,  # Argument 1: HMONITOR (handle to display monitor)
                HDC,       # Argument 2: HDC (handle to device context)
                ctypes.POINTER(RECT), # Argument 3: LPRECT (pointer to monitor RECT)
                LPARAM     # Argument 4: LPARAM (user-defined data)
            )

            # Define the Python callback function that will be called by EnumDisplayMonitors
            def _monitor_enum_callback(hmonitor: HMONITOR, hdc: HDC, lprect: ctypes.POINTER(RECT), lparam: LPARAM) -> bool:
                # Store the HMONITOR handle
                hmonitors_collected.append(hmonitor)
                # Log details (optional)
                # rect = lprect.contents
                # logging.getLogger(__name__).debug(
                # f"EnumDisplayMonitors: Found HMONITOR {hmonitor} with HDC {hdc}, "
                # f"Rect: ({rect.left},{rect.top})-({rect.right},{rect.bottom})"
                # )
                # Unused parameters, mark as such to potentially help linters
                del hdc, lprect, lparam
                return True  # Return True to continue enumeration

            # Create a C-callable function pointer from the Python callback
            c_callback = MONITORENUMPROC(_monitor_enum_callback)
            logging.getLogger(__name__).debug("Calling EnumDisplayMonitors")
            try:
                # Call EnumDisplayMonitors.
                # The first two NULLs mean enumerate all display monitors on the desktop.
                # The last 0 is for the dwData (lParam) passed to the callback, not used here.
                if not ctypes.windll.user32.EnumDisplayMonitors(None, None, c_callback, 0):
                    error_msg = f"EnumDisplayMonitors failed: {ctypes.FormatError()}"
                    logging.getLogger(__name__).error(error_msg)
                    raise VCPError(error_msg)
            except OSError as e: # This can happen due to system-level issues
                raise VCPError("EnumDisplayMonitors call failed due to OSError") from e

            logging.getLogger(__name__).debug(f"EnumDisplayMonitors found {len(hmonitors_collected)} logical monitors.")
            # Create a WindowsVCP instance for each HMONITOR found
            for hmonitor_handle in hmonitors_collected:
                vcps.append(WindowsVCP(hmonitor_handle))

            return vcps
