from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from app.ui.ui_stepinfowidget import Ui_StepInfoWidget


class StepInfoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_StepInfoWidget()
        self.ui.setupUi(self)

        self.ui.gridLayout.addLayout(self.ui.stepNumberLayout, 0, 0, Qt.AlignmentFlag.AlignRight)

    @property
    def current_step(self) -> int:
        return int(self.ui.currentStepLabel.text())
    
    @current_step.setter
    def current_step(self, number: int):
        self.ui.currentStepLabel.setText(str(number))

    @property
    def total_steps(self) -> int:
        return int(self.ui.totalStepLabel.text())
    
    @total_steps.setter
    def total_steps(self, total: int):
        self.ui.totalStepLabel.setText(str(total))

    @property
    def title(self) -> str:
        return self.ui.titleLabel.text()

    @title.setter
    def title(self, name: str):
        self.ui.titleLabel.setText(name)

    @property
    def image_name(self) -> str:
        return self.ui.imageValueLabel.text()

    @image_name.setter
    def image_name(self, image: str):
        self.ui.imageValueLabel.setText(image)
        
    @property
    def step_backlight(self) -> int:
        return int(self.ui.stepBacklightValueLabel.text())

    @step_backlight.setter
    def step_backlight(self, backlight: int):
        self.ui.stepBacklightValueLabel.setText(str(backlight))

    @property
    def current_backlight(self) -> int | None:
        if self.ui.currentBacklightValueLabel.isvisible():
            return int(self.ui.currentBacklightValueLabel.text())
        return None
    
    @current_backlight.setter
    def current_backlight(self, backlight: int | None):
        if backlight is None:
            self.ui.currentBacklightValueLabel.setText("")
            self.ui.currentBacklightValueLabel.hide()
            self.ui.currentBacklightLabel.hide()
        else:
            self.ui.currentBacklightLabel.show()
            self.ui.currentBacklightValueLabel.show()
            self.ui.currentBacklightValueLabel.setText(str(backlight))
