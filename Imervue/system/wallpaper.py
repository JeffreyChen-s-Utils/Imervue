"""Set the desktop wallpaper: Windows through ``SystemParametersInfoW``, macOS
through Finder via ``osascript``, Linux through GNOME's ``gsettings``.

The image path comes from the browsed folder, so it is never spliced into a
script: macOS receives it as an ``osascript`` argument, GNOME as a ``file://``
URI. Failures are logged, not raised — the caller is a menu action.
"""
from __future__ import annotations

import logging
import os
import subprocess  # nosec B404  # static argument lists, see wallpaper_commands
import sys
from pathlib import Path

logger = logging.getLogger("Imervue.system.wallpaper")

_SPI_SETDESKWALLPAPER = 0x0014
_SPIF_UPDATEINIFILE = 0x01
_SPIF_SENDCHANGE = 0x02

# The path arrives as ``item 1 of argv``, never as script text, so a file name
# containing quotes cannot change what the script does.
_MACOS_SCRIPT = (
    "on run argv",
    'tell application "Finder" to set desktop picture to POSIX file (item 1 of argv)',
    "end run",
)

# GNOME 42+ keeps a separate wallpaper for the dark style; setting only
# ``picture-uri`` leaves a dark-mode desktop unchanged.
_GNOME_KEYS = ("picture-uri", "picture-uri-dark")


def wallpaper_commands(path: str, platform: str) -> list[list[str]]:
    """Return the argument lists that set ``path`` as wallpaper on a non-Windows ``platform``.

    ``path`` is made absolute first, so it never starts with ``-`` and cannot be
    read as an option.
    """
    abs_path = os.path.abspath(path)
    if platform == "darwin":
        script_args = [arg for line in _MACOS_SCRIPT for arg in ("-e", line)]
        return [["osascript", *script_args, abs_path]]
    uri = Path(abs_path).as_uri()
    return [["gsettings", "set", "org.gnome.desktop.background", key, uri] for key in _GNOME_KEYS]


def _set_windows_wallpaper(path: str) -> None:
    import ctypes
    ok = ctypes.windll.user32.SystemParametersInfoW(
        _SPI_SETDESKWALLPAPER, 0, os.path.abspath(path),
        _SPIF_UPDATEINIFILE | _SPIF_SENDCHANGE,
    )
    if not ok:
        logger.warning("Windows refused to set the wallpaper to %s", path)


def set_desktop_wallpaper(path: str) -> None:
    """Set ``path`` as the desktop wallpaper; log instead of raising on failure.

    Side effect: on macOS and Linux the helper processes are started and not
    waited for.
    """
    if sys.platform == "win32":
        _set_windows_wallpaper(path)
        return
    for command in wallpaper_commands(path, sys.platform):
        try:
            subprocess.Popen(command)  # nosec B603,B607  # nosemgrep  # fixed argv, no shell
        except OSError:
            logger.warning("Could not run %s to set the wallpaper", command[0], exc_info=True)
            return
