"""
Plugin dependency installer — find/download Python and install pip packages.

When plugins require pip packages that aren't bundled with the app, this
module provides:

* ``ensure_dependencies(parent, packages, on_ready)`` — one-call gate that
  checks for missing packages, pops an install dialog if needed, and calls
  *on_ready* when everything is available.
* Automatic Python discovery (PATH, registry, common paths, embedded).
* Automatic download of the Python embeddable package on Windows when no
  interpreter is found.
"""
from __future__ import annotations

import importlib
import io
import logging
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.request import urlopen, Request
from urllib.error import URLError

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

logger = logging.getLogger("Imervue.plugin.pip_installer")


# ===========================
# subprocess 工具
# ===========================

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


# ===========================
# 環境偵測
# ===========================

def _is_frozen() -> bool:
    """是否在 PyInstaller 打包環境中執行"""
    return getattr(sys, "frozen", False)


# 啟動時：若為凍結環境，將 lib/site-packages 加入 sys.path
# 這樣上次安裝的套件在下次啟動時就能被 import
if _is_frozen():
    _frozen_lib = str(Path(sys.executable).parent / "lib" / "site-packages")
    if Path(_frozen_lib).is_dir() and _frozen_lib not in sys.path:
        sys.path.insert(0, _frozen_lib)


# ===========================
# 內嵌 Python 自動下載
# ===========================

_EMBED_PYTHON_VERSION = "3.12.8"
_EMBED_PYTHON_URL = (
    f"https://www.python.org/ftp/python/{_EMBED_PYTHON_VERSION}/"
    f"python-{_EMBED_PYTHON_VERSION}-embed-amd64.zip"
)
_GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"


def _embedded_python_dir() -> Path:
    """內嵌 Python 的安裝路徑"""
    if _is_frozen():
        return Path(sys.executable).parent / "python_embedded"
    return Path(__file__).resolve().parent.parent.parent / "python_embedded"


def _embedded_python_exe() -> Path | None:
    """回傳內嵌 Python 的 python.exe 路徑（若已安裝）"""
    exe = _embedded_python_dir() / "python.exe"
    return exe if exe.is_file() else None


class _DownloadPythonWorker(QThread):
    """背景下載並安裝 Python embeddable package"""
    log = Signal(str)
    finished = Signal(bool, str)  # success, python_exe_path or error

    def run(self):
        try:
            dest_dir = _embedded_python_dir()
            dest_dir.mkdir(parents=True, exist_ok=True)

            # 1) 下載 Python embeddable zip
            self.log.emit(f"Downloading Python {_EMBED_PYTHON_VERSION} embeddable ...")
            try:
                req = Request(_EMBED_PYTHON_URL, headers={"User-Agent": "Imervue/1.0"})
                resp = urlopen(req, timeout=120)
                data = resp.read()
            except (URLError, OSError) as e:
                self.finished.emit(False, f"Download failed: {e}")
                return

            # 2) 解壓到目標資料夾
            self.log.emit("Extracting Python embeddable ...")
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(dest_dir)

            python_exe = dest_dir / "python.exe"
            if not python_exe.is_file():
                self.finished.emit(False, "python.exe not found after extraction")
                return

            # 3) 修改 ._pth 檔案：取消註解 import site（pip 需要它）
            for pth_file in dest_dir.glob("python*._pth"):
                self.log.emit(f"Patching {pth_file.name} to enable 'import site' ...")
                content = pth_file.read_text(encoding="utf-8")
                content = content.replace("#import site", "import site")
                pth_file.write_text(content, encoding="utf-8")

            # 4) 下載並執行 get-pip.py（即時輸出）
            self.log.emit("Downloading get-pip.py ...")
            try:
                req = Request(_GET_PIP_URL, headers={"User-Agent": "Imervue/1.0"})
                resp = urlopen(req, timeout=120)
                get_pip_data = resp.read()
            except (URLError, OSError) as e:
                self.finished.emit(False, f"Failed to download get-pip.py: {e}")
                return

            get_pip_path = dest_dir / "get-pip.py"
            get_pip_path.write_bytes(get_pip_data)

            self.log.emit("Installing pip ...")
            returncode = self._run_with_live_output(
                [str(python_exe), str(get_pip_path)],
                cwd=str(dest_dir),
                timeout=300,
            )
            if returncode != 0:
                self.finished.emit(False, f"get-pip.py failed (exit code {returncode})")
                return

            get_pip_path.unlink(missing_ok=True)

            # 5) 驗證 pip 可用
            self.log.emit("Verifying pip ...")
            if not _verify_python(str(python_exe)):
                self.finished.emit(False, "pip verification failed after bootstrap")
                return

            self.log.emit("Python embeddable installed successfully!")
            self.finished.emit(True, str(python_exe))

        except Exception as exc:
            logger.error(f"Download Python failed: {exc}")
            self.finished.emit(False, str(exc))

    def _run_with_live_output(
        self, cmd: list[str], cwd: str | None = None, timeout: int = 600,
    ) -> int:
        """執行子程序並即時 emit 每一行輸出"""
        kw = _subprocess_kwargs()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            **kw,
        )
        try:
            for line in proc.stdout:
                text = line.rstrip("\n\r")
                if text:
                    self.log.emit(text)
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            self.log.emit("Process timed out")
            return -1
        return proc.returncode


