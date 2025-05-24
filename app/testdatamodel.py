"""
Defines the data model for managing test steps in the DazzleTest application.

This module includes:
- `TestDataColumn`: An enumeration for the columns in the test data table.
- `TestStep`: A dataclass representing a single step in a test sequence.
- `TestDataTableModel`: A QAbstractTableModel subclass that provides the data
  and handling logic for displaying and editing test steps in a table view.
"""
from dataclasses import dataclass
from enum import IntEnum

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)

from app.utils import test_image_filename_to_display_name

# Type alias for model index types, used for clarity in method signatures
_ParentIndexType = QModelIndex | QPersistentModelIndex

class TestDataColumn(IntEnum):
    """Enumerates the columns in the test data table view."""
    STEP_NUM_COLUMN = 0  #: Column for the step number.
    NAME_COLUMN = 1      #: Column for the test step name.
    IMAGE_COLUMN = 2     #: Column for the test image filename.
    BACKLIGHT_COLUMN = 3 #: Column for the backlight percentage.


@dataclass
class TestStep:
    """
    Represents a single step in a display test sequence.

    Attributes:
        name (str): The name of the test step.
        image (str): The filename of the image to be displayed for this step.
        backlight (int): The backlight percentage to be set for this step (0-100).
    """
    name: str
    image: str
    backlight: int


class TestDataTableModel(QAbstractTableModel):
    """
    A Qt Table Model for managing and displaying test steps.

    This model interfaces with a list of `TestStep` objects and provides
    the necessary methods for Qt's model/view framework to display and
    manipulate this data in a QTableView.
    """
    def __init__(self, data: list[TestStep], /, parent: QObject | None = None):
        """
        Initializes the TestDataTableModel.

        Args:
            data: A list of `TestStep` objects that this model will manage.
            parent: The parent QObject, if any.
        """
        super().__init__(parent)
        self._data: list[TestStep] = data

    def addStep(self, step: TestStep):
        """
        Adds a new test step to the end of the model.

        Args:
            step: The `TestStep` object to add.
        """
        # Notify views that rows are about to be inserted
        self.beginInsertRows(QModelIndex(), len(self._data), len(self._data))
        self._data.append(step)
        # Notify views that rows have been inserted
        self.endInsertRows()

    def removeStep(self, index: int):
        """
        Removes a test step from the model at the given index.

        Args:
            index: The row index of the step to remove.
        """
        if 0 <= index < len(self._data):
            # Notify views that rows are about to be removed
            self.beginRemoveRows(QModelIndex(), index, index)
            del self._data[index]
            # Notify views that rows have been removed
            self.endRemoveRows()

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        """
        Returns the data for the given header role and section.

        Args:
            section: The column index (for horizontal headers).
            orientation: The orientation of the header (Horizontal or Vertical).
            role: The data role being requested (e.g., DisplayRole).

        Returns:
            The header string if the role and orientation are supported, otherwise None.
        """
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
        return None # Default case for unsupported roles or orientations

    def rowCount(self, parent: _ParentIndexType | None = None) -> int:
        """
        Returns the number of rows in the model.

        Args:
            parent: The parent model index (unused in flat models).

        Returns:
            The total number of test steps.
        """
        return len(self._data)

    def columnCount(self, parent: _ParentIndexType | None = None) -> int:
        """
        Returns the number of columns in the model.

        Args:
            parent: The parent model index (unused in flat models).

        Returns:
            The fixed number of columns (4).
        """
        return 4 # Corresponds to the number of items in TestDataColumn

    def data(self, index: _ParentIndexType, role: int = Qt.ItemDataRole.DisplayRole) -> str | int | None:
        """
        Returns the data stored under the given role for the item at the specified index.

        Args:
            index: The model index of the item.
            role: The data role being requested (e.g., DisplayRole, EditRole).

        Returns:
            The data for the item, or None if the index is invalid or role not supported.
        """
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None

        current_step = self._data[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == TestDataColumn.STEP_NUM_COLUMN:
                return index.row() + 1 # Display 1-based step number
            elif index.column() == TestDataColumn.NAME_COLUMN:
                return current_step.name
            elif index.column() == TestDataColumn.IMAGE_COLUMN:
                # For display, convert filename to a more readable name
                return test_image_filename_to_display_name(current_step.image)
            elif index.column() == TestDataColumn.BACKLIGHT_COLUMN:
                return current_step.backlight
        elif role == Qt.ItemDataRole.EditRole: # Data for editing
            if index.column() == TestDataColumn.NAME_COLUMN:
                return current_step.name
            elif index.column() == TestDataColumn.IMAGE_COLUMN:
                # For editing, return the raw filename
                return current_step.image
            elif index.column() == TestDataColumn.BACKLIGHT_COLUMN:
                return current_step.backlight
        return None # Default for other roles

    def setData(self, index: _ParentIndexType, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        """
        Sets the role data for the item at index to value.

        Args:
            index: The model index of the item to modify.
            value: The new value for the item.
            role: The data role to set (typically EditRole).

        Returns:
            True if setting the data was successful, False otherwise.
        """
        changed = False
        if index.isValid() and 0 <= index.row() < len(self._data):
            if role == Qt.ItemDataRole.EditRole:
                current_step = self._data[index.row()]
                if index.column() == TestDataColumn.NAME_COLUMN:
                    if current_step.name != str(value):
                        current_step.name = str(value)
                        changed = True
                elif index.column() == TestDataColumn.IMAGE_COLUMN:
                    if current_step.image != str(value):
                        current_step.image = str(value)
                        changed = True
                elif index.column() == TestDataColumn.BACKLIGHT_COLUMN:
                    try:
                        backlight_val = int(value)
                        if 0 <= backlight_val <= 100: # Basic validation
                            if current_step.backlight != backlight_val:
                                current_step.backlight = backlight_val
                                changed = True
                        else:
                            # Handle invalid backlight value (e.g., log, notify user)
                            print(f"Warning: Invalid backlight value '{value}' provided.")
                            return False
                    except ValueError:
                        print(f"Warning: Could not convert backlight value '{value}' to int.")
                        return False # Value could not be converted

                if changed:
                    # Notify views that the data has changed
                    self.dataChanged.emit(index, index, [role]) # Specify role for more granular updates
        return changed

    def step(self, index: int) -> TestStep | None:
        """
        Retrieves the TestStep object at the given row index.

        Args:
            index: The row index.

        Returns:
            The `TestStep` object at the specified index, or None if index is out of bounds.
        """
        if 0 <= index < len(self._data):
            return self._data[index]
        return None

    def steps(self) -> list[TestStep]:
        """
        Returns the entire list of TestStep objects managed by the model.

        Returns:
            A list of all `TestStep` objects.
        """
        return self._data

    def clear(self):
        """
        Removes all test steps from the model.
        """
        # Notify views that the model is about to be reset
        self.beginResetModel()
        self._data.clear()
        # Notify views that the model has been reset
        self.endResetModel()

    def flags(self, index: _ParentIndexType) -> Qt.ItemFlags:
        """
        Returns the item flags for the given index.

        This determines properties like whether an item is selectable, enabled, or editable.

        Args:
            index: The model index of the item.

        Returns:
            The Qt.ItemFlags for the item.
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags # Default for invalid index

        # All items are selectable, enabled, and editable.
        # Step number column could be made non-editable if desired.
        base_flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        if index.column() != TestDataColumn.STEP_NUM_COLUMN: # Make step number not editable
            base_flags |= Qt.ItemFlag.ItemIsEditable
        return base_flags

