"""
Main application package for DazzleTest.

This package initializes the application, sets up global configurations,
and defines the main entry point `run()`. It also handles version information
and application-specific constants.
"""
import sys

# Version handling:
# Tries to import the version from _version.py (populated by setuptools_scm during build)
# Falls back to dynamically getting the version using setuptools_scm if not found (e.g., in development)
try:
    from ._version import version as VERSION
except ImportError:
    from setuptools_scm import get_version
    # Get version dynamically if not in a packaged environment
    VERSION = get_version()


# Application constants
# TODO: Update application information if necessary
APP_NAME = "DazzleTest"
APP_DESCRIPTION = "Utility for testing display brightness"
APP_AUTHOR = "Timothy Lassiter"
DOMAIN_NAME = "tlassiter"  # Used for Qt settings, typically a reverse domain name
ORGANIZATION_NAME = "tlassiter" # Used for Qt settings

TEST_IMAGES_DIR = "./test_images" # Directory for test images

def run():
    """
    Initializes and runs the DazzleTest Qt application.

    This function sets up the application environment, parses command-line
    arguments, creates the main window, and starts the Qt event loop.
    """
    import locale

    from PySide6.QtCore import QCommandLineParser
    from PySide6.QtWidgets import QApplication

    from app.widgets.mainwindow import MainWindow

    # Handle all uncaught exceptions
    # Set the global exception hook for logging uncaught exceptions
    sys.excepthook = _exception_hook

    # Set the locale to the user's default settings
    locale.setlocale(locale.LC_ALL, "")

    # Configure QApplication metadata (used for settings, etc.)
    QApplication.setOrganizationName(ORGANIZATION_NAME)
    QApplication.setOrganizationDomain(DOMAIN_NAME)
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationVersion(VERSION)

    # Create the QApplication instance
    app = QApplication(sys.argv)

    # Setup command line argument parser
    parser = QCommandLineParser()
    parser.setApplicationDescription(APP_DESCRIPTION)
    parser.addHelpOption()    # Adds -h, --help
    parser.addVersionOption() # Adds -v, --version

    # Create and show the main application window
    widget = MainWindow()
    widget.show()

    # Start the Qt event loop and exit when it finishes
    sys.exit(app.exec())


def _exception_hook(exc_type, exc_value, exc_traceback):
    """
    Global exception hook to log uncaught exceptions.

    This function is set as `sys.excepthook` to catch any exceptions
    not handled within the application. It logs the exception information
    using the application's logger, except for KeyboardInterrupt, which
    is ignored to allow normal console application termination.

    Args:
        exc_type: The type of the exception.
        exc_value: The exception instance.
        exc_traceback: A traceback object encapsulating the call stack at the
                       point where the exception originally occurred.
    """
    import logging
    logger = logging.getLogger(APP_NAME) # Get the application's logger

    if issubclass(exc_type, KeyboardInterrupt):
        # For KeyboardInterrupt, fall back to the default Python excepthook
        # This allows Ctrl+C to terminate the application as expected.
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    else:
        # Log other uncaught exceptions with full traceback information
        exc_info = (exc_type, exc_value, exc_traceback)
        logger.critical(f"Uncaught exception: {exc_value}", exc_info=exc_info)