"""
This module provides the Linux-specific implementation of the VCP (Virtual Control Panel) interface.

It uses the `ddcci` protocol over I2C to communicate with monitors.
The `LinuxVCP` class handles the low-level details of constructing and sending
DDC/CI commands and parsing responses.
"""
from .vcp_abc import BaseVCP, VCPIOError, VCPPermissionError
from types import TracebackType
from typing import Literal, Type
import os
import struct
import sys
import time
import logging

# hide the Linux code from Windows CI coverage
if sys.platform.startswith("linux"):
    import fcntl
    import pyudev


class LinuxVCP(BaseVCP):
    """
    Linux API access to a monitor's virtual control panel using DDC/CI over I2C.

    This class implements the `BaseVCP` interface for Linux systems.
    It communicates with monitors using the I2C protocol and the DDC/CI standard.

    References:
        - DDC/CI Specification: Provides the protocol details.
        - https://github.com/Informatic/python-ddcci: A Python DDC/CI library.
        - https://github.com/siemer/ddcci/: Another DDC/CI implementation.

    Attributes:
        GET_VCP_HEADER_LENGTH: Length of the header in a Get VCP Feature reply.
        PROTOCOL_FLAG: Protocol flag used in DDC/CI messages.
        GET_VCP_CMD: Command code for Get VCP Feature.
        GET_VCP_REPLY: Reply code for Get VCP Feature.
        SET_VCP_CMD: Command code for Set VCP Feature.
        GET_VCP_CAPS_CMD: Command code for Capabilities Request.
        GET_VCP_CAPS_REPLY: Reply code for Capabilities Request.
        GET_VCP_TIMEOUT: Timeout for Get VCP Feature command in seconds.
        CMD_RATE: Minimum time between commands in seconds.
        DDCCI_ADDR: I2C address of the DDC/CI device.
        HOST_ADDRESS: Virtual I2C slave address of the host.
        I2C_SLAVE: ioctl command to set the I2C slave address.
        GET_VCP_RESULT_CODES: Mapping of result codes from Get VCP Feature reply to messages.
        CHECKSUM_ERRORS: How to handle checksum errors ("ignore", "warning", "strict").
    """

    # Constants for DDC/CI protocol
    GET_VCP_HEADER_LENGTH = 2  # Expected length of the header packet for Get VCP Feature reply
    PROTOCOL_FLAG = 0x80  # Protocol flag, bit 7 of the length byte in DDC/CI messages

    # VCP command codes
    GET_VCP_CMD = 0x01  # Command to get a VCP feature
    GET_VCP_REPLY = 0x02  # Expected reply code for a successful Get VCP Feature
    SET_VCP_CMD = 0x03  # Command to set a VCP feature
    GET_VCP_CAPS_CMD = 0xF3  # Command to request monitor capabilities
    GET_VCP_CAPS_REPLY = 0xE3  # Expected reply code for a successful Capabilities Request

    # Timeouts and rate limiting
    GET_VCP_TIMEOUT = 0.04  # Minimum delay (seconds) to wait for a reply after Get VCP command (spec: >=40ms)
    CMD_RATE = 0.05  # Minimum delay (seconds) between sending commands (spec: >=50ms)

    # I2C addresses
    DDCCI_ADDR = 0x37  # Standard I2C slave address for DDC/CI communication
    HOST_ADDRESS = 0x51  # Source address used in DDC/CI messages (virtual I2C slave address of the host)
    I2C_SLAVE = 0x0703  # Linux ioctl request code to set the I2C slave address for a device

    # Result codes for Get VCP Feature reply (byte 3 of payload)
    GET_VCP_RESULT_CODES = {
        0: "No Error",
        1: "Unsupported VCP code",
    }

    # Behavior for checksum errors. Can be "ignore", "warning", or "strict".
    CHECKSUM_ERRORS: str = "ignore"

    def __init__(self, bus_number: int):
        """
        Args:
            bus_number: I2C bus number.
        """
        self.logger = logging.getLogger(__name__)
        self.bus_number = bus_number
        self.fd = 0
        self.fp: str = f"/dev/i2c-{self.bus_number}"
        # time of last feature set call
        self.last_set: float | None = None

    def __enter__(self):
        """
        Initializes the LinuxVCP instance.

        Args:
            bus_number: The I2C bus number (e.g., 0 for /dev/i2c-0).
        """
        self.logger = logging.getLogger(__name__)
        self.bus_number = bus_number
        self.fd: int = 0  # File descriptor for the I2C device
        self.fp: str = f"/dev/i2c-{self.bus_number}"  # File path to the I2C device
        self.last_set: float | None = None # Timestamp of the last set_vcp_feature call for rate limiting

    def __enter__(self):
        """
        Opens the I2C device and prepares it for communication.

        Raises:
            VCPPermissionError: If there's a permission error accessing the I2C bus.
            VCPIOError: If the I2C bus cannot be opened or configured.
        """
        def _cleanup_fd(fd_to_close: int | None):
            """Helper to close file descriptor if open."""
            if fd_to_close:
                try:
                    os.close(fd_to_close)
                except OSError:
                    # Ignore errors on close if we're already handling another error
                    pass

        try:
            # Open the I2C device file
            self.fd = os.open(self.fp, os.O_RDWR)
            # Set the I2C slave address to the DDC/CI address
            fcntl.ioctl(self.fd, self.I2C_SLAVE, self.DDCCI_ADDR)
            # Perform a dummy read to check if the monitor is responsive.
            # Some monitors require this to "wake up".
            self.read_bytes(1)
        except PermissionError as e:
            _cleanup_fd(self.fd)
            self.fd = 0 # Ensure fd is reset
            raise VCPPermissionError(f"Permission error accessing I2C bus {self.fp}") from e
        except OSError as e:
            _cleanup_fd(self.fd)
            self.fd = 0 # Ensure fd is reset
            raise VCPIOError(f"Unable to open or configure I2C bus {self.fp}") from e
        except Exception as e: # Catch any other unexpected errors during setup
            _cleanup_fd(self.fd)
            self.fd = 0 # Ensure fd is reset
            raise VCPIOError(f"An unexpected error occurred with I2C bus {self.fp}") from e
        return self

    def __exit__(
        self,
        exception_type: Type[BaseException] | None,
        exception_value: BaseException | None,
        exception_traceback: TracebackType | None,
    ) -> Literal[False]:
        """
        Closes the I2C device.

        Returns:
            False, to indicate that any exceptions should not be suppressed.
        """
        if self.fd: # Check if file descriptor is valid and open
            try:
                os.close(self.fd)
            except OSError as e:
                # Log or handle error during close if necessary,
                # but avoid overshadowing an existing exception.
                self.logger.error(f"Error closing I2C bus {self.fp}: {e}")
                # Optionally, re-raise as VCPIOError if closing is critical
                # raise VCPIOError(f"Unable to close I2C bus {self.fp}") from e
            finally:
                self.fd = 0 # Mark as closed
        return False # Do not suppress exceptions

    def set_vcp_feature(self, code: int, value: int):
        """
        Sets the value of a feature on the virtual control panel.

        Args:
            code: feature code
            value: feature value

        Raises:
            VCPIOError: failed to set VCP feature
        """
        self.rate_limit() # Ensure compliance with DDC/CI command rate

        # Construct the DDC/CI message payload for Set VCP Feature
        # Payload: [SET_VCP_CMD, VCP Code, Value (High Byte), Value (Low Byte)]
        payload_data = bytearray()
        payload_data.append(self.SET_VCP_CMD)
        payload_data.append(code)
        # Pack the 16-bit value into two bytes (Big Endian)
        # struct.pack(">H", value) would also work here.
        high_byte, low_byte = (value >> 8) & 0xFF, value & 0xFF
        payload_data.append(high_byte)
        payload_data.append(low_byte)

        # Construct the full DDC/CI message
        # Message: [Host Address, Length | PROTOCOL_FLAG, Payload..., Checksum]
        message = bytearray()
        message.append(self.HOST_ADDRESS)
        # Length byte includes the payload itself. PROTOCOL_FLAG is ORed in.
        message.append(len(payload_data) | self.PROTOCOL_FLAG)
        message.extend(payload_data)
        # Checksum is calculated over (DDCCI_ADDR << 1) + message up to checksum byte
        checksum_data = bytearray([self.DDCCI_ADDR << 1]) + message # Data for checksum calculation
        message.append(self.get_checksum(checksum_data))

        # Send the DDC/CI message over I2C
        self.logger.debug(f"set_vcp_feature: code={code:02X}, value={value}, "
                          f"data={' '.join([f'{b:02X}' for b in message])}")
        self.write_bytes(message)

        # Update the timestamp of the last command sent
        self.last_set = time.time()

    def get_vcp_feature(self, code: int) -> tuple[int, int]:
        """
        Gets the value of a feature from the virtual control panel.

        Args:
            code: Feature code.

        Returns:
            Current feature value, maximum feature value.

        Raises:
            VCPIOError: Failed to get VCP feature.
        """
        self.rate_limit() # Ensure compliance with DDC/CI command rate

        # Construct the DDC/CI message payload for Get VCP Feature
        # Payload: [GET_VCP_CMD, VCP Code]
        payload_data = bytearray()
        payload_data.append(self.GET_VCP_CMD)
        payload_data.append(code)

        # Construct the full DDC/CI message
        # Message: [Host Address, Length | PROTOCOL_FLAG, Payload..., Checksum]
        message = bytearray()
        message.append(self.HOST_ADDRESS)
        message.append(len(payload_data) | self.PROTOCOL_FLAG)
        message.extend(payload_data)
        # Checksum is calculated over (DDCCI_ADDR << 1) + message up to checksum byte
        checksum_data = bytearray([self.DDCCI_ADDR << 1]) + message
        message.append(self.get_checksum(checksum_data))

        # Send the DDC/CI message over I2C
        self.logger.debug(f"get_vcp_feature: code={code:02X}, "
                          f"data={' '.join([f'{b:02X}' for b in message])}")
        self.write_bytes(message)

        # Wait for the monitor to process the command
        time.sleep(self.GET_VCP_TIMEOUT)

        # Read the DDC/CI reply header
        # Reply Header: [Source Address (monitor), Length | PROTOCOL_FLAG]
        reply_header = self.read_bytes(self.GET_VCP_HEADER_LENGTH)
        self.logger.debug(f"get_vcp_feature reply header: "
                          f"{' '.join([f'{b:02X}' for b in reply_header])}")
        # Source address is ignored for now.
        # Length byte includes the payload and the checksum.
        _, reply_length_byte = struct.unpack("=BB", reply_header)
        reply_payload_length = reply_length_byte & ~self.PROTOCOL_FLAG  # Clear protocol flag

        # Read the DDC/CI reply payload and checksum
        # Reply Payload + Checksum: [Payload..., Checksum]
        reply_payload_with_checksum = self.read_bytes(reply_payload_length + 1) # +1 for checksum
        self.logger.debug(f"get_vcp_feature reply payload+csum: "
                          f"{' '.join([f'{b:02X}' for b in reply_payload_with_checksum])}")

        # Verify checksum
        # Checksum is calculated over reply_header + reply_payload (excluding received checksum)
        received_payload = reply_payload_with_checksum[:-1]
        received_checksum = reply_payload_with_checksum[-1]
        expected_checksum_data = reply_header + received_payload
        calculated_checksum = self.get_checksum(expected_checksum_data)

        if received_checksum != calculated_checksum:
            checksum_mismatch_msg = (f"Checksum mismatch: expected {calculated_checksum:02X}, "
                                     f"got {received_checksum:02X}")
            if self.CHECKSUM_ERRORS.lower() == "strict":
                raise VCPIOError(message)
            elif self.CHECKSUM_ERRORS.lower() == "warning":
                self.logger.warning(message)
            # else ignore

        # unpack the payload
        (
            reply_code,
            result_code,
            vcp_opcode,
            vcp_type_code,
            feature_max,
            feature_current,
        ) = struct.unpack(">BBBBHH", payload)

        if reply_code != self.GET_VCP_REPLY:
            raise VCPIOError(f"received unexpected response code: {reply_code}")

        if vcp_opcode != code:
            raise VCPIOError(f"received unexpected opcode: {vcp_opcode}")

        if result_code > 0:
            try:
                message = self.GET_VCP_RESULT_CODES[result_code]
            except KeyError:
                message = f"received result with unknown code: {result_code}"
            raise VCPIOError(message)

        return feature_current, feature_max

    def get_vcp_capabilities(self):
        """
        Gets capabilities string from the virtual control panel.

        Returns:
            One long capabilities string in the format:
            "(prot(monitor)type(LCD)model(ACER VG271U)cmds(01 02 03 07 0C)"

            No error checking for the string being valid. String can have
            bit errors or dropped characters.

        Raises:
            VCPError: Failed to get VCP feature.
        """

        # Create an empty capabilities string to be filled with the data
        caps_str = ""

        self.rate_limt()

        # Get the first 32B of capabilities string
        offset = 0

        # Keep a count going to keep things sane
        loop_count = 0
        loop_count_limit = 40

        while loop_count < loop_count_limit:
            loop_count += 1

            # transmission data
            data = bytearray()
            data.append(self.GET_VCP_CAPS_CMD)
            low_byte, high_byte = struct.pack("H", offset)
            data.append(high_byte)
            data.append(low_byte)

            # add headers and footers
            data.insert(0, (len(data) | self.PROTOCOL_FLAG))
            data.insert(0, self.HOST_ADDRESS)
            data.append(self.get_checksum(data))

            # write data
            self.write_bytes(data)

            time.sleep(self.GET_VCP_TIMEOUT)

            # read the data
            header = self.read_bytes(self.GET_VCP_HEADER_LENGTH)
            self.logger.debug("header=" + " ".join([f"{x:02X}" for x in header]))
            source, length = struct.unpack("BB", header)
            length &= ~self.PROTOCOL_FLAG  # clear protocol flag
            payload = self.read_bytes(length + 1)
            self.logger.debug("payload=" + " ".join([f"{x:02X}" for x in payload]))

            # check if length is valid
            if length < 3 or length > 35:
                raise VCPIOError(f"received unexpected response length: {length}")

            # check checksum
            payload, checksum = struct.unpack(f"{length}sB", payload)
            calculated_checksum = self.get_checksum(header + payload)
            checksum_xor = checksum ^ calculated_checksum
            if checksum_xor:
                message = f"checksum does not match: {checksum_xor}"
                if self.CHECKSUM_ERRORS.lower() == "strict":
                    raise VCPIOError(message)
                elif self.CHECKSUM_ERRORS.lower() == "warning":
                    self.logger.warning(message)
                # else ignore
            # remove checksum from length

            # unpack the payload
            reply_code, payload = struct.unpack(f">B{length - 1}s", payload)
            length -= 1

            if reply_code != self.GET_VCP_CAPS_REPLY:
                raise VCPIOError(f"received unexpected response code: {reply_code}")

            # unpack the payload
            offset, payload = struct.unpack(f">H{length - 2}s", payload)
            length -= 2

            if length > 0:
                caps_str += payload.decode("ASCII")
            else:
                break

            # update the offset and go again
            offset += length

        self.logger.debug(f"caps str={caps_str}")

        if loop_count >= loop_count_limit:
            raise VCPIOError("Capabilities string incomplete or too long")

        return caps_str

    @staticmethod
    def get_checksum(data: bytearray | bytes) -> int:
        """
        Computes the checksum for a set of data, with the option to
        use the virtual host address (per the DDC-CI specification).

        Args:
            data: Data array to transmit.

        Returns:
            Checksum for the data.
        """
        checksum = 0x00
        for data_byte in data:
            checksum ^= data_byte
        return checksum

    def rate_limt(self):
        """Rate limits messages to the VCP."""
        if self.last_set is None:
            return

        rate_delay = self.CMD_RATE - time.time() - self.last_set
        if rate_delay > 0:
            time.sleep(rate_delay)

    def read_bytes(self, num_bytes: int) -> bytes:
        """
        Reads bytes from the I2C bus.

        Args:
            num_bytes: number of bytes to read

        Raises:
            VCPIOError: unable to read data
        """
        try:
            return os.read(self.fd, num_bytes)
        except OSError as e:
            raise VCPIOError("unable to read from I2C bus") from e

    def write_bytes(self, data: bytes):
        """
        Writes bytes to the I2C bus.

        Args:
            data: data to write to the I2C bus

        Raises:
            VCPIOError: unable to write data
        """
        try:
            os.write(self.fd, data)
        except OSError as e:
            raise VCPIOError("unable write to I2C bus") from e

    @staticmethod
    def get_vcps() -> list[BaseVCP]:
        """
        Interrogates I2C buses to determine if they are DDC-CI capable.

        Returns:
            List of all VCPs detected.
        """
        vcps: list[BaseVCP] = []

        # iterate I2C devices
        for device in pyudev.Context().list_devices(subsystem="i2c"):
            vcp = LinuxVCP(device.sys_number)
            try:
                with vcp:
                    pass
            except (OSError, VCPIOError):
                pass
            else:
                vcps.append(vcp)

        return vcps