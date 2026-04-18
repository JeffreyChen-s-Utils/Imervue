"""
Windows 檔案關聯 — 「以 Imervue 開啟」右鍵選單
Windows file association — "Open with Imervue" context menu.
"""
from __future__ import annotations

import logging
import sys

from Imervue.system.app_paths import is_frozen, app_dir, icon_path as _app_icon_path

logger = logging.getLogger("Imervue.file_assoc")

# 支援關聯的副檔名
ASSOC_EXTENSIONS = [
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif",
    ".webp", ".gif", ".apng",
    ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf",
]

_APP_ID = "Imervue.ImageViewer"
_SHELL_LABEL = "Open with Imervue"


def _build_command() -> str:
    """建立用於檔案關聯的啟動命令。

    * 凍結環境：直接用 exe 路徑。
    * 開發環境：用 python + 入口腳本 / -m Imervue。
    """
    if is_frozen():
        return f'"{sys.executable}" "%1"'

    python_exe = sys.executable
    pkg_dir = app_dir() / "Imervue"
    main_file = pkg_dir / "__main__.py"
    if main_file.exists():
        return f'"{python_exe}" "{main_file}" "%1"'
    return f'"{python_exe}" -m Imervue "%1"'


def register_file_association() -> tuple[bool, str]:
    """在 Windows 登錄檔中註冊檔案關聯。需要管理員權限。

    Returns:
        (success, message)
    """
    if sys.platform != "win32":
        return False, "Only supported on Windows"

    try:
        import winreg
    except ImportError:
        return False, "winreg not available"

    command = _build_command()

    try:
        # 1. 建立 Application 登錄
        app_key_path = rf"Software\Classes\{_APP_ID}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_key_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Imervue Image Viewer")

        # shell\open\command
        cmd_path = rf"{app_key_path}\shell\open\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)

        # 2. 為每種副檔名加入「以 Imervue 開啟」右鍵選單
        for ext in ASSOC_EXTENSIONS:
            _register_ext_context_menu(ext, command)

        logger.info("File association registered successfully")
        return True, "OK"
    except PermissionError:
        return False, "need_admin"
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        return False, str(e)


def _register_ext_context_menu(ext: str, command: str):
    """為指定副檔名加入右鍵 shell 選單"""
    import winreg

    # HKCU\Software\Classes\.ext\shell\Imervue\command
    shell_path = rf"Software\Classes\SystemFileAssociations\{ext}\shell\Imervue"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_path) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, _SHELL_LABEL)
        # Icon
        ico = _app_icon_path()
        if ico.exists():
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, str(ico))

    cmd_path = rf"{shell_path}\command"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_path) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)


def unregister_file_association() -> tuple[bool, str]:
    """移除已註冊的檔案關聯。

    Returns:
        (success, message)
    """
    if sys.platform != "win32":
        return False, "Only supported on Windows"

    try:
        import winreg
    except ImportError:
        return False, "winreg not available"

    try:
        # 移除 Application 登錄
        _delete_key_tree(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{_APP_ID}")

        # 移除各副檔名的右鍵選單
        for ext in ASSOC_EXTENSIONS:
            shell_path = rf"Software\Classes\SystemFileAssociations\{ext}\shell\Imervue"
            _delete_key_tree(winreg.HKEY_CURRENT_USER, shell_path)

        logger.info("File association removed successfully")
        return True, "OK"
    except PermissionError:
        return False, "need_admin"
    except Exception as e:
        logger.error(f"Unregistration failed: {e}")
        return False, str(e)


def _delete_key_tree(hive, path: str):
    """遞迴刪除登錄機碼"""
    import winreg
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS) as key:
            # 先刪除所有子機碼
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, 0)
                    _delete_key_tree(hive, rf"{path}\{subkey_name}")
                except OSError:
                    break
        winreg.DeleteKey(hive, path)
    except FileNotFoundError:
        pass  # 機碼不存在
