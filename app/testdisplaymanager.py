import logging
from dataclasses import dataclass

from PySide6.QtCore import (
    QByteArray,
    QCoreApplication,
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QKeyEvent, QScreen
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from app.mccs import MCCSCommand, Monitor
from app.testdatamodel import TestStep
from app.utils import file_to_display_name, get_test_image
from app.widgets.stepinfowidget import StepInfoWidget

logger = logging.getLogger(__name__)


@dataclass
class TestDisplay:
    pyside_screen: QScreen
    mccs_monitor: Monitor | None = None

    @property
    def name(self) -> str:
        """Return the name of the display."""
        return self.pyside_screen.name()


class TestDisplayManager(QObject):
    statusChanged: Signal = Signal()
    stepChanged: Signal = Signal(int)

    FADE_ANIMATION_DURATION: int = 250
    STEP_INFO_DISPLAY_DURATION: int = 2500

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent=parent)

        # This should get updated when we pass a display to start the test
        # Just use some sane default value.
        self._backlight_max: int = 100
        self._starting_backlight: int = self._backlight_max
        self._pause_backlight: int = self._backlight_max

        self._is_paused: bool = False

        self._current_index = 0
        self._display: TestDisplay | None = None
        self._steps: list[TestStep] = []

        self._widget = QWidget()
        self._widget.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        layout = QGridLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._image_label = QLabel(self._widget)
        self._image_label.setMinimumSize(1, 1)
        self._image_label.setScaledContents(True)
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._step_info_widget = StepInfoWidget()
        self._step_info_widget.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum
        )
        self._step_info_widget.setAutoFillBackground(True)

        self._effect = QGraphicsOpacityEffect(self, opacity=0.0)
        self._step_info_widget.setGraphicsEffect(self._effect)
        self._animation = QPropertyAnimation(self._effect, QByteArray(b"opacity"))
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(self.FADE_ANIMATION_DURATION)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)

        layout.addWidget(self._step_info_widget, 0, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._image_label, 0, 0)

        self._pause_hide_timer = QTimer(self)
        self._pause_hide_timer.setSingleShot(True)
        self._pause_hide_timer.setInterval(self.STEP_INFO_DISPLAY_DURATION)
        self._pause_hide_timer.timeout.connect(self._hide_pause_widget)

        app = QCoreApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    @property
    def current_index(self) -> int:
        return self._current_index

    @current_index.setter
    def current_index(self, value: int) -> None:
        if 0 <= value < len(self._steps):
            if self._current_index != value:
                self._current_index = value
                self._update()
                self.stepChanged.emit(value)
        else:
            raise IndexError("Current index out of range")

    @property
    def current_step(self) -> TestStep:
        return self._steps[self._current_index]

    @property
    def is_running(self) -> bool:
        return self._widget.isVisible()

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def start(
        self,
        display: TestDisplay,
        steps: list[TestStep],
    ) -> None:
        if not steps:
            raise ValueError("No test steps provided")

        self._current_index = 0
        self._display = display
        self._steps = steps
        self._step_info_widget.total_steps = len(steps)
        self.resume(animate=False)

        if display.mccs_monitor and self._can_set_backlight():
            self._starting_backlight = display.mccs_monitor.backlight
            self._backlight_max = display.mccs_monitor.backlight_maximum
            self._pause_backlight = self._starting_backlight

        self._widget.setScreen(display.pyside_screen)
        self._widget.setGeometry(display.pyside_screen.geometry())

        self._update()
        self._widget.showFullScreen()
        self._show_pause_widget(autohide=True)
        self.statusChanged.emit()

    def stop(self) -> None:
        self._widget.hide()
        self.resume(animate=False)
        self.statusChanged.emit()
        self._set_backlight(self._starting_backlight)

    def pause(self, animate=True) -> None:
        self._is_paused = True
        self._show_pause_widget(animate)
        self._update()
        self.statusChanged.emit()

    def resume(self, animate=True) -> None:
        self._is_paused = False
        self._hide_pause_widget(animate)
        self._update()
        self.statusChanged.emit()

    def next(self) -> None:
        if self._current_index < len(self._steps) - 1:
            self._current_index += 1

            if not self.is_paused:
                self._show_pause_widget(autohide=True)

            self._update()
            self.stepChanged.emit(self._current_index)

    def previous(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1

            if not self.is_paused:
                self._show_pause_widget(autohide=True)

            self._update()
            self.stepChanged.emit(self._current_index)

    def _show_pause_widget(self, animate: bool = True, autohide: bool = False) -> None:

        # If the widget is already visible and opacity is 1.0, we don't want to animate it again
        if self._effect.opacity() != 1.0:
            if animate:
                self._animation.setDirection(QPropertyAnimation.Direction.Forward)
                self._animation.start()
            else:
                self._effect.setOpacity(1.0)

        # Start the timer to hide the pause widget
        if autohide:
            self._pause_hide_timer.start()
        # Stop the timer to prevent it from hiding
        else:
            self._pause_hide_timer.stop()

    def _hide_pause_widget(self, animate: bool = True) -> None:
        if animate:
            self._animation.setDirection(QPropertyAnimation.Direction.Backward)
            self._animation.start()
        else:
            self._effect.setOpacity(0.0)

    def _update(self) -> None:
        if self._current_index < 0 or self._current_index >= len(self._steps):
            raise IndexError("Current index out of range")

        step = self._steps[self._current_index]
        pixmap = get_test_image(step.image)
        if pixmap is not None:
            self._image_label.setPixmap(pixmap)
        else:
            self._image_label.clear()
            self._image_label.setText(f"Image {step.image} not found")

        self._step_info_widget.title = step.name
        self._step_info_widget.current_step = self._current_index + 1
        self._step_info_widget.image_name = file_to_display_name(step.image)
        self._step_info_widget.step_backlight = step.backlight

        if self._can_set_backlight():
            self._step_info_widget.current_backlight = self._pause_backlight
        else:
            self._step_info_widget.current_backlight = None

        if self.is_paused:
            self._set_backlight(self._pause_backlight)
        else:
            self._set_backlight(step.backlight)

    def _can_set_backlight(self) -> bool:
        return (
            self._display is not None
            and self._display.mccs_monitor is not None
            and self._display.mccs_monitor.supports_vcp(
                MCCSCommand.BACKLIGHT_LEVEL_WHITE
            )
        )

    def _set_backlight(self, backlight: int) -> None:
        assert self._display is not None, "Display must be set before setting backlight"

        if self._display.mccs_monitor and self._can_set_backlight():
            # Clamp backlight value to be within [0, _backlight_max]
            backlight = max(0, min(self._backlight_max, backlight))
            self._display.mccs_monitor.backlight = backlight

    def eventFilter(self, watched: QObject, event: QEvent):
        if (
            event.type() == QKeyEvent.Type.KeyRelease
            and isinstance(event, QKeyEvent)
            and self.is_running
        ):
            if event.key() == Qt.Key.Key_Escape:
                self.stop()
                return True
            elif event.key() == Qt.Key.Key_I:
                if self._effect.opacity() == 0.0:
                    self._show_pause_widget(autohide=False)
                elif self._effect.opacity() == 1.0:
                    self._hide_pause_widget()
                return True
            elif event.key() == Qt.Key.Key_Space:
                if self.is_paused:
                    self.resume()
                else:
                    self.pause()
                return True
            elif event.key() == Qt.Key.Key_Right:
                self.next()
                return True
            elif event.key() == Qt.Key.Key_Left:
                self.previous()
                return True
            elif event.key() == Qt.Key.Key_Up:
                if self.is_paused:
                    self._pause_backlight = min(
                        self._backlight_max, self._pause_backlight + 1
                    )
                    self._update()
                    return True
            elif event.key() == Qt.Key.Key_Down:
                if self.is_paused:
                    self._pause_backlight = max(0, self._pause_backlight - 1)
                    self._update()
                    return True
        return super().eventFilter(watched, event)
