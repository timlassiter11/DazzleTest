import sys

try:
    from ._version import version as VERSION
except ImportError:
    from setuptools_scm import get_version

    VERSION = get_version()


# TODO: Update application information
APP_NAME = "DazzleTest"
APP_DESCRIPTION = "Utility for testing display brightness"
APP_AUTHOR = "Timothy Lassiter"
DOMAIN_NAME = "tlassiter"
ORGANIZATION_NAME = "tlassiter"

TEST_IMAGES_DIR = "./test_images"

def run():
    import locale

    from PySide6.QtCore import QCommandLineParser
    from PySide6.QtWidgets import QApplication

    from app.widgets.mainwindow import MainWindow

    # Handle all uncaught exceptions
    sys.excepthook = _exception_hook

    locale.setlocale(locale.LC_ALL, "")

    QApplication.setOrganizationName(ORGANIZATION_NAME)
    QApplication.setOrganizationDomain(DOMAIN_NAME)
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationVersion(VERSION)

    app = QApplication(sys.argv)

    parser = QCommandLineParser()
    parser.setApplicationDescription(APP_DESCRIPTION)
    parser.addHelpOption()
    parser.addVersionOption()

    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())


def _exception_hook(exc_type, exc_value, exc_traceback):
    import logging
    logger = logging.getLogger(APP_NAME)

    if issubclass(exc_type, KeyboardInterrupt):
        # ignore keyboard interrupt to support console applications
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    else:
        exc_info = (exc_type, exc_value, exc_traceback)
        logger.exception(f"Uncaught exception", exc_info=exc_info)