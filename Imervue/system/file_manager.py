"""Open the OS file manager at a path, selecting the file where the platform can.

Windows uses ``explorer`` (``/select,`` for a file), macOS ``open`` (``-R`` to
reveal), Linux ``xdg-open`` on the folder. :func:`reveal_in_file_manager`
raises the ``OSError`` of a file manager that cannot be started;
:func:`reveal_or_warn` logs it, for a menu action with nothing better to do.

Explorer splits its command line at commas and ``=``, and only a field in
double quotes may hold them; ``subprocess`` quotes an argument only when it has
a space, so a photo in a folder named ``trip,day1`` opened the wrong folder.
The Windows command line is therefore built with the path always quoted (a
Windows path can't contain a quote itself).
"""
from __future__ import annotations

import logging
import os
import subprocess  # nosec B404  # static commands around a local path, see reveal_in_file_manager
import sys
from pathlib import Path

logger = logging.getLogger("Imervue.file_manager")


def explorer_command(path: str, *, select: bool) -> str:
    """The ``explorer`` command line that selects *path* (or opens it), the path quoted."""
    target = os.path.normpath(path)
    return f'explorer /select,"{target}"' if select else f'explorer "{target}"'


def reveal_in_file_manager(path: str, *, select: bool = True) -> None:
    """Open the OS file manager at ``path`` (selecting it when ``select``).

    Static command + a local filesystem path from the file tree — no
    untrusted input, shell=False. Bandit B603/B607 and Semgrep flag any
    subprocess use; suppressed inline (rules are also config-skipped).
    Raises ``OSError`` when the file manager cannot be started.
    """
    if sys.platform == "win32":
        subprocess.Popen(  # nosec B603,B607  # nosemgrep
            explorer_command(path, select=select and Path(path).is_file()),
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


def reveal_or_warn(path: str, *, select: bool = True) -> None:
    """:func:`reveal_in_file_manager`, logging a warning when the file manager won't start."""
    try:
        reveal_in_file_manager(path, select=select)
    except (OSError, ValueError):   # file manager missing, or it refused the path
        logger.warning("Could not reveal %s in the file manager", path, exc_info=True)
