from PySide6.QtCore import QModelIndex, Qt, Signal, QPersistentModelIndex, QAbstractItemModel
from PySide6.QtWidgets import QComboBox, QSpinBox, QStyledItemDelegate, QTableView, QWidget, QStyleOptionViewItem, QHeaderView

from app.testdatamodel import TestDataColumn, TestDataTableModel, TestStep
from app.utils import get_test_images, test_image_filename_to_display_name

class TestDataEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex):
        if index.column() == TestDataColumn.IMAGE_COLUMN: 
            cb = QComboBox(parent)
            for filename in get_test_images():
                display_name = test_image_filename_to_display_name(filename)
                cb.addItem(display_name, filename)
                cb.currentIndexChanged.connect(lambda: cb.clearFocus())
            return cb
        elif index.column() == TestDataColumn.BACKLIGHT_COLUMN:
            sb = QSpinBox(parent)
            sb.setMinimum(0)
            sb.setMaximum(255)
            return sb
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor: QWidget, index: QModelIndex | QPersistentModelIndex):
        if index.column() == TestDataColumn.IMAGE_COLUMN:
            value = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        else:
            value = index.model().data(index, Qt.ItemDataRole.EditRole)

        if isinstance(editor, QComboBox):
            editor.setCurrentText(str(value))
        elif isinstance(editor, QSpinBox):

            editor.setValue(int(value))
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex | QPersistentModelIndex):
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentData(), Qt.ItemDataRole.EditRole)
        elif isinstance(editor, QSpinBox):
            model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)


class TestDataView(QTableView):
    currentRowChanged = Signal(int)
    currentRowDataChanged = Signal()
    stepDataChanged = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = TestDataTableModel([], self)
        self.setModel(self._model)
        self.selectionModel().currentRowChanged.connect(self._on_current_row_changed)
        self.setItemDelegate(TestDataEditDelegate(self))
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)

    def model(self) -> TestDataTableModel:
        return self._model

    def addStep(self, step: TestStep) -> None:
        self._model.addStep(step)

    def removeStep(self, row: int) -> None:
        self._model.removeStep(row)

    def currentRow(self) -> int:
        if self.currentIndex().isValid():
            return self.currentIndex().row()
        return -1

    def currentStep(self) -> TestStep | None:
        current_row = self.currentRow()
        if current_row >= 0:
            return self._model.step(current_row)
        return None

    def clear(self) -> None:
        self._model.clear()

    def count(self) -> int:
        return self._model.rowCount()
    
    def step(self, row: int) -> TestStep:
        return self._model.step(row)
    
    def steps(self) -> list[TestStep]:
        return self._model.steps()

    def setCurrentRow(self, row: int) -> None:
        self.setCurrentIndex(self._model.index(row, 0))

    def _on_current_row_changed(self, current: QModelIndex, previous: QModelIndex):
        self.currentRowChanged.emit(current.row())

    def dataChanged(self, topLeft: QModelIndex | QPersistentModelIndex, bottomRight: QModelIndex | QPersistentModelIndex, /, roles = ...):
        start = topLeft.row()
        end = bottomRight.row()
        for row in range(start, end + 1):
            self.stepDataChanged.emit(row)

        return super().dataChanged(topLeft, bottomRight, roles)
        