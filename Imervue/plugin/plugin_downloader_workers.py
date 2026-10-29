"""Background workers of the plugin downloader: fetch the listing, install one plugin.

The network helpers (``_https_urlopen``, ``_github_get``, ``_get_plugin_dir``), the
listing walk and the path check are read from :mod:`plugin_downloader` at call
time, where the https guard lives and where tests patch them.
"""
from __future__ import annotations

import logging
import urllib.request

from PySide6.QtCore import QThread, Signal

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_api import PLUGIN_API_VERSION, IncompatiblePluginError, check_compatible
from Imervue.system.job_state import JobState
from Imervue.plugin.installation import installation_stage, commit_installation
from Imervue.plugin.status import status_registry

logger = logging.getLogger("Imervue.plugin.downloader")

# Failures a fetch or download is expected to meet: network and HTTP errors and
# disk errors (``OSError``), bad JSON or a truncated listing (``ValueError``), a
# listing of the wrong shape (``TypeError``, ``KeyError``). Anything else is a bug
# and is logged with its traceback.
_EXPECTED_FETCH_ERRORS = (OSError, ValueError, TypeError, KeyError)


def needs_newer_text(error: IncompatiblePluginError) -> str:
    """The status-line text for a plugin this Imervue is too old to run."""
    return language_wrapper.language_word_dict.get(
        "plugin_dl_needs_newer",
        "{name} needs a newer Imervue (plugin API {needed}; this one has {have}). "
        "Update Imervue, then download it again.",
    ).format(name=error.plugin, needed=error.needed, have=PLUGIN_API_VERSION)


# ================================================================
# Worker: fetch available plugins list from GitHub
# ================================================================

class FetchPluginListWorker(QThread):
    result_ready = Signal(list)  # [(category, plugin_name, [file_info, ...])]
    error = Signal(str)

    def run(self):
        try:
            # Read at call time: the network helpers live in plugin_downloader.
            from Imervue.plugin import plugin_downloader as downloader
            tree = downloader._github_get(downloader.REPO_TREE_URL)
            if not isinstance(tree, dict):
                raise TypeError("Unexpected plugin repository listing")
            self.result_ready.emit(downloader.parse_plugin_tree(tree))
        except _EXPECTED_FETCH_ERRORS as e:
            self.error.emit(str(e))
        except Exception as e:
            # Worker boundary: the dialog waits on a signal, so report even a bug.
            logger.exception("Fetching the plugin list failed unexpectedly")
            self.error.emit(str(e))


# ================================================================
# Worker: download a single plugin
# ================================================================

class DownloadPluginWorker(QThread):
    progress = Signal(int, int)  # (current, total)
    result_ready = Signal(str)       # plugin_name
    error = Signal(str)

    def __init__(self, plugin_name: str, file_infos: list[dict], parent=None):
        super().__init__(parent)
        self.plugin_name = plugin_name
        self.file_infos = [dict(info) for info in file_infos]
        self.job_state = JobState([plugin_name])
        self._status_key = "download:" + plugin_name

    def run(self):
        try:
            # Read at call time: the https guard and plugin dir live in plugin_downloader.
            from Imervue.plugin import plugin_downloader as downloader
            names = [self.plugin_name, *(info["name"] for info in self.file_infos)]
            unsafe = [n for n in names if not downloader.is_safe_path_component(n)]
            if unsafe:
                raise ValueError(f"Refusing unsafe plugin path: {unsafe[0]!r}")
            plugin_root = downloader._get_plugin_dir()
            plugin_root.mkdir(parents=True, exist_ok=True)
            final_dir = plugin_root / self.plugin_name
            with installation_stage(final_dir) as tmp_dir:
                status_registry.publish(self._status_key, self.plugin_name, "downloading")
                total = len(self.file_infos)
                for i, info in enumerate(self.file_infos):
                    self._check_cancelled()
                    url = info["download_url"]
                    dest = tmp_dir / info["name"]
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    req = urllib.request.Request(url)
                    with downloader._https_urlopen(req, timeout=30) as resp:
                        dest.write_bytes(resp.read())
                    self.job_state.progress(i + 1, total)
                    self.progress.emit(i + 1, total)
                # Refused before the swap, so a working install stays as it was.
                self._check_cancelled()
                check_compatible(tmp_dir, self.plugin_name)
                commit_installation(tmp_dir, final_dir, before_commit=self._check_cancelled)
            status_registry.publish(self._status_key, self.plugin_name, "installed",
                                    "Reload Plugins in each open window to activate the new code")
            self.job_state.record(self.plugin_name, output=str(final_dir))
            self.result_ready.emit(self.plugin_name)
        except InterruptedError:
            self.job_state.request_cancel()
            status_registry.publish(self._status_key, self.plugin_name, "cancelled")
        except IncompatiblePluginError as e:
            self._report_error(needs_newer_text(e))
        except _EXPECTED_FETCH_ERRORS as e:
            self._report_error(str(e) or type(e).__name__)
        except Exception as e:
            logger.exception("Downloading plugin %s failed unexpectedly", self.plugin_name)
            self._report_error(str(e) or type(e).__name__)
        finally:
            self.job_state.finish()

    def _report_error(self, message: str) -> None:
        status_registry.publish(self._status_key, self.plugin_name, "failed", message)
        self.job_state.record(self.plugin_name, error=message)
        self.error.emit(message)

    def _check_cancelled(self) -> None:
        if self.isInterruptionRequested() or self.job_state.cancelled:
            raise InterruptedError("Plugin download cancelled")

    def stop(self) -> None:
        """Request cancellation between requests without removing a working plugin."""
        self.job_state.request_cancel()


def _retry_download(paths: tuple[str, ...], *,
                    file_infos: tuple[dict, ...]) -> DownloadPluginWorker:
    """A plugin is one atomic install item; committed plugins are never retried."""
    return DownloadPluginWorker(paths[0], list(file_infos))
