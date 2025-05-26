import json
import logging

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication, QNativeInterface
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
)

from app.mccs import get_monitors
from app.mccs.mccs import MCCSCommand
from app.mccs.vcp import VCPError
from app.mccs.vcp.windowsvcp import WindowsVCP
from app.testdatamodel import TestDataColumn, TestStep
from app.testdisplaymanager import TestDisplay, TestDisplayManager
from app.ui.ui_mainwindow import Ui_MainWindow
from app.utils import get_test_image

_last_used_file = "last_used.json"

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.testDataView.setColumnWidth(TestDataColumn.NAME_COLUMN, 100)
        self.ui.testDataView.setColumnWidth(TestDataColumn.IMAGE_COLUMN, 200)
        self.ui.testDataView.setColumnWidth(TestDataColumn.BACKLIGHT_COLUMN, 100)
        

        self._current_file: str | None = None
        self._test_displays: dict[str, TestDisplay] = {}
        self._test_manager: TestDisplayManager = TestDisplayManager(self)
        
        window_title = f"{QApplication.applicationDisplayName()} - {QApplication.applicationVersion()}[*]"
        self.setWindowTitle(window_title)
        self._load_settings()

        # Connect signals to slots
        self.ui.actionNew_Test.triggered.connect(self.on_new_test_triggered)
        self.ui.actionSave_Test.triggered.connect(self.on_save_test_triggered)
        self.ui.actionOpen_Test.triggered.connect(self.on_open_test_triggered)

        self.ui.actionStart_Test.triggered.connect(self.on_start_test_triggered)
        self.ui.actionStop_Test.triggered.connect(self.on_stop_test_triggered)
        self.ui.actionPause_Test.triggered.connect(self.on_pause_test_triggered)

        self.ui.addStepButton.clicked.connect(self.on_add_step_clicked)
        self.ui.removeStepButton.clicked.connect(self.on_remove_step_clicked)

        self.ui.displaysListWidget.currentRowChanged.connect(self._update_toolbar)
        self.ui.testDataView.currentRowChanged.connect(self.on_current_step_changed)
        self.ui.testDataView.stepDataChanged.connect(self.on_step_data_changed)

        self._test_manager.statusChanged.connect(self.on_test_manager_status_changed)
        self._test_manager.stepChanged.connect(self.on_test_manager_step_changed)

        screens = QGuiApplication.screens()
        monitors = get_monitors()

        for screen in screens:
            display = TestDisplay(pyside_screen=screen)
            self._test_displays[display.name] = display

            # Try to match the QScreen with the MCCS monitor
            iface = screen.nativeInterface()
            if isinstance(iface, QNativeInterface.QWindowsScreen):
                for monitor in monitors:
                    vcp = monitor.vcp
                    # This should always be true since iface is a WindowsScreen
                    # but it helps with type checking
                    if isinstance(vcp, WindowsVCP):
                        # Check if the MCCS monitor's handle matches the QScreen's handle
                        if vcp.hmonitor.value == iface.handle():
                            try:
                                # Try to get the capabilities of the monitor
                                # This can sometimes throw a VCP error if the monitor's
                                # capabilities string does not match the expected format
                                caps = monitor.capabilities
                                # Only set the monitor if we can get the capabilities
                                display.mccs_monitor = monitor
                            except VCPError as e:
                                logger.warning(f"Failed to get capabilities for monitor {display.name}")
                                logger.debug(e, exc_info=True)

        # Add the displays to the list widget
        for test_display in self._test_displays.values():
            name = test_display.name
            tooltip = ""

            if test_display.mccs_monitor is None:
                name += "*"
                tooltip = "Does not support software control"
            elif not test_display.mccs_monitor.supports_vcp(MCCSCommand.BACKLIGHT_LEVEL_WHITE):
                name += "*"
                tooltip = "Does not support backlight control"

            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, test_display.name)
            item.setToolTip(tooltip)
            self.ui.displaysListWidget.addItem(item)

        self._load_from_file(_last_used_file)
        self.on_current_step_changed()
        self._update_toolbar()

    @property
    def is_test_modified(self) -> bool:
        return self.isWindowModified()

    @property
    def selected_display(self) -> TestDisplay | None:
        selected_item = self.ui.displaysListWidget.currentItem()
        if selected_item is not None:
            display_id = selected_item.data(Qt.ItemDataRole.UserRole)
            return self._test_displays.get(display_id)

        return None

    @property
    def selected_test_step(self) -> TestStep | None:
        return self.ui.testDataView.currentStep()

    @property
    def is_testing(self) -> bool:
        return self._test_manager.is_running

    @property
    def is_paused(self) -> bool:
        return self._test_manager.is_paused

    @property
    def can_start_test(self) -> bool:
        return self.selected_display is not None and self.ui.testDataView.count()

    def on_new_test_triggered(self) -> None:
        if not self._request_save():
            return

        self.ui.testDataView.clear()
        self.ui.removeStepButton.setEnabled(False)
        # Clear the current test steps last
        self.ui.testDataView.clear()
        self._set_modified(False)
        self._current_file = None

        self._update_toolbar()

    def on_save_test_triggered(self) -> None:
        if self._current_file is None:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Save Test",
                "",
                "Dazzle Test Files (*.dzt)",
            )
        else:
            filename = self._current_file

        if filename:
            self._current_file = filename
            self._save_to_file(filename)
            self._set_modified(False)

    def on_open_test_triggered(self) -> None:
        if not self._request_save():
            return

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Test",
            "",
            "Dazzle Test Files (*.dzt)",
        )
        if filename:
            self._load_from_file(filename)
            self._current_file = filename
            self.setWindowModified(False)

    def on_add_step_clicked(self) -> None:
        
        image = ""
        backlight = 100
        current_step = self.ui.testDataView.currentStep()
        if current_step:
            image = current_step.image
            backlight = current_step.backlight

        row_index = self.ui.testDataView.count()
        step_num = row_index + 1
        step = self._add_step(f"Step {step_num}", image, backlight)
        self.ui.testDataView.setCurrentRow(row_index)

        self._update_toolbar()
        self._set_modified(True)

    def on_remove_step_clicked(self) -> None:
        row = self.ui.testDataView.currentRow()
        self.ui.testDataView.removeStep(row)

        if self.ui.testDataView.count() == 0:
            self.ui.removeStepButton.setEnabled(False)

        self._update_toolbar()
        self._set_modified(True)

    def on_current_step_changed(self) -> None:
        row = self.ui.testDataView.currentRow()
        if row >= 0:
            step = self.ui.testDataView.step(row)
            self._update_step_image()

            if self.is_testing:
                self._test_manager.current_index = row
        else:
            self.ui.imageLabel.clear()

    def on_step_data_changed(self, index: int) -> None:
        self._set_modified(True)
        if index == self.ui.testDataView.currentRow():
            self._update_step_image()

    def on_start_test_triggered(self) -> None:
        if self._test_manager.is_paused:
            self._test_manager.resume()
            return

        test_display = self.selected_display
        if test_display is None or not self.can_start_test:
            return

        self._test_manager.start(test_display, self.ui.testDataView.steps())

    def on_stop_test_triggered(self) -> None:
        self._test_manager.stop()

    def on_pause_test_triggered(self) -> None:
        self._test_manager.pause()

    def on_test_manager_status_changed(self) -> None:
        self._update_toolbar()

    def on_test_manager_step_changed(self, step: int) -> None:
        self.ui.testDataView.setCurrentRow(step)

    def _update_toolbar(self) -> None:
        self.ui.actionStart_Test.setVisible(not self.is_testing or self.is_paused)
        self.ui.actionPause_Test.setVisible(self.is_testing and not self.is_paused)

        self.ui.actionStart_Test.setEnabled(self.can_start_test)
        self.ui.actionPause_Test.setEnabled(self.is_testing and not self.is_paused)
        self.ui.actionStop_Test.setEnabled(self.is_testing)

    def _set_modified(self, modified: bool) -> None:
        if self._current_file is not None:
            self.setWindowModified(modified)

    def _request_save(self) -> bool:
        """Prompt the user to save the current test if it has been modified.
        If the user chooses to save, the test is saved and True is returned.
        If the user chooses not to save, the test is not saved and True is returned.
        If the user cancels, False is returned.
        """
        if self.is_test_modified:
            result = QMessageBox.question(
                self,
                "Save Test",
                "Do you want to save changes to the current test?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if result == QMessageBox.StandardButton.Cancel:
                return False

            if result == QMessageBox.StandardButton.Yes:
                self.on_save_test_triggered()

        return True
    
    def _filename_to_display_name(self, filename: str) -> str:
        """Convert a filename to a display name"""

        try:
            start_index = filename.index("_") + 1
        except ValueError:
            start_index = 0
        
        try:
            end_index = filename.index(".")
        except ValueError:
            end_index = len(filename)
        
        return filename[start_index : end_index]

    def _update_step_image(self) -> None:
        step = self.ui.testDataView.currentStep()
        if step is not None:
            pixmap = get_test_image(step.image)
            if pixmap:
                self.ui.imageLabel.setPixmap(pixmap)
            else:
                self.ui.imageLabel.clear()
                self.ui.imageLabel.setText(f"Image not found: {step.image}")
        else:
            self.ui.imageLabel.clear()

    def _add_step(self, name: str, image: str, backlight: int) -> TestStep :
        step = TestStep(
            name=name,
            image=image,
            backlight=backlight,
        )
        self.ui.testDataView.addStep(step)
        self.ui.removeStepButton.setEnabled(True)
        return step

    def _load_from_file(self, filename: str) -> None:
        try:
            with open(filename, "r") as file:
                data = json.load(file)
                self.ui.testDataView.clear()
                self.ui.removeStepButton.setEnabled(False)
                for step in data["steps"]:
                    self._add_step(step["name"], step["image"], step["backlight"])
        except FileNotFoundError:
            pass

    def _save_to_file(self, filename: str) -> None:
        steps = []
        for step in self.ui.testDataView.steps():
            steps.append(
                {
                    "name": step.name,
                    "image": step.image,
                    "backlight": step.backlight,
                }
            )

        data = {
            "version": QApplication.applicationVersion(),
            "display": self.selected_display.name if self.selected_display else None,
            "steps": steps,
        }

        with open(filename, "w") as file:
            json.dump(data, file, indent=4)

    def _load_settings(self) -> None:
        settings = QSettings()
        self.restoreGeometry(settings.value("geometry"))
        self.restoreState(settings.value("state"))

        # Restore column widths
        width = settings.value("step_num_width")
        if width:
            self.ui.testDataView.setColumnWidth(TestDataColumn.STEP_NUM_COLUMN, width)

        width = settings.value("step_name_width")
        if width:
            self.ui.testDataView.setColumnWidth(TestDataColumn.NAME_COLUMN, width)

        width = settings.value("step_image_width")
        if width:
            self.ui.testDataView.setColumnWidth(TestDataColumn.IMAGE_COLUMN, width)

        width = settings.value("step_backlight_width")
        if width:
            self.ui.testDataView.setColumnWidth(TestDataColumn.BACKLIGHT_COLUMN, width)

    def _save_settings(self) -> None:
        settings = QSettings()
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())
        settings.setValue("step_num_width", self.ui.testDataView.columnWidth(TestDataColumn.STEP_NUM_COLUMN))
        settings.setValue("step_name_width", self.ui.testDataView.columnWidth(TestDataColumn.NAME_COLUMN))
        settings.setValue("step_image_width", self.ui.testDataView.columnWidth(TestDataColumn.IMAGE_COLUMN))
        settings.setValue("step_backlight_width", self.ui.testDataView.columnWidth(TestDataColumn.BACKLIGHT_COLUMN))

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._request_save():
            event.ignore()
            return
        
        # If the user already had a file open we don't need to
        # save this data. Instead, let's clear everything
        # and save a blank test.
        if self._current_file is not None:
            self.ui.testDataView.clear()

        self._save_to_file(_last_used_file)
        
        self._test_manager.stop()
        self._save_settings()
            
        return super().closeEvent(event)
