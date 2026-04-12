"""
Frozen-safe path resolution for Imervue.

Supports both PyInstaller and Nuitka standalone bundles:

* PyInstaller sets ``sys.frozen = True`` and ``sys._MEIPASS``.
* Nuitka sets a ``__compiled__`` attribute on every compiled module. It does
  **not** set ``sys.frozen``, so a naive ``getattr(sys, "frozen", False)``
  check misses Nuitka builds — which is the common reason plugin pip-install
  (which drops packages into ``<app_dir>/lib/site-packages``) silently
  breaks under Nuitka.

In both frozen environments:

* ``sys.executable`` → the ``.exe`` itself (NOT a Python interpreter).
* ``__file__``       → points inside the bundle directory.

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
    """Whether we are running inside a frozen bundle (PyInstaller **or** Nuitka)."""
    # PyInstaller / cx_Freeze set sys.frozen
    if getattr(sys, "frozen", False):
        return True
    # Nuitka sets __compiled__ in every compiled module's globals.
    # Because this very file gets compiled by Nuitka when building a
    # standalone bundle, its own module globals will carry the attribute.
    if "__compiled__" in globals():
        return True
    return False


@lru_cache(maxsize=1)
def app_dir() -> Path:
    """Return the application root directory.

    * Frozen (PyInstaller one-dir / Nuitka standalone): directory that
      contains the ``.exe``. For Nuitka this is ``<project>.dist/``.
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
    """``<app_dir>/exe/Imervue.ico``"""
    return app_dir() / "exe" / "Imervue.ico"


def embedded_python_dir() -> Path:
    """``<app_dir>/python_embedded/``"""
    return app_dir() / "python_embedded"


def user_settings_path() -> Path:
    """``<app_dir>/user_setting.json``"""
    return app_dir() / "user_setting.json"


def frozen_site_packages() -> Path:
    """``<app_dir>/lib/site-packages/`` — where plugin pip-installs land in frozen builds."""
    return app_dir() / "lib" / "site-packages"


def ensure_frozen_site_packages_on_path() -> None:
    """Insert the frozen ``lib/site-packages`` folder at the front of ``sys.path``.

    Called eagerly at startup so that packages a plugin previously installed
    (e.g. ``onnxruntime`` for the AI background remover) import correctly
    on the **next** launch without waiting for ``pip_installer`` to be
    imported. Idempotent; safe to call multiple times.
    """
    if not is_frozen():
        return
    lib = str(frozen_site_packages())
    if Path(lib).is_dir() and lib not in sys.path:
        sys.path.insert(0, lib)


# Run the injection at module-import time so every downstream import inherits
# the extra sys.path entry. This file is transitively imported by almost every
# startup code path (log setup, main window, plugin manager), so by the time
# any plugin tries to import its dependencies, the path is already wired up.
ensure_frozen_site_packages_on_path()
