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

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from urllib.request import urlopen, Request

from PySide6.QtCore import Qt, QCoreApplication, QObject, QThread, Signal
from shiboken6 import isValid

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.status import status_registry
from Imervue.plugin.worker_retirement import retire_workers
# Plugins in Imervue_Plugins import ``_find_python`` from this module
# (architecture.md §6), and tests reach the probe through it, so the finder's
# names stay importable here.
from Imervue.plugin.python_finder import (  # noqa: F401 - re-exported for plugins and tests
    _PYTHON_EXE_NAME,
    _VERIFY_TIMEOUT_S,
    _embedded_python_dir,
    _embedded_python_exe,
    _find_python,
    _subprocess_kwargs,
    _verify_python,
)
from Imervue.system.app_paths import (
    ensure_frozen_site_packages_on_path as _ensure_frozen_site_packages_on_path,
)
# The embedded-Python download, the workers and the dialog live in sibling
# modules; their names stay importable here for callers, plugins and tests.
from Imervue.plugin.pip_embed_python import (
    _EMBED_PYTHON_SHA256,
    _EMBED_PYTHON_URL,
    _EMBED_PYTHON_VERSION,
    _PIP_FROM_WHEEL,
    _PIP_WHEEL_NAME,
    _PIP_WHEEL_SHA256,
    _PIP_WHEEL_URL,
    _PIP_WHEEL_VERSION,
    _PROCESS_TIMEOUT_MSG,
    _PTH_NAME_RE,
    _UA_HEADERS,
    _USER_AGENT,
    _DownloadPythonWorker,
    _matches_sha256,
)
from Imervue.plugin.pip_install_workers import (
    _CheckDepsWorker,
    _FindPythonWorker,
    _ImportWorker,
    _InstallWorker,
    _check_missing_frozen,
    _is_frozen,
    check_missing_packages,
)
from Imervue.plugin.pip_install_dialog import InstallDependenciesDialog

__all__ = [
    "InstallDependenciesDialog",
    "_CheckDepsWorker",
    "_DownloadPythonWorker",
    "_EMBED_PYTHON_SHA256",
    "_EMBED_PYTHON_URL",
    "_EMBED_PYTHON_VERSION",
    "_EnsureDepsHelper",
    "_FindPythonWorker",
    "_ImportWorker",
    "_InstallWorker",
    "_PIP_FROM_WHEEL",
    "_PIP_WHEEL_NAME",
    "_PIP_WHEEL_SHA256",
    "_PIP_WHEEL_URL",
    "_PIP_WHEEL_VERSION",
    "_PROCESS_TIMEOUT_MSG",
    "_PTH_NAME_RE",
    "_PYTHON_EXE_NAME",
    "_TRANSLATIONS",
    "_UA_HEADERS",
    "_USER_AGENT",
    "_VERIFY_TIMEOUT_S",
    "_check_missing_frozen",
    "_embedded_python_dir",
    "_embedded_python_exe",
    "_find_python",
    "_https_urlopen",
    "_is_frozen",
    "_matches_sha256",
    "_subprocess_kwargs",
    "_verify_python",
    "check_missing_packages",
    "ensure_dependencies",
    "register_translations",
]


def _https_urlopen(req: Request, timeout: int):
    """urlopen that refuses any scheme other than https.

    The installer's URLs are hardcoded https:// endpoints (python.org,
    pythonhosted.org, see ``pip_embed_python``), but this guard makes the
    scheme explicit so bandit B310 and future maintainers both see that
    non-https is rejected.
    """
    scheme = urlparse(req.full_url).scheme
    if scheme != "https":
        raise ValueError(f"Refusing non-https URL scheme: {scheme!r}")
    return urlopen(req, timeout=timeout)  # nosec B310  # scheme validated above

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

logger = logging.getLogger("Imervue.plugin.pip_installer")


# ===========================
# 環境偵測
# ===========================

