"""Open the OS file manager at a path, selecting the file where the platform can.

Windows uses ``explorer`` (``/select,`` for a file), macOS ``open`` (``-R`` to
reveal), Linux ``xdg-open`` on the folder. Callers decide how to report the
``OSError`` raised when the file manager cannot be started.
"""
from __future__ import annotations

import os
import subprocess  # nosec B404  # static argument lists, see reveal_in_file_manager
import sys
from pathlib import Path


def reveal_in_file_manager(path: str, *, select: bool = True) -> None:
    """Open the OS file manager at ``path`` (selecting it when ``select``).

    Static command + a local filesystem path from the file tree — no
    untrusted input, shell=False. Bandit B603/B607 and Semgrep flag any
    subprocess use; suppressed inline (rules are also config-skipped).
    Raises ``OSError`` when the file manager cannot be started.
    """
    if sys.platform == "win32":
        if select and Path(path).is_file():
            subprocess.Popen(  # nosec B603,B607  # nosemgrep
                ["explorer", "/select,", os.path.normpath(path)],
            )
        else:
            subprocess.Popen(  # nosec B603,B607  # nosemgrep
                ["explorer", os.path.normpath(path)],
            )
    elif sys.platform == "darwin":
        subprocess.Popen(  # nosec B603,B607  # nosemgrep
            ["open", "-R", path] if select else ["open", path],
        )
    else:
        target = path if Path(path).is_dir() else str(Path(path).parent)
        subprocess.Popen(  # nosec B603,B607  # nosemgrep
            ["xdg-open", target],
        )
