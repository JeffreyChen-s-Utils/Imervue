"""GPU Develop: batch export renders Develop recipes on the discrete GPU.

The plugin registers a develop backend (``Imervue.image.develop_backends``)
that Batch Export offers under *Render on*. It needs ``wgpu`` (installed from
the Plugins menu entry on first use) and a discrete GPU: integrated GPUs and
software adapters are never used, and a machine without a discrete GPU keeps
rendering on the CPU. Every window loads its own instance of the plugin; the
backend stays registered while any of them is loaded.
"""
from __future__ import annotations

import importlib.util
import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from Imervue.image import develop_backends
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.pip_installer import ensure_dependencies
from Imervue.plugin.plugin_base import ImervuePlugin

from gpu_develop.renderer import GpuDevelopRenderer, probe
from gpu_develop.translations import TRANSLATIONS

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMenu

logger = logging.getLogger("Imervue.plugin.gpu_develop")

BACKEND_KEY = "gpu_develop"
REQUIRED_PACKAGES = [("wgpu", "wgpu")]
PROVIDER = develop_backends.BackendProvider(key=BACKEND_KEY, probe=probe, open=GpuDevelopRenderer)

_live: set[int] = set()


def _tr(key: str, default: str) -> str:
    return language_wrapper.language_word_dict.get(key, default)


def wgpu_installed() -> bool:
    """Whether the ``wgpu`` package can be imported."""
    try:
        return importlib.util.find_spec("wgpu") is not None
    except (ImportError, ValueError):   # a broken spec
        return False


def status_text(gpu: str | None) -> str:
    """What the status box says: the GPU batch export will use, or why it renders on the CPU."""
    if gpu:
        return _tr("gpu_develop_found",
                   "Batch Export can render Develop recipes on {gpu}. Choose it under "
                   "“Render on” in the Batch Export dialog.").format(gpu=gpu)
    return _tr("gpu_develop_none",
               "No discrete GPU was found. Integrated GPUs are not used, so Batch Export "
               "renders Develop recipes on the CPU.")


class GpuDevelopPlugin(ImervuePlugin):
    """Registers the GPU develop backend and a Plugins-menu status entry."""

    plugin_name = "GPU Develop"
    plugin_version = "1.0.0"
    plugin_description = "Batch export renders Develop recipes on the discrete GPU"
    plugin_author = "JE Chen"

    def on_plugin_loaded(self) -> None:
        _live.add(id(self))
        develop_backends.register(PROVIDER)

    def on_plugin_unloaded(self) -> None:
        _live.discard(id(self))
        if not _live:
            develop_backends.unregister(BACKEND_KEY)

    def get_translations(self) -> dict[str, dict[str, str]]:
        return TRANSLATIONS

    def on_build_menu_bar(self, plugin_menu: QMenu) -> None:
        action = plugin_menu.addAction(_tr("gpu_develop_menu", "GPU Develop…"))
        action.triggered.connect(self._show_status)

    def _show_status(self) -> None:
        """Install wgpu when missing, then say which GPU batch export uses."""
        if not wgpu_installed():
            ensure_dependencies(self.main_window, REQUIRED_PACKAGES, self._report)
            return
        self._report()

    def _report(self) -> None:
        QMessageBox.information(self.main_window, _tr("gpu_develop_title", "GPU Develop"),
                                status_text(probe()))
