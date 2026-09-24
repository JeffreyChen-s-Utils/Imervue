"""Find a Python interpreter with a working pip for installing plugin dependencies.

Outside a frozen build that is ``sys.executable``. In a frozen build the
search tries PATH, then the Windows registry and the usual install folders
(or the usual Unix paths), then the embedded Python the installer can
download. Every candidate is checked with ``python -m pip --version``.
All of this runs subprocesses, so call it off the UI thread.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from Imervue.system.app_paths import (
    embedded_python_dir as _embedded_python_dir_path,
)
from Imervue.system.app_paths import is_frozen as _is_frozen

logger = logging.getLogger("Imervue.plugin.python_finder")



def _subprocess_kwargs() -> dict:
    """所有 subprocess 共用的參數，防止卡住。

    - stdin=DEVNULL：阻止子程序讀取 stdin（pip 等待輸入）
    - CREATE_NO_WINDOW：Windows 下不彈出黑色主控台
    - encoding / errors：避免非 UTF-8 系統下的 UnicodeDecodeError
    """
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


_PYTHON_EXE_NAME = "python.exe"


def _embedded_python_dir() -> Path:
    """內嵌 Python 的安裝路徑"""
    return _embedded_python_dir_path()


def _embedded_python_exe() -> Path | None:
    """回傳內嵌 Python 的 python.exe 路徑（若已安裝）"""
    exe = _embedded_python_dir() / _PYTHON_EXE_NAME
    return exe if exe.is_file() else None


def _find_python_windows_install_paths() -> str | None:
    """Scan common Windows Python install locations for a working interpreter."""
    import shutil
    import os
    localappdata = os.environ.get("LOCALAPPDATA", "")
    appdata_programs = os.environ.get("PROGRAMFILES", "C:\\Program Files")
    candidates: list[str] = []
    py_launcher = shutil.which("py")
    if py_launcher:
        candidates.append(py_launcher)
    for base in [localappdata + "\\Programs\\Python",
                  appdata_programs + "\\Python"]:
        if Path(base).is_dir():
            for d in sorted(Path(base).iterdir(), reverse=True):
                exe = d / _PYTHON_EXE_NAME
                if exe.is_file():
                    candidates.append(str(exe))
    for c in candidates:
        if _verify_python(c):
            return c
    return None


def _find_python_unix_paths() -> str | None:
    """Scan conventional Unix Python locations for a working interpreter."""
    for p in ("/usr/bin/python3", "/usr/local/bin/python3",
              "/usr/bin/python", "/usr/local/bin/python"):
        if Path(p).is_file() and _verify_python(p):
            return p
    return None


def _find_python() -> str | None:
    """找到可用的 Python 直譯器路徑。

    - 一般環境：直接用 sys.executable
    - PyInstaller 環境：sys.executable 是 .exe 本身，需另外搜尋

    注意：此函式會執行多個 subprocess，不應在 UI 主執行緒呼叫。
    """
    import shutil

    if not _is_frozen():
        return sys.executable

    # 1) PATH 搜尋
    for name in ("python", "python3", "py"):
        found = shutil.which(name)
        if found and _verify_python(found):
            return found

    # 2) Windows：查 registry 找已安裝的 Python
    if sys.platform == "win32":
        reg_python = _find_python_from_registry()
        if reg_python:
            return reg_python
        win_install = _find_python_windows_install_paths()
        if win_install:
            return win_install
    else:
        unix = _find_python_unix_paths()
        if unix:
            return unix

    # 3) 內嵌 Python（之前自動下載的）
    embed_exe = _embedded_python_exe()
    if embed_exe and _verify_python(str(embed_exe)):
        return str(embed_exe)

    return None


_REG_SUBKEYS = (
    r"Software\Python\PythonCore",
    r"Software\WOW6432Node\Python\PythonCore",
)


def _find_python_from_registry() -> str | None:
    """Windows：從 registry 搜尋已安裝的 Python"""
    try:
        import winreg
    except ImportError:
        return None
    hives = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    for hive in hives:
        for sub in _REG_SUBKEYS:
            path = _scan_registry_branch(winreg, hive, sub)
            if path:
                return path
    return None


def _scan_registry_branch(winreg, hive, sub: str) -> str | None:
    try:
        key = winreg.OpenKey(hive, sub)
    except OSError:
        return None
    try:
        return _enumerate_python_versions(winreg, key)
    except OSError:
        return None


def _enumerate_python_versions(winreg, key) -> str | None:
    i = 0
    while True:
        try:
            ver = winreg.EnumKey(key, i)
        except OSError:
            return None
        i += 1
        path = _read_install_path(winreg, key, ver)
        if path:
            return path


def _read_install_path(winreg, key, ver: str) -> str | None:
    try:
        install_key = winreg.OpenKey(key, ver + r"\InstallPath")
        path, _ = winreg.QueryValueEx(install_key, "ExecutablePath")
    except OSError:
        return None
    if Path(path).is_file() and _verify_python(path):
        return path
    return None


# ``pip --version`` has to import pip before it answers; on a cold start or a
# busy machine that takes several seconds, and a tight budget rejected working
# interpreters.
_VERIFY_TIMEOUT_S = 30.0


def _verify_python(path: str) -> bool:
    """驗證該路徑確實是可用的 Python 且有 pip.

    Returns ``False`` — and logs why — when the interpreter cannot be started
    (``OSError``, or ``ValueError`` for a malformed path), does not answer
    within :data:`_VERIFY_TIMEOUT_S`, or has no working pip. Anything else is
    a bug and propagates.
    """
    try:
        result = subprocess.run(
            [path, "-m", "pip", "--version"],
            capture_output=True,
            timeout=_VERIFY_TIMEOUT_S,
            check=False,
            **_subprocess_kwargs(),
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "Python at %s did not answer `pip --version` within %.0f s",
            path, _VERIFY_TIMEOUT_S,
        )
        return False
    except (OSError, ValueError) as exc:
        logger.info("Cannot run Python at %s: %s", path, exc)
        return False
    if result.returncode != 0:
        logger.info("Python at %s has no working pip (exit %d)", path, result.returncode)
        return False
    return True