# ===========================
# Python 搜尋
# ===========================

class _FindPythonWorker(QThread):
    """在背景執行緒搜尋可用的 Python 直譯器，避免阻塞 UI。"""
    finished = Signal(object)  # str | None

    def run(self):
        result = _find_python()
        self.finished.emit(result)


def _find_python() -> str | None:
    """找到可用的 Python 直譯器路徑。

    - 一般環境：直接用 sys.executable
    - PyInstaller 環境：sys.executable 是 .exe 本身，需另外搜尋

    注意：此函式會執行多個 subprocess，不應在 UI 主執行緒呼叫。
    """
    import shutil

    # 非凍結環境 → 直接用
    if not _is_frozen():
        return sys.executable

    # --- 凍結環境：嘗試各種方式找 Python ---

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

    # 3) Windows：常見安裝路徑
    if sys.platform == "win32":
        import os
        localappdata = os.environ.get("LOCALAPPDATA", "")
        appdata_programs = os.environ.get("ProgramFiles", "C:\\Program Files")
        candidates = []
        py_launcher = shutil.which("py")
        if py_launcher:
            candidates.append(py_launcher)
        for base in [localappdata + "\\Programs\\Python",
                      appdata_programs + "\\Python"]:
            if Path(base).is_dir():
                for d in sorted(Path(base).iterdir(), reverse=True):
                    exe = d / "python.exe"
                    if exe.is_file():
                        candidates.append(str(exe))
        for c in candidates:
            if _verify_python(c):
                return c

    # 4) Unix：常見路徑
    if sys.platform != "win32":
        for p in ["/usr/bin/python3", "/usr/local/bin/python3",
                   "/usr/bin/python", "/usr/local/bin/python"]:
            if Path(p).is_file() and _verify_python(p):
                return p

    # 5) 內嵌 Python（之前自動下載的）
    embed_exe = _embedded_python_exe()
    if embed_exe and _verify_python(str(embed_exe)):
        return str(embed_exe)

    return None


def _find_python_from_registry() -> str | None:
    """Windows：從 registry 搜尋已安裝的 Python"""
    try:
        import winreg
        for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            for sub in [r"Software\Python\PythonCore",
                        r"Software\WOW6432Node\Python\PythonCore"]:
                try:
                    key = winreg.OpenKey(hive, sub)
                except OSError:
                    continue
                try:
                    i = 0
                    while True:
                        ver = winreg.EnumKey(key, i)
                        i += 1
                        try:
                            install_key = winreg.OpenKey(
                                key, ver + r"\InstallPath")
                            path, _ = winreg.QueryValueEx(
                                install_key, "ExecutablePath")
                            if Path(path).is_file() and _verify_python(path):
                                return path
                        except OSError:
                            continue
                except OSError:
                    pass
    except ImportError:
        pass
    return None


