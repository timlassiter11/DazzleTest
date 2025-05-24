"""
Application entry point.

This module is executed when the application is run as a package (e.g., `python -m app`).
It imports and calls the `run()` function from the main `app` package,
which initializes and starts the DazzleTest application.
"""
from . import run

# Execute the main run function to start the application
run()
