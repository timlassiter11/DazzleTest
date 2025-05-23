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
    name: str
    screen: QScreen
    vcp: Monitor | None = None
    capabilities: Capabilities | None = None


class TestDisplayManager(QObject):
    statusChanged: Signal = Signal()
    stepChanged: Signal = Signal(int)

    _widget: QWidget
    _current_index: int = 0

    # This should get updated when we pass a display to start the test
    # Just use some sane default value.
    _backlight_max: int = 100
    _starting_backlight: int = _backlight_max
    _pause_backlight: int = _backlight_max
    
    _is_paused: bool = False

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent=parent)

        self._current_index = 0
        self._display: TestDisplay | None = None
        self._steps: list[TestStep] = []

        self._widget = QWidget()
        self._widget.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        layout = QVBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._image_label = QLabel(self._widget)
        self._image_label.setMinimumSize(1, 1)
        self._image_label.setScaledContents(True)
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._image_label)

        self._pause_label = QLabel(self._widget)
        self._pause_label.setWindowFlags(Qt.WindowType.SplashScreen)
        self._pause_label.setText("Paused")

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
        self._current_index = 0
        self._display = display
        self._steps = steps
        self._is_paused = False

        if display.vcp:
            #TODO: Check to make sure the display supports backlight functions
            with display.vcp:
                self._starting_backlight = display.vcp.backlight
                self._backlight_max = display.vcp.backlight_maximum
                self._pause_backlight = self._backlight_max
        
        self._widget.setScreen(display.screen)
        self._widget.setGeometry(display.screen.geometry())
        self._pause_label.setScreen(display.screen)

        self._update()
        self._widget.showFullScreen()
        self.statusChanged.emit()

    def stop(self) -> None:
        self._widget.hide()
        self._pause_label.hide()
        self._is_paused = False
        self.statusChanged.emit()
        self._set_backlight(self._starting_backlight)

    def pause(self) -> None:
        self._is_paused = True
        self._update()
        self.statusChanged.emit()

    def resume(self) -> None:
        self._is_paused = False
        self._update()
        self.statusChanged.emit()

    def next(self) -> None:
        if self._current_index < len(self._steps) - 1:
            self._current_index += 1
            self._is_paused = False
            self._update()
            self.stepChanged.emit(self._current_index)

    def previous(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._is_paused = False
            self._update()
            self.stepChanged.emit(self._current_index)

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

        self._pause_label.setText(f"{step.name}\nImage: {step.image}\nBacklight: {step.backlight}")

        if self.is_paused:
            self._set_backlight(self._pause_backlight)
            self._pause_label.show()

            c = self._widget.geometry().center()
            s = self._pause_label.size()
            self._pause_label.move(c.x() - s.width() // 2, c.y() - s.height() // 2)
        else:
            self._set_backlight(step.backlight)
            self._pause_label.hide()

    def _set_backlight(self, backlight: int) -> None:
        if self._display and self._display.vcp is not None:
            backlight = min(self._backlight_max, backlight)
            with self._display.vcp:
                self._display.vcp.backlight = backlight

    def eventFilter(self, watched, event):
        if (
            event.type() == QKeyEvent.Type.KeyRelease
            and isinstance(event, QKeyEvent)
            and self.is_running
        ):
            if event.key() == Qt.Key_Escape:
                self.stop()
                return True
            elif event.key() == Qt.Key_Space:
                if self.is_paused:
                    self.resume()
                else:
                    self.pause()
                return True
            elif event.key() == Qt.Key_Right:
                self.next()
                return True
            elif event.key() == Qt.Key_Left:
                self.previous()
                return True
            elif event.key() == Qt.Key_Up:
                if self.is_paused:
                    self._pause_backlight += 1
                    self._update()
                    return True
            elif event.key() == Qt.Key_Down:
                if self.is_paused:
                    self._pause_backlight -= 1
                    self._update()
                    return True
        return super().eventFilter(watched, event)
