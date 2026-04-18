"""
Centralized logging configuration for Imervue.

Call ``setup_logging()`` once at startup (before any other import that uses
``logging.getLogger``).  In frozen (PyInstaller) builds the log file is
written next to the .exe; in development it goes to the project root.
"""
from __future__ import annotations

import logging
import sys


def setup_logging() -> None:
    """Configure the root ``Imervue`` logger to write to a file + stderr."""
    from Imervue.system.app_paths import app_dir

    log_path = app_dir() / "imervue.log"

    # Rotate: keep only the last run (overwrite)
    handler = logging.FileHandler(str(log_path), mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root_logger = logging.getLogger("Imervue")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    # Also log to stderr when a console is available
    if not getattr(sys, "frozen", False):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(
            "[%(levelname)s] %(name)s: %(message)s"
        ))
        root_logger.addHandler(console)

    root_logger.info("Logging initialized — log file: %s", log_path)
