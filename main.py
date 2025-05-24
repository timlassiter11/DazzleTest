"""
Main entry point for the DazzleTest application.

This script initializes basic configurations, primarily logging, and then
delegates to the `run()` function within the `app` package to start the
actual application logic and user interface.
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Import application-specific constants and the main run function
from app import APP_NAME, run


# Determine the base directory for the application.
# This is important for locating resources like log files, especially when
# the application is run as a frozen executable (e.g., created by PyInstaller).
if hasattr(sys, "frozen"):
    # If 'sys.frozen' attribute exists, it means the application is running in a bundled environment.
    # sys.executable points to the executable itself.
    exe_path = sys.executable
else:
    # Otherwise, it's likely running from a script, so sys.argv[0] is the script path.
    exe_path = sys.argv[0]

# Get the directory containing the executable or script.
app_dir = os.path.dirname(exe_path)

# Define the path for the application log file, placing it in the same directory as the executable/script.
log_file_path = os.path.join(app_dir, f"{APP_NAME}.log")

# Configure logging with a RotatingFileHandler.
# This handler will create log files that rotate when they reach a certain size.
# - maxBytes: The maximum size of a log file before it's rotated (100MB here).
# - backupCount: The number of old log files to keep (2 here).
log_handler = RotatingFileHandler(log_file_path, maxBytes=100_000_000, backupCount=2)

# Set up basic logging configuration:
# - level: The minimum severity level of messages to log (WARNING here).
# - handlers: A list of logging handlers to use (just our rotating file handler).
logging.basicConfig(level=logging.WARNING, handlers=[log_handler])

# Call the main run function from the app package to start the application.
# This typically initializes the Qt application, main window, etc.
run()