def _verify_python(path: str) -> bool:
    """驗證該路徑確實是可用的 Python 且有 pip"""
    try:
        kw = _subprocess_kwargs()
        result = subprocess.run(
            [path, "-m", "pip", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            **kw,
        )
        return result.returncode == 0
    except Exception:
        return False


# ===========================
# 套件檢查
# ===========================

def check_missing_packages(
    packages: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """回傳缺少的套件列表。

    Args:
        packages: [(import_name, pip_name), ...]

    Returns:
        Still-missing subset of *packages*.
    """
    missing = []
    for import_name, pip_name in packages:
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append((import_name, pip_name))
    return missing


# ===========================
# 安裝 Worker
# ===========================

class _InstallWorker(QThread):
    """背景安裝缺少的 pip 套件（即時輸出每行 log）"""
    log = Signal(str)
    finished = Signal(bool, str)  # success, message

    def __init__(self, pip_names: list[str], python_path: str):
        super().__init__()
        self._pip_names = pip_names
        self._python = python_path

    def run(self):
        extra_args: list[str] = []
        if _is_frozen():
            target_dir = str(Path(sys.executable).parent / "lib" / "site-packages")
            extra_args = ["--target", target_dir]
            self.log.emit(f"Frozen mode: installing to {target_dir}")
            Path(target_dir).mkdir(parents=True, exist_ok=True)
            if target_dir not in sys.path:
                sys.path.insert(0, target_dir)

        for name in self._pip_names:
            self.log.emit(f"Installing {name} ...")
            try:
                cmd = [
                    self._python, "-m", "pip", "install",
                    "--no-input",
                    "--disable-pip-version-check",
                    name,
                ] + extra_args

                returncode = self._run_with_live_output(cmd, timeout=600)
                if returncode != 0:
                    self.finished.emit(
                        False,
                        f"Failed to install {name} (exit code {returncode})",
                    )
                    return
            except FileNotFoundError:
                self.finished.emit(False, f"Python not found: {self._python}")
                return
            except Exception as exc:
                self.finished.emit(False, str(exc))
                return

        self.finished.emit(True, "All packages installed successfully!")

    def _run_with_live_output(self, cmd: list[str], timeout: int = 600) -> int:
        """執行子程序並即時 emit 每一行輸出"""
        kw = _subprocess_kwargs()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kw,
        )
        try:
            for line in proc.stdout:
                text = line.rstrip("\n\r")
                if text:
                    self.log.emit(text)
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            self.log.emit("Process timed out")
            return -1
        return proc.returncode


# ===========================
# 安裝對話框
# ===========================

class InstallDependenciesDialog(QDialog):
    """顯示缺少套件並自動安裝"""

    def __init__(
        self,
        parent: QWidget,
        missing: list[tuple[str, str]],
        on_success=None,
    ):
        super().__init__(parent)
        self._missing = missing
        self._on_success = on_success
        self._worker = None
        self._dl_worker = None
        self._find_worker = None
        lang = language_wrapper.language_word_dict

        self.setWindowTitle(
            lang.get("pip_install_title", "Install Dependencies")
        )
        self.setMinimumSize(520, 360)
        self._build_ui()

    def _build_ui(self):
        lang = language_wrapper.language_word_dict
        layout = QVBoxLayout(self)

        pip_names = [pip for _, pip in self._missing]
        desc = lang.get(
            "pip_install_desc",
            "The following packages are required but not installed:\n\n"
            "{packages}\n\n"
            "Click Install to download and install them automatically.",
        ).format(packages="\n".join(f"  - {n}" for n in pip_names))
        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setVisible(False)
        self._log.setMaximumHeight(180)
        layout.addWidget(self._log)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel("")
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton(lang.get("export_cancel", "Cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        self._install_btn = QPushButton(
            lang.get("pip_install_btn", "Install")
        )
        self._install_btn.clicked.connect(self._do_install)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._install_btn)
        layout.addLayout(btn_row)

    # ----- 安裝流程 -----

    def _do_install(self):
        """按下安裝：先在背景搜尋 Python（不阻塞 UI）"""
        lang = language_wrapper.language_word_dict
        self._install_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._log.setVisible(True)
        self._log.append(lang.get(
            "pip_searching_python", "Searching for Python interpreter..."
        ))

        self._find_worker = _FindPythonWorker()
        self._find_worker.finished.connect(self._on_python_found)
        self._find_worker.start()

    def _on_python_found(self, python: str | None):
        self._find_worker = None

        if python is not None:
            self._start_package_install(python)
            return

        # 找不到 Python → 嘗試自動下載 (僅 Windows)
        if sys.platform == "win32":
            self._start_python_download()
        else:
            self._progress.setVisible(False)
            self._install_btn.setEnabled(True)
            self._show_no_python_error()

    def _show_no_python_error(self):
        lang = language_wrapper.language_word_dict
        self._log.setVisible(True)
        self._log.append(lang.get(
            "pip_no_python",
            "Cannot find a Python interpreter with pip.\n\n"
            "Please install Python from https://www.python.org/downloads/\n"
            "and make sure to check 'Add Python to PATH' during installation.",
        ))
        self._status.setText(lang.get(
            "pip_no_python_short",
            "Python not found. Please install Python first.",
        ))

    def _start_python_download(self):
        lang = language_wrapper.language_word_dict
        self._log.append(lang.get(
            "pip_downloading_python",
            "No Python found. Downloading portable Python automatically...",
        ))

        self._dl_worker = _DownloadPythonWorker()
        self._dl_worker.log.connect(self._on_log)
        self._dl_worker.finished.connect(self._on_python_downloaded)
        self._dl_worker.start()

    def _on_python_downloaded(self, success: bool, result: str):
        self._dl_worker = None
        if success:
            self._log.append(f"Portable Python ready: {result}")
            self._start_package_install(result)
        else:
            self._progress.setVisible(False)
            self._install_btn.setEnabled(True)
            self._log.append(f"\nFailed to download Python: {result}")
            self._show_no_python_error()

    def _start_package_install(self, python: str):
        self._log.append(f"Using Python: {python}")
        if _is_frozen():
            self._log.append("(Frozen/packaged environment detected)")

        pip_names = [pip for _, pip in self._missing]
        self._worker = _InstallWorker(pip_names, python)
        self._worker.log.connect(self._on_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_log(self, text: str):
        self._log.append(text)
        self._status.setText(text.split("\n")[0][:80])

    def _on_finished(self, success: bool, message: str):
        self._progress.setVisible(False)
        self._install_btn.setEnabled(True)
        self._worker = None

        if success:
            lang = language_wrapper.language_word_dict
            self._status.setText(
                lang.get("pip_install_done", "Installation complete!")
            )
            self._log.append(f"\n{message}")

            # 重新載入模組
            for import_name, _ in self._missing:
                try:
                    importlib.import_module(import_name)
                except Exception:
                    pass

            if self._on_success:
                self._on_success()
            self.accept()
        else:
            self._status.setText(f"Error: {message[:100]}")
            self._log.append(f"\nError: {message}")


# ===========================
# 公開 API
# ===========================

def ensure_dependencies(
    parent: QWidget,
    packages: list[tuple[str, str]],
    on_ready,
) -> bool:
    """檢查依賴，若缺少則彈出安裝對話框。

    Args:
        parent: Parent widget for the dialog.
        packages: [(import_name, pip_name), ...]
        on_ready: Callback invoked when all packages are available.

    Returns:
        True if already satisfied (on_ready called immediately).
    """
    missing = check_missing_packages(packages)
    if not missing:
        on_ready()
        return True

    dlg = InstallDependenciesDialog(parent, missing, on_success=on_ready)
    dlg.exec()
    return False


# ===========================
# 翻譯（合併到全域語言系統）
# ===========================

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "English": {
        "pip_install_title": "Install Dependencies",
        "pip_install_desc":
            "The following packages are required but not installed:\n\n"
            "{packages}\n\n"
            "Click Install to download and install them automatically.",
        "pip_install_btn": "Install",
        "pip_install_done": "Installation complete!",
        "pip_no_python":
            "Cannot find a Python interpreter with pip.\n\n"
            "Please install Python from https://www.python.org/downloads/\n"
            "and make sure to check 'Add Python to PATH' during installation.",
        "pip_no_python_short": "Python not found. Please install Python first.",
        "pip_downloading_python":
            "No Python found. Downloading portable Python automatically...",
        "pip_searching_python": "Searching for Python interpreter...",
    },
    "Traditional_Chinese": {
        "pip_install_title": "安裝依賴套件",
        "pip_install_desc":
            "以下套件尚未安裝：\n\n"
            "{packages}\n\n"
            "點擊安裝即可自動下載並安裝。",
        "pip_install_btn": "安裝",
        "pip_install_done": "安裝完成！",
        "pip_no_python":
            "找不到帶有 pip 的 Python 直譯器。\n\n"
            "請從 https://www.python.org/downloads/ 安裝 Python，\n"
            "安裝時請勾選「Add Python to PATH」。",
        "pip_no_python_short": "找不到 Python，請先安裝 Python。",
        "pip_downloading_python":
            "找不到 Python，正在自動下載可攜式 Python...",
        "pip_searching_python": "正在搜尋 Python 直譯器...",
    },
    "Chinese": {
        "pip_install_title": "安装依赖包",
        "pip_install_desc":
            "以下依赖包尚未安装：\n\n"
            "{packages}\n\n"
            "点击安装即可自动下载并安装。",
        "pip_install_btn": "安装",
        "pip_install_done": "安装完成！",
        "pip_no_python":
            "找不到带有 pip 的 Python 解释器。\n\n"
            "请从 https://www.python.org/downloads/ 安装 Python，\n"
            "安装时请勾选「Add Python to PATH」。",
        "pip_no_python_short": "找不到 Python，请先安装 Python。",
        "pip_downloading_python":
            "找不到 Python，正在自动下载便携版 Python...",
        "pip_searching_python": "正在搜索 Python 解释器...",
    },
    "Japanese": {
        "pip_install_title": "依存パッケージのインストール",
        "pip_install_desc":
            "以下のパッケージがインストールされていません：\n\n"
            "{packages}\n\n"
            "インストールをクリックして自動ダウンロード・インストールします。",
        "pip_install_btn": "インストール",
        "pip_install_done": "インストール完了！",
        "pip_no_python":
            "pip を持つ Python インタープリターが見つかりません。\n\n"
            "https://www.python.org/downloads/ から Python をインストールし、\n"
            "インストール時に「Add Python to PATH」にチェックしてください。",
        "pip_no_python_short":
            "Python が見つかりません。先に Python をインストールしてください。",
        "pip_downloading_python":
            "Python が見つかりません。ポータブル Python を自動ダウンロード中...",
        "pip_searching_python": "Python インタープリターを検索中...",
    },
    "Korean": {
        "pip_install_title": "의존성 패키지 설치",
        "pip_install_desc":
            "다음 패키지가 설치되지 않았습니다:\n\n"
            "{packages}\n\n"
            "설치를 클릭하면 자동으로 다운로드 및 설치됩니다.",
        "pip_install_btn": "설치",
        "pip_install_done": "설치 완료!",
        "pip_no_python":
            "pip이 포함된 Python 인터프리터를 찾을 수 없습니다.\n\n"
            "https://www.python.org/downloads/ 에서 Python을 설치하고,\n"
            "설치 시 'Add Python to PATH'를 체크해 주세요.",
        "pip_no_python_short":
            "Python을 찾을 수 없습니다. 먼저 Python을 설치해 주세요.",
        "pip_downloading_python":
            "Python을 찾을 수 없습니다. 포터블 Python을 자동 다운로드 중...",
        "pip_searching_python": "Python 인터프리터를 검색 중...",
    },
}


def register_translations() -> None:
    """將安裝對話框的翻譯合併到全域語言系統（應在 app 啟動時呼叫）。"""
    language_wrapper.merge_translations(_TRANSLATIONS)
