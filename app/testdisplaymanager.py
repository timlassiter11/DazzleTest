"""
Manages the presentation of test steps on a dedicated display.

This module provides `TestDisplayManager` which is responsible for:
- Displaying test images fullscreen on a selected monitor.
- Controlling monitor backlight levels via VCP (if available).
- Handling user input for navigating test steps (next, previous, pause, resume, stop).
- Showing information about the current test step.

It defines `TestDisplay` to hold information about the target display and its
capabilities. The manager uses a `QWidget` to show images and a `QLabel` for
pause/information overlays.
"""
from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QScreen
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.mccs import Monitor
from app.mccs.mccs import Capabilities
from app.utils import get_test_image
from app.testdatamodel import TestStep


@dataclass
class TestDisplay:
    """
    Holds information about a display screen used for testing.

    Attributes:
        name (str): A human-readable name for the display (e.g., "Monitor 1").
        screen (QScreen): The Qt QScreen object representing the display.
        vcp (Monitor | None): An optional `Monitor` object for VCP control (e.g., backlight).
        capabilities (Capabilities | None): Optional VCP capabilities of the monitor.
    """
    name: str
    screen: QScreen
    vcp: Monitor | None = None
    capabilities: Capabilities | None = None


class TestDisplayManager(QObject):
    """
    Manages the display of test images and information on a selected screen.

    This class handles the lifecycle of a test sequence on a display, including
    starting, stopping, pausing, resuming, and navigating through test steps.
    It also manages backlight control if a VCP interface is available for the
    selected display.

    Signals:
        statusChanged: Emitted when the test status changes (e.g., started, stopped, paused).
        stepChanged: Emitted with the new step index when the current test step changes.
    """
    statusChanged: Signal = Signal()  #: Signal emitted when the test status (running/paused/stopped) changes.
    stepChanged: Signal = Signal(int) #: Signal emitted with the new index when the current step changes.

    _widget: QWidget  #: The main widget used to display images fullscreen.
    _current_index: int = 0 #: Index of the currently active test step.

    # Default backlight values, updated when a test starts on a specific display.
    _backlight_max: int = 100        #: Maximum backlight level supported by the display.
    _starting_backlight: int = 100   #: Backlight level before the test started, to restore later.
    _pause_backlight: int = 100      #: Backlight level to use when the test is paused.
    
    _is_paused: bool = False #: Flag indicating if the test is currently paused.

    def __init__(self, parent: QObject | None = None) -> None:
        """
        Initializes the TestDisplayManager.

        Sets up the image display widget, pause label, and installs an event filter
        to capture keyboard input for controlling the test.

        Args:
            parent: The parent QObject, if any.
        """
        super().__init__(parent=parent)

        self._current_index = 0
        self._display: TestDisplay | None = None  # Information about the currently used display
        self._steps: list[TestStep] = []          # List of test steps for the current test

        # Main widget for displaying images fullscreen
        self._widget = QWidget()
        self._widget.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint) # Frameless and on top

        # Layout for the image label within the main widget
        layout = QVBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0) # No margins
        layout.setSpacing(0)                  # No spacing

        # Label to display the test image
        self._image_label = QLabel(self._widget)
        self._image_label.setMinimumSize(1, 1) # Ensure it can shrink
        self._image_label.setScaledContents(True) # Scale image to fit label
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding # Expand to fill widget
        )
        layout.addWidget(self._image_label)

        # Label to display pause information (as a splash screen type overlay)
        self._pause_label = QLabel(self._widget) # Parent is _widget so it moves with it
        self._pause_label.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)
        self._pause_label.setStyleSheet("background-color: rgba(0, 0, 0, 180); color: white; padding: 20px; font-size: 24px;")
        self._pause_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pause_label.hide() # Initially hidden

        # Install event filter to capture key presses at the application level
        app = QCoreApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    @property
    def current_index(self) -> int:
        """Gets the index of the current test step."""
        return self._current_index
    
    @current_index.setter
    def current_index(self, value: int) -> None:
        """
        Sets the current test step index.

        If the new index is valid and different from the current one,
        it updates the display and emits the `stepChanged` signal.

        Args:
            value: The new step index.

        Raises:
            IndexError: If the value is out of the valid range of steps.
        """
        if 0 <= value < len(self._steps):
            if self._current_index != value:
                self._current_index = value
                self._is_paused = False # Changing step usually unpauses
                self._update()
                self.stepChanged.emit(value)
        else:
            # Allow setting to len(self._steps) to indicate end, but clamp for _update
            if value == len(self._steps) and len(self._steps) > 0:
                 # Special case: if trying to go one past the end, stop the test.
                self.stop()
                return
            self.logger.warning(f"Attempted to set current_index to {value}, which is out of range (0-{len(self._steps)-1}).")
            # Option: raise IndexError("Current index out of range")
            # Option: clamp to valid range, e.g. self._current_index = max(0, min(value, len(self._steps) -1))
            # For now, just log and don't change if truly out of bounds for _update

    @property
    def current_step(self) -> TestStep | None:
        """
        Gets the current `TestStep` object.

        Returns:
            The current `TestStep`, or None if no steps are loaded or index is out of bounds.
        """
        if self._steps and 0 <= self._current_index < len(self._steps):
            return self._steps[self._current_index]
        return None

    @property
    def is_running(self) -> bool:
        """Checks if the test display widget is currently visible (i.e., test is active)."""
        return self._widget.isVisible()

    @property
    def is_paused(self) -> bool:
        """Checks if the test is currently paused."""
        return self._is_paused

    def start(
        self,
        display: TestDisplay,
        steps: list[TestStep],
    ) -> None:
        """
        Starts or restarts the test sequence on the specified display with the given steps.

        Args:
            display: The `TestDisplay` object representing the target screen.
            steps: A list of `TestStep` objects for the test sequence.
        """
        if not steps:
            self.logger.warning("Cannot start test: no steps provided.")
            return

        self._current_index = 0
        self._display = display
        self._steps = steps
        self._is_paused = False

        # Store initial backlight settings if VCP is available
        if display.vcp:
            # TODO: Check if the display supports backlight functions (e.g., from capabilities)
            try:
                with display.vcp: # Ensure VCP is context-managed for operations
                    self._starting_backlight = display.vcp.backlight
                    self._backlight_max = display.vcp.backlight_maximum
                    # Default pause backlight to max, or current if max is unusual
                    self._pause_backlight = self._backlight_max if self._backlight_max > 0 else self._starting_backlight
                    self.logger.info(f"Initial backlight: {self._starting_backlight}, Max: {self._backlight_max}")
            except Exception as e:
                self.logger.error(f"Error accessing VCP for initial backlight settings: {e}")
                # Fallback to defaults if VCP access fails
                self._starting_backlight = 100 
                self._backlight_max = 100
                self._pause_backlight = 100
        else:
            # Defaults if no VCP
            self._starting_backlight = 100
            self._backlight_max = 100
            self._pause_backlight = 100
        
        # Configure the main display widget for the target screen
        self._widget.setScreen(display.screen)
        self._widget.setGeometry(display.screen.geometry()) # Set to screen's geometry

        # Update display with the first step
        self._update()
        self._widget.showFullScreen() # Show fullscreen
        self.statusChanged.emit()     # Notify status change

    def stop(self) -> None:
        """
        Stops the current test sequence.

        Hides the display widget, restores the initial backlight level (if VCP available),
        and emits the `statusChanged` signal.
        """
        self._widget.hide()
        self._pause_label.hide()
        self._is_paused = False
        self.statusChanged.emit()
        # Restore initial backlight
        self._set_backlight(self._starting_backlight)
        self.logger.info("Test stopped, backlight restored to initial setting.")

    def pause(self) -> None:
        """
        Pauses the current test step.

        Sets the backlight to the pause level and shows the pause information overlay.
        Emits `statusChanged`.
        """
        if not self.is_running or self.is_paused:
            return
        self._is_paused = True
        self._update() # Update will show pause label and set pause backlight
        self.statusChanged.emit()
        self.logger.info("Test paused.")

    def resume(self) -> None:
        """
        Resumes the current test step if paused.

        Restores the step's defined backlight and hides the pause overlay.
        Emits `statusChanged`.
        """
        if not self.is_running or not self.is_paused:
            return
        self._is_paused = False
        self._update() # Update will hide pause label and set step backlight
        self.statusChanged.emit()
        self.logger.info("Test resumed.")

    def next(self) -> None:
        """
        Advances to the next test step if available.

        If already on the last step, this does nothing.
        Emits `stepChanged` if successful.
        """
        if self._current_index < len(self._steps) - 1:
            self.current_index += 1 # Setter handles update and signal
        else:
            self.logger.info("Already at the last step.")
            # Optionally, could stop or loop here.

    def previous(self) -> None:
        """
        Goes back to the previous test step if available.

        If already on the first step, this does nothing.
        Emits `stepChanged` if successful.
        """
        if self._current_index > 0:
            self.current_index -= 1 # Setter handles update and signal
        else:
            self.logger.info("Already at the first step.")

    def _update(self) -> None:
        """
        Updates the display with the current test step's image and backlight.

        Also handles showing/hiding the pause overlay and adjusting its position.
        This is an internal method called when the step changes or pause state toggles.
        """
        current_step_obj = self.current_step
        if not self._display or not current_step_obj:
            self.logger.warning("_update called with no display or current step.")
            return

        # Update image
        pixmap = get_test_image(current_step_obj.image)
        if pixmap:
            self._image_label.setPixmap(pixmap)
        else:
            self._image_label.clear()
            self._image_label.setText(f"Image not found:\n{current_step_obj.image}")
            self.logger.warning(f"Image not found: {current_step_obj.image}")

        # Update pause label text (even if hidden, so it's ready)
        pause_text = (f"Step: {self._current_index + 1} / {len(self._steps)}\n"
                      f"Name: {current_step_obj.name}\n"
                      f"Image: {current_step_obj.image}\n"
                      f"Target Backlight: {current_step_obj.backlight}%")
        if self.is_paused:
             pause_text += f"\nPaused Backlight: {self._pause_backlight}% (Use Up/Down to adjust)"
        self._pause_label.setText(pause_text)


        if self.is_paused:
            self._set_backlight(self._pause_backlight)
            # Ensure pause label is correctly sized and centered on the image widget
            self._pause_label.adjustSize() # Adjust size to content
            # Center the pause label on the main widget (_widget)
            # _widget should be fullscreen on the correct screen.
            widget_geo = self._widget.geometry()
            label_size_hint = self._pause_label.sizeHint()
            
            # Calculate new position to center it on the _widget
            new_x = widget_geo.x() + (widget_geo.width() - label_size_hint.width()) // 2
            new_y = widget_geo.y() + (widget_geo.height() - label_size_hint.height()) // 2
            
            # Move and show. Since _pause_label is a child of _widget, its coordinates are relative
            # if we don't give it its own window flags that make it independent.
            # With SplashScreen flag, it's an independent window, so coords should be global.
            self._pause_label.move(new_x, new_y)
            self._pause_label.show()
        else:
            self._set_backlight(current_step_obj.backlight)
            self._pause_label.hide()

    def _set_backlight(self, backlight_percent: int) -> None:
        """
        Sets the backlight level of the display if VCP is available.

        Args:
            backlight_percent: The desired backlight level (0-100).
                               This will be clamped to the monitor's reported maximum.
        """
        if self._display and self._display.vcp:
            try:
                # Clamp backlight_percent to be within 0 and reported maximum
                # (or 100 if max is 0 or unavailable)
                effective_max = self._backlight_max if self._backlight_max > 0 else 100
                clamped_backlight = max(0, min(backlight_percent, effective_max))

                with self._display.vcp: # Ensure VCP context is managed
                    self._display.vcp.backlight = clamped_backlight
                self.logger.debug(f"Set backlight to {clamped_backlight}% (requested {backlight_percent}%)")
            except Exception as e:
                self.logger.error(f"Failed to set backlight to {backlight_percent}%: {e}")
        else:
            self.logger.debug(f"Backlight control not available or display not set. "
                              f"Requested {backlight_percent}%.")

    def eventFilter(self, watched: QObject, event: QKeyEvent) -> bool:
        """
        Filters events to capture global key presses for controlling the test.

        Handles:
            - Escape: Stop the test.
            - Space: Pause/Resume the test.
            - Right Arrow: Next step.
            - Left Arrow: Previous step.
            - Up Arrow: Increase backlight when paused.
            - Down Arrow: Decrease backlight when paused.

        Args:
            watched: The QObject that originally received the event.
            event: The QEvent object.

        Returns:
            True if the event was handled, False otherwise.
        """
        if self.is_running and event.type() == QKeyEvent.Type.KeyRelease and isinstance(event, QKeyEvent):
            key = event.key()
            alt_modifier = event.modifiers() & Qt.KeyboardModifier.AltModifier

            if key == Qt.Key_Escape:
                self.logger.debug("Escape key pressed, stopping test.")
                self.stop()
                return True
            elif key == Qt.Key_Space:
                self.logger.debug("Space key pressed, toggling pause.")
                if self.is_paused:
                    self.resume()
                else:
                    self.pause()
                return True
            # Navigation keys should only work if not paused, or if explicitly desired
            elif not self.is_paused and key == Qt.Key_Right:
                self.logger.debug("Right arrow key pressed, next step.")
                self.next()
                return True
            elif not self.is_paused and key == Qt.Key_Left:
                self.logger.debug("Left arrow key pressed, previous step.")
                self.previous()
                return True
            # Backlight adjustment keys only work if paused and VCP is available
            elif self.is_paused and self._display and self._display.vcp:
                if key == Qt.Key_Up:
                    self._pause_backlight = min(self._backlight_max if self._backlight_max > 0 else 100, self._pause_backlight + 1)
                    self.logger.debug(f"Up arrow key pressed in pause, new pause backlight: {self._pause_backlight}")
                    self._update() # Update display with new pause backlight
                    return True
                elif key == Qt.Key_Down:
                    self._pause_backlight = max(0, self._pause_backlight - 1)
                    self.logger.debug(f"Down arrow key pressed in pause, new pause backlight: {self._pause_backlight}")
                    self._update() # Update display with new pause backlight
                    return True
            # Allow Alt+F4 to close even in fullscreen
            elif key == Qt.Key_F4 and alt_modifier:
                self.logger.info("Alt+F4 pressed, stopping test and allowing application to close.")
                self.stop()
                QCoreApplication.quit() # Allow application to quit
                return True


        return super().eventFilter(watched, event) # Pass unhandled events along
