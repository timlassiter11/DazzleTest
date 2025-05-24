"""
Utility functions and classes for the DazzleTest application.

This module provides helper functions for:
- Converting image filenames to display names.
- Listing and loading test images from the designated directory.
- A context manager (`SignalBlocker`) to temporarily block signals of QObjects.
"""
from PySide6.QtCore import QDir, QObject
from PySide6.QtGui import QPixmap

from app import TEST_IMAGES_DIR # Application constant for test images directory

def test_image_filename_to_display_name(filename: str) -> str:
    """
    Converts a test image filename to a more human-readable display name.

    Assumes filenames might have a prefix (e.g., "prefix_actualname.png")
    and an extension. This function tries to extract "actualname".
    If "_" is not found, it uses the part before the extension.
    If "." is not found, it uses the whole filename.

    Args:
        filename: The original filename (e.g., "01_grayscale_ramp.png").

    Returns:
        A cleaned-up name for display (e.g., "grayscale_ramp").
    """
    try:
        # Find the first underscore, start after it
        start_index = filename.index("_") + 1
    except ValueError:
        # No underscore found, start from the beginning of the filename
        start_index = 0

    try:
        # Find the first dot (extension separator), end before it
        end_index = filename.index(".")
    except ValueError:
        # No dot found, use the rest of the filename
        end_index = len(filename)

    return filename[start_index:end_index]


def get_test_images() -> list[str]:
    """
    Retrieves a sorted list of test image filenames from the `TEST_IMAGES_DIR`.

    Filters for "*.png" files and sorts them by name.

    Returns:
        A list of string filenames, or an empty list if the directory
        doesn't exist or contains no matching images.
    """
    image_dir = QDir(TEST_IMAGES_DIR)
    if image_dir.exists():
        image_dir.setNameFilters(["*.png"]) # Filter for PNG files
        # Filter for files only, excluding "." and ".."
        image_dir.setFilter(QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        image_dir.setSorting(QDir.SortFlag.Name) # Sort by filename
        return image_dir.entryList()
    return [] # Return empty list if directory doesn't exist


def get_test_image(image_name: str) -> QPixmap | None:
    """
    Loads a QPixmap from the specified image name within `TEST_IMAGES_DIR`.

    Args:
        image_name: The filename of the image (e.g., "image.png").

    Returns:
        A QPixmap object if the image is successfully loaded, otherwise None.
    """
    pixmap = QPixmap()
    # Construct the full path to the image
    image_path = f"{TEST_IMAGES_DIR}/{image_name}"
    if pixmap.load(image_path):
        return pixmap
    # Optionally, log a warning if image loading fails
    # print(f"Warning: Could not load image '{image_path}'")
    return None


class SignalBlocker:
    """
    A context manager to temporarily block signals for one or more QObjects.

    This is useful when performing batch updates on QObject properties to prevent
    excessive signal emissions or to avoid triggering slots prematurely.

    Example:
        with SignalBlocker(my_qobject):
            my_qobject.setValue(10) # Signals for setValue are blocked
            my_qobject.setText("hello") # Signals for setText are blocked
        # Signals are automatically unblocked upon exiting the 'with' block.
    """

    def __init__(self, objects: QObject | list[QObject]):
        """
        Initializes the SignalBlocker.

        Args:
            objects: A single QObject or a list of QObjects whose signals
                     are to be blocked.
        """
        if isinstance(objects, QObject):
            # If a single object is passed, wrap it in a list
            self._objects: list[QObject] = [objects]
        else:
            self._objects: list[QObject] = objects

    def __enter__(self):
        """
        Enters the context, blocking signals for all specified QObjects.
        """
        for obj in self._objects:
            obj.blockSignals(True) # Block signals for each object
        return self # Return self to allow use with 'as' keyword, though not typical for this class

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exits the context, unblocking signals for all specified QObjects.

        Args:
            exc_type: The type of exception that occurred (if any).
            exc_val: The exception instance (if any).
            exc_tb: The traceback object (if any).

        Returns:
            False, to indicate that any exceptions should not be suppressed by this context manager.
        """
        for obj in self._objects:
            obj.blockSignals(False) # Unblock signals for each object
        return False # Do not suppress any exceptions that occurred within the 'with' block
