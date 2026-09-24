"""
Centralized logging configuration for Imervue.

Call ``setup_logging()`` once at startup (before any other import that uses
``logging.getLogger``).  In frozen (PyInstaller / Nuitka) builds the log file
is written next to the .exe; in development it goes to the project root. When
that directory is not writable — an EXE installed under ``Program Files`` —
the log falls back to the per-user data directory.

``install_exception_logging()`` routes unhandled exceptions through the same
log, which is the only trace a windowed frozen build leaves behind.
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

_LOG_FILENAME = "imervue.log"
_FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _user_log_dir() -> Path:
    """Per-user fallback directory, used when the app directory is read-only."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue"
    return Path.home() / ".cache" / "imervue"


def _file_handler(directory: Path) -> logging.FileHandler:
    """Open a fresh (mode ``w``) log file handler under *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(str(directory / _LOG_FILENAME), mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    return handler


def setup_logging() -> None:
    """Configure the root ``Imervue`` logger to write to a file (+ stderr in dev).

    Safe to call more than once: a second call with a file handler already
    attached returns without adding duplicates.
    """
    from Imervue.system.app_paths import app_dir, is_frozen

    root_logger = logging.getLogger("Imervue")
    if any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        return

    try:
        handler = _file_handler(app_dir())
    except OSError:
        handler = _file_handler(_user_log_dir())

    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    # Also log to stderr when a console is available. A windowed frozen build
    # has no stderr, and writing to it raises on every record.
    if not is_frozen():
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        root_logger.addHandler(console)

    root_logger.info("Logging initialized — log file: %s", handler.baseFilename)


def install_exception_logging() -> None:
    """Log unhandled exceptions to the ``Imervue`` logger before the app dies."""
    logger = logging.getLogger("Imervue")
    previous = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb) -> None:
        logger.critical(
            "Unhandled exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook
