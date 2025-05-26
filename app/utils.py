from PySide6.QtCore import QDir, QObject
from PySide6.QtGui import QPixmap

from app import TEST_IMAGES_DIR

def file_to_display_name(filename: str) -> str:
    """Convert a filename to a display name"""
    try:
        start_index = filename.index("_") + 1
    except ValueError:
        start_index = 0

    try:
        end_index = filename.index(".")
    except ValueError:
        end_index = len(filename)

    return filename[start_index:end_index]


def get_test_images() -> list[str]:
    """
    Get the list of test images from the resource directory.

    Returns:
        list[str]: A list of image file names.
    """
    dir = QDir(TEST_IMAGES_DIR)
    if dir.exists():
        dir.setNameFilters(["*.png"])
        dir.setFilter(QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        dir.setSorting(QDir.SortFlag.Name)
        return dir.entryList()
    return []


def get_test_image(image_name: str) -> QPixmap | None:
    """
    Get the test image from the resource directory.

    Args:
        image_name (str): The name of the image file.

    Returns:
        QPixmap: The QPixmap object representing the image.
    """
    pixmap = QPixmap()
    if pixmap.load(f"{TEST_IMAGES_DIR}/{image_name}"):
        return pixmap
    return None


class SignalBlocker:
    """
    A context manager to temporarily block signals for a QObject.

    Args:
        obj (QObject): The QObject whose signals should be blocked.
    """

    def __init__(self, objects: QObject | list[QObject]):
        if isinstance(objects, QObject):
            objects = [objects]

        self._objects: list[QObject] = objects

    def __enter__(self):
        for obj in self._objects:
            obj.blockSignals(True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for obj in self._objects:
            obj.blockSignals(False)
        return False
