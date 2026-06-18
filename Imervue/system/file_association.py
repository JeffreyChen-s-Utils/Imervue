"""Cross-platform file association — "Open with Imervue".

* **Windows**: per-user registry entries (``HKCU\\Software\\Classes``) giving an
  app registration and a right-click "Open with Imervue" verb per extension.
* **Linux**: an XDG ``imervue.desktop`` entry in
  ``~/.local/share/applications`` declaring the supported MIME types; most
  desktop environments pick it up without an explicit database refresh.
* **macOS**: associations are declared by the ``.app`` bundle's ``Info.plist``
  at build time, so the runtime call is a documented no-op.

The platform-independent decisions (MIME mapping, desktop-entry text, the
launch command) are pure functions so they can be unit-tested without touching
the registry or the real home directory.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from Imervue.system.app_paths import app_dir, icon_path as _app_icon_path, is_frozen

logger = logging.getLogger("Imervue.file_assoc")

# 支援關聯的副檔名
ASSOC_EXTENSIONS = [
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif",
    ".webp", ".gif", ".apng",
    ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf",
]

_APP_ID = "Imervue.ImageViewer"
_SHELL_LABEL = "Open with Imervue"
_DESKTOP_FILE = "imervue.desktop"

_MIME_BY_EXT = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".bmp": "image/bmp", ".tiff": "image/tiff", ".tif": "image/tiff",
    ".webp": "image/webp", ".gif": "image/gif", ".apng": "image/apng",
    ".cr2": "image/x-canon-cr2", ".nef": "image/x-nikon-nef",
    ".arw": "image/x-sony-arw", ".dng": "image/x-adobe-dng",
    ".raf": "image/x-fuji-raf", ".orf": "image/x-olympus-orf",
}


# ---------------------------------------------------------------------------
# Pure helpers (no I/O — unit-testable)
# ---------------------------------------------------------------------------


def mime_types_for_extensions(exts: list[str]) -> list[str]:
    """Map file extensions to de-duplicated MIME types, preserving order."""
    out: list[str] = []
    for ext in exts:
        mime = _MIME_BY_EXT.get(ext.lower())
        if mime and mime not in out:
            out.append(mime)
    return out


def launch_command(executable: str, main_file: str | None,
                   frozen: bool, file_token: str) -> str:
    """Build the launch command with *file_token* (``%1`` Windows / ``%f`` XDG)."""
    if frozen:
        return f'"{executable}" {file_token}'
    if main_file:
        return f'"{executable}" "{main_file}" {file_token}'
    return f'"{executable}" -m Imervue {file_token}'


def desktop_entry_content(exec_cmd: str, icon: str, mime_types: list[str]) -> str:
    """Build the XDG ``.desktop`` file body for the Linux file association."""
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Name=Imervue",
        "Comment=Image viewer and editor",
        f"Exec={exec_cmd}",
        f"Icon={icon}",
        "Terminal=false",
        "Categories=Graphics;Viewer;Photography;",
        "MimeType=" + ";".join(mime_types) + ";",
    ]
    return "\n".join(lines) + "\n"


def _main_file() -> str | None:
    candidate = app_dir() / "Imervue" / "__main__.py"
    return str(candidate) if candidate.exists() else None


# ---------------------------------------------------------------------------
# Platform dispatch
# ---------------------------------------------------------------------------


def register_file_association() -> tuple[bool, str]:
    """Register the file association for the current platform. ``(ok, message)``."""
    if sys.platform == "win32":
        return _register_windows()
    if sys.platform.startswith("linux"):
        return _register_linux()
    if sys.platform == "darwin":
        return False, "macos_use_bundle"
    return False, "unsupported_platform"


def unregister_file_association() -> tuple[bool, str]:
    """Remove the file association for the current platform. ``(ok, message)``."""
    if sys.platform == "win32":
        return _unregister_windows()
    if sys.platform.startswith("linux"):
        return _unregister_linux()
    if sys.platform == "darwin":
        return False, "macos_use_bundle"
    return False, "unsupported_platform"


# ---------------------------------------------------------------------------
# Linux (XDG desktop entry)
# ---------------------------------------------------------------------------


def _applications_dir() -> Path:
    return Path.home() / ".local" / "share" / "applications"


def _register_linux(apps_dir: Path | None = None) -> tuple[bool, str]:
    apps_dir = apps_dir or _applications_dir()
    exec_cmd = launch_command(sys.executable, _main_file(), is_frozen(), "%f")
    content = desktop_entry_content(
        exec_cmd, str(_app_icon_path()), mime_types_for_extensions(ASSOC_EXTENSIONS),
    )
    try:
        apps_dir.mkdir(parents=True, exist_ok=True)
        (apps_dir / _DESKTOP_FILE).write_text(content, encoding="utf-8")
    except OSError as exc:
        logger.exception("Linux desktop entry write failed")
        return False, str(exc)
    logger.info("Linux desktop entry written to %s", apps_dir / _DESKTOP_FILE)
    return True, str(apps_dir / _DESKTOP_FILE)


def _unregister_linux(apps_dir: Path | None = None) -> tuple[bool, str]:
    desktop_file = (apps_dir or _applications_dir()) / _DESKTOP_FILE
    try:
        desktop_file.unlink(missing_ok=True)
    except OSError as exc:
        return False, str(exc)
    return True, "OK"


# ---------------------------------------------------------------------------
# Windows (registry)
# ---------------------------------------------------------------------------


def _build_command() -> str:
    return launch_command(sys.executable, _main_file(), is_frozen(), '"%1"')


def _register_windows() -> tuple[bool, str]:
    try:
        import winreg
    except ImportError:
        return False, "winreg not available"

    command = _build_command()
    try:
        app_key_path = rf"Software\Classes\{_APP_ID}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_key_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Imervue Image Viewer")

        cmd_path = rf"{app_key_path}\shell\open\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)

        for ext in ASSOC_EXTENSIONS:
            _register_ext_context_menu(ext, command)

        logger.info("File association registered successfully")
        return True, "OK"
    except PermissionError:
        return False, "need_admin"
    except OSError as e:
        logger.exception("Registration failed")
        return False, str(e)


def _register_ext_context_menu(ext: str, command: str):
    """為指定副檔名加入右鍵 shell 選單"""
    import winreg

    shell_path = rf"Software\Classes\SystemFileAssociations\{ext}\shell\Imervue"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_path) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, _SHELL_LABEL)
        ico = _app_icon_path()
        if ico.exists():
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, str(ico))

    cmd_path = rf"{shell_path}\command"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_path) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)


def _unregister_windows() -> tuple[bool, str]:
    try:
        import winreg
    except ImportError:
        return False, "winreg not available"

    try:
        _delete_key_tree(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{_APP_ID}")
        for ext in ASSOC_EXTENSIONS:
            shell_path = rf"Software\Classes\SystemFileAssociations\{ext}\shell\Imervue"
            _delete_key_tree(winreg.HKEY_CURRENT_USER, shell_path)
        logger.info("File association removed successfully")
        return True, "OK"
    except PermissionError:
        return False, "need_admin"
    except OSError as e:
        logger.exception("Unregistration failed")
        return False, str(e)


def _delete_key_tree(hive, path: str):
    """遞迴刪除登錄機碼"""
    import winreg
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS) as key:
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, 0)
                    _delete_key_tree(hive, rf"{path}\{subkey_name}")
                except OSError:
                    break
        winreg.DeleteKey(hive, path)
    except FileNotFoundError:
        pass  # 機碼不存在
