import os
import sys
import logging
from logging.handlers import RotatingFileHandler

from app import APP_NAME, run


if hasattr(sys, "frozen"):
    exe = sys.executable
else:
    exe = sys.argv[0]

dir = os.path.dirname(exe)
log_file = os.path.join(dir, f"{APP_NAME}.log")

handler = RotatingFileHandler(log_file, maxBytes=100_000_000, backupCount=2)
logging.basicConfig(level=logging.WARN, handlers=[handler])

run()