# 啟動時：若為凍結環境，確保 lib/site-packages 在 sys.path 上。
# 這個函式已在 app_paths 模組被載入時就跑過一次，這裡再呼叫只是保險 —
# 若使用者透過其他路徑（例如先於 app_paths 被載入的自訂 entry point）進來，
# 仍然能保證安裝過的套件可以被 import。
_ensure_frozen_site_packages_on_path()


# ===========================
# 公開 API
# ===========================

class _EnsureDepsHelper(QObject):
    """協調 ensure_dependencies 的背景檢查流程。

    用 QObject 包裝，讓所有 signal-slot 連接都在 QObject 之間進行，
    Qt 的 AutoConnection 會自動根據執行緒使用 QueuedConnection。
    QApplication 持有此物件，parent 被刪除也不會銷毀執行中的 QThread。
    """
    _relay = Signal(list)

    def __init__(self, parent: QWidget, packages, on_ready):
        super().__init__(QCoreApplication.instance())
        self._parent_widget = parent
        self._on_ready = on_ready
        self._status_key = "dependencies:" + ",".join(sorted(imp for imp, _pip in packages))
        status_registry.publish(self._status_key, "Dependencies", "checking")

        logger.info("_EnsureDepsHelper.__init__: parent=%s, packages=%s", parent, packages)

        # _relay 是 QObject-to-QObject 的 signal，AutoConnection 安全跨執行緒
        self._relay.connect(self._handle_result)

        self._worker = _CheckDepsWorker(packages, parent=self)
        self._worker.result_ready.connect(self._relay)
        self._worker.finished.connect(self._cleanup)

        logger.info("_EnsureDepsHelper: starting worker")
        self._worker.start()
        logger.info("_EnsureDepsHelper: worker started")

    def _handle_result(self, missing: list[tuple[str, str]]):
        logger.info("_EnsureDepsHelper._handle_result: missing=%s (thread=%s)",
                     missing, QThread.currentThread())
        try:
            if not isValid(self._parent_widget):
                status_registry.publish(self._status_key, "Dependencies", "cancelled")
                return
            status_registry.publish(self._status_key, "Dependencies",
                                    "missing" if missing else "available",
                                    ", ".join(pip for _imp, pip in missing))
            if not missing:
                logger.info("_EnsureDepsHelper: no missing deps, calling on_ready")
                self._ready()
                logger.info("_EnsureDepsHelper: on_ready returned")
                return
            logger.info("_EnsureDepsHelper: missing deps found, opening install dialog")
            dlg = InstallDependenciesDialog(
                self._parent_widget, missing, on_success=self._ready,
            )
            dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dlg.open()
            logger.info("_EnsureDepsHelper: install dialog opened")
        except Exception:
            logger.exception("_EnsureDepsHelper._handle_result failed")

    def _ready(self) -> None:
        try:
            if not isValid(self._parent_widget):
                status_registry.publish(self._status_key, "Dependencies", "cancelled")
                return
            self._on_ready()
        except Exception as exc:
            status_registry.publish(self._status_key, "Dependencies", "failed",
                                    str(exc) or type(exc).__name__)
            raise
        status_registry.publish(self._status_key, "Dependencies", "available")

    def _cleanup(self):
        logger.info("_EnsureDepsHelper._cleanup: worker finished")
        worker, self._worker = self._worker, None
        if worker is not None:
            retire_workers(self, [worker], self.deleteLater, cancel=False)
        else:
            self.deleteLater()


def ensure_dependencies(
    parent: QWidget,
    packages: list[tuple[str, str]],
    on_ready,
) -> None:
    """檢查依賴，若缺少則彈出安裝對話框（完全非阻塞）。

    Args:
        parent: Parent widget for the dialog.
        packages: [(import_name, pip_name), ...]
        on_ready: Callback invoked when all packages are available.
    """
    _EnsureDepsHelper(parent, packages, on_ready)


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
