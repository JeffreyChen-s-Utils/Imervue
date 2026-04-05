"""
Frozen-safe path resolution for Imervue.

PyInstaller sets ``sys.frozen = True`` and ``sys._MEIPASS`` to the temp
extraction folder.  In that environment:

* ``sys.executable`` → the ``.exe`` itself (NOT a Python interpreter).
* ``__file__``       → points inside ``_internal/`` (one-dir mode).

This module provides a single ``app_dir()`` that always returns the
**application root** — the directory that contains the ``.exe`` (frozen)
or the project root (development).

All other path helpers (``plugins_dir``, ``icon_path``, …) are derived
from ``app_dir()`` so every part of the code resolves consistently.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path


def is_frozen() -> bool:
    """Whether we are running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


@lru_cache(maxsize=1)
def app_dir() -> Path:
    """Return the application root directory.

    * Frozen (PyInstaller one-dir): directory that contains the ``.exe``.
    * Development: project root (the parent of the ``Imervue/`` package).
    """
    if is_frozen():
        # sys.executable is e.g. D:/output/Imervue/Imervue.exe
        return Path(sys.executable).resolve().parent
    # Development: this file is Imervue/system/app_paths.py
    return Path(__file__).resolve().parent.parent.parent


def plugins_dir() -> Path:
    """``<app_dir>/plugins/``"""
    return app_dir() / "plugins"


def icon_path() -> Path:
    """``<app_dir>/Imervue.ico``"""
    return app_dir() / "Imervue.ico"


def embedded_python_dir() -> Path:
    """``<app_dir>/python_embedded/``"""
    return app_dir() / "python_embedded"


def user_settings_path() -> Path:
    """``<app_dir>/user_setting.json``"""
    return app_dir() / "user_setting.json"
