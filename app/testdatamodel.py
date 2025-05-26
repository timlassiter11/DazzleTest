from dataclasses import dataclass
from enum import IntEnum

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)

from app.utils import file_to_display_name

_ParentIndexType = QModelIndex | QPersistentModelIndex

class TestDataColumn(IntEnum):
    STEP_NUM_COLUMN = 0
    NAME_COLUMN = 1
    IMAGE_COLUMN = 2
    BACKLIGHT_COLUMN = 3


@dataclass
class TestStep:
    name: str
    image: str
    backlight: int


class TestDataTableModel(QAbstractTableModel):
    def __init__(self, data: list[TestStep], /, parent: QObject | None = None):
        super().__init__(parent)
        self._data = data

    def addStep(self, step: TestStep):
        self.beginInsertRows(QModelIndex(), len(self._data), len(self._data))
        self._data.append(step)
        self.endInsertRows()

    def removeStep(self, index: int):
        self.beginRemoveRows(QModelIndex(), index, index)
        del self._data[index]
        self.endRemoveRows()

    def headerData(self, section, orientation, /, role=...):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section == TestDataColumn.STEP_NUM_COLUMN:
                    return "Step"
                elif section == TestDataColumn.NAME_COLUMN:
                    return "Name"
                elif section == TestDataColumn.IMAGE_COLUMN:
                    return "Image"
                elif section == TestDataColumn.BACKLIGHT_COLUMN:
                    return "Backlight"
        return None

    def rowCount(self, parent: _ParentIndexType | None = None) -> int:
        return len(self._data)

    def columnCount(self, /, parent: _ParentIndexType | None = None) -> int:
        return 4

    def data(self, index: _ParentIndexType, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._data):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == TestDataColumn.STEP_NUM_COLUMN:
                return index.row() + 1
            elif index.column() == TestDataColumn.NAME_COLUMN:
                return self._data[index.row()].name
            elif index.column() == TestDataColumn.IMAGE_COLUMN:
                return file_to_display_name(self._data[index.row()].image)
            elif index.column() == TestDataColumn.BACKLIGHT_COLUMN:
                return self._data[index.row()].backlight
        elif role == Qt.ItemDataRole.EditRole:
            if index.column() == TestDataColumn.NAME_COLUMN:
                return self._data[index.row()].name
            elif index.column() == TestDataColumn.IMAGE_COLUMN:
                return self._data[index.row()].image
            elif index.column() == TestDataColumn.BACKLIGHT_COLUMN:
                return self._data[index.row()].backlight
            
    def setData(self, index: _ParentIndexType, value, /, role = ...):
        changed = False
        if index.isValid() and index.row() < len(self._data):
            if role == Qt.ItemDataRole.EditRole:
                if index.column() == TestDataColumn.NAME_COLUMN:
                    self._data[index.row()].name = value
                    changed = True
                elif index.column() == TestDataColumn.IMAGE_COLUMN:
                    self._data[index.row()].image = value
                    changed = True
                elif index.column() == TestDataColumn.BACKLIGHT_COLUMN:
                    self._data[index.row()].backlight = value
                    changed = True

                if changed:
                    self.dataChanged.emit(index, index)
        return changed
        
    
    def step(self, index: int):
        return self._data[index]
    
    def steps(self):
        return self._data
    
    def clear(self):
        self.beginResetModel()
        self._data.clear()
        self.endResetModel()

    def flags(self, index):
         return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable

