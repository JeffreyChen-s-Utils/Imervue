"""Exercise the frozen entry/OpenGL import boundary without starting the GUI.

PyInstaller bundles the repository entry file unchanged as data, avoiding the
GUI dependency graph. This is an import smoke test, not a rendering test.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import sys


def main() -> None:
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Run the PyInstaller executable, not the source probe")
    if "PYOPENGL_PLATFORM" in os.environ:
        raise RuntimeError("PYOPENGL_PLATFORM must be unset before startup")
    if "OpenGL.platform" in sys.modules:
        raise RuntimeError("OpenGL platform was loaded before the application entry")

    entry = Path(__file__).resolve().parent / "imervue-entry" / "__main__.py"
    source_hash = hashlib.sha256(entry.read_bytes()).hexdigest()
    runpy.run_path(str(entry), run_name="imervue_frozen_startup_probe")

    from OpenGL import GL, platform

    expected = {
        "linux": "GLXPlatform",
        "darwin": "DarwinPlatform",
        "win32": "Win32Platform",
    }[sys.platform]
    actual = type(platform.PLATFORM).__name__
    if actual != expected:
        raise RuntimeError(f"Expected native {expected}, got {actual}")
    if sys.platform != "win32" and "PYOPENGL_PLATFORM" in os.environ:
        raise RuntimeError("Application entry unexpectedly forced an OpenGL platform")
    if platform.PLATFORM.GL is None or not callable(GL.glGetError):
        raise RuntimeError("Native OpenGL library or GL entry point is unavailable")
    if any(name.startswith(("PySide6", "PyQt")) for name in sys.modules):
        raise RuntimeError("Import probe unexpectedly loaded the GUI")

    print(json.dumps({
        "scope": "frozen entry initialization and native OpenGL.GL import",
        "frozen": True,
        "platform": sys.platform,
        "backend": actual,
        "entry_sha256": source_hash,
        "commit": os.environ.get("GITHUB_SHA"),
        "status": "passed",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
