"""Set the desktop wallpaper: Windows through ``SystemParametersInfoW``, macOS
through Finder via ``osascript``, Linux through GNOME's ``gsettings``.

The image path comes from the browsed folder, so it is never spliced into a
script: macOS receives it as an ``osascript`` argument, GNOME as a ``file://``
URI. Failures are logged, not raised — the caller is a menu action.

The desktop decodes the file itself, and not every format Imervue opens:
Windows, handed a file it can't decode (a TGA, a PSD, a camera RAW or HEIC
without Microsoft's codec), still reports success and turns the desktop
black. A picture outside JPEG / PNG / BMP, and a photo that has to be turned
upright, therefore goes over as a JPEG copy of what the viewer shows
(:func:`wallpaper_file`).
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess  # nosec B404  # static argument lists, see wallpaper_commands
import sys
from pathlib import Path

from PIL import Image

from Imervue.image.formats import JPEG_EXTENSIONS
from Imervue.image.high_bit_depth import to_eight_bit
from Imervue.image.orientation import read_orientation
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.image.shown import open_shown

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

# Formats every desktop decodes; anything else goes over as a JPEG copy.
_DESKTOP_SUFFIXES = JPEG_EXTENSIONS | {".png", ".bmp"}
_UPRIGHT = 1
_COPY_QUALITY = 95


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


def _copy_dir() -> Path:
    """Where the wallpaper copy lives: it must outlast the session (GNOME reads it at login)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue" / "wallpaper"
    return Path.home() / ".local" / "share" / "imervue" / "wallpaper"


def _needs_copy(path: str) -> bool:
    if Path(path).suffix.lower() not in _DESKTOP_SUFFIXES:
        return True
    return read_orientation(path) != _UPRIGHT


def _copy_name(path: str) -> str:
    """A name that changes with the source, so a desktop caching by path shows the new one."""
    stat = os.stat(path)
    key = f"{os.path.abspath(path)}|{stat.st_size}|{stat.st_mtime_ns}".encode()
    return f"{Path(path).stem}-{hashlib.sha256(key).hexdigest()[:12]}.jpg"


def _write_copy(path: str, target: Path) -> None:
    """Save *path* as the viewer shows it, transparency on black, as a JPEG at *target*."""
    shown = to_eight_bit(open_shown(path)).convert("RGBA")
    flat = Image.new("RGB", shown.size)
    flat.paste(shown, mask=shown.getchannel("A"))
    partial = target.with_suffix(".part")
    flat.save(partial, "JPEG", quality=_COPY_QUALITY)
    os.replace(partial, target)


def _remove_other_copies(folder: Path, keep: Path) -> None:
    for entry in folder.iterdir():
        if entry == keep or not entry.is_file():
            continue
        try:
            entry.unlink()
        except OSError:   # still open somewhere: the next wallpaper tries again
            logger.debug("Could not remove the old wallpaper copy %s", entry, exc_info=True)


def wallpaper_file(path: str) -> str:
    """The file to hand the desktop for *path*: *path* itself, or a JPEG copy of it.

    The copy - upright, sRGB, 8-bit, transparency on black - is made for a
    format outside JPEG / PNG / BMP and for a photo with an EXIF orientation.
    Only the newest copy is kept. When no copy can be made, *path* itself is
    returned and the desktop may still manage it.
    """
    if not _needs_copy(path):
        return path
    folder = _copy_dir()
    try:
        target = folder / _copy_name(path)
        if not target.is_file():
            folder.mkdir(parents=True, exist_ok=True)
            _write_copy(path, target)
        _remove_other_copies(folder, keep=target)
    except IMAGE_READ_ERRORS:   # unreadable picture, or the copy can't be written
        logger.warning("Could not make a wallpaper copy of %s; handing over the file itself",
                       path, exc_info=True)
        return path
    return str(target)


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

    Side effects: may decode *path* and write a copy (see
    :func:`wallpaper_file`), so it belongs off the GUI thread; on macOS and
    Linux the helper processes are started and not waited for.
    """
    path = wallpaper_file(path)
    if sys.platform == "win32":
        _set_windows_wallpaper(path)
        return
    for command in wallpaper_commands(path, sys.platform):
        try:
            subprocess.Popen(command)  # nosec B603,B607  # nosemgrep  # fixed argv, no shell
        except OSError:
            logger.warning("Could not run %s to set the wallpaper", command[0], exc_info=True)
            return
