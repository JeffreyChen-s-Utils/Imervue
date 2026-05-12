"""Puppet plugin — top-level tab for the from-scratch 2D rigged
animation system.

Mounts the workspace as the **Puppet** tab via the plugin manager's
``on_build_main_tabs`` hook so the heavy GL / mesh / optional
``simple_lama_inpainting`` ML deps stay outside the main package and
a failure in any of them can't take down the main viewer.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from PySide6.QtWidgets import QTabWidget

logger = logging.getLogger("Imervue.plugin.puppet")


class PuppetPlugin(ImervuePlugin):
    plugin_name = "Puppet"
    plugin_version = "0.2.0"
    plugin_description = (
        "From-scratch 2D rigged-puppet animation tab "
        "with deformers, parameters, motions, physics, and live input."
    )
    plugin_author = "Imervue"

    def __init__(self, main_window):
        super().__init__(main_window)
        self._tab_widget = None

    def on_build_main_tabs(self, tabs: QTabWidget) -> None:
        widget = _build_workspace_widget()
        lang = language_wrapper.language_word_dict
        title = lang.get("puppet_tab_title", "Puppet")
        tabs.addTab(widget, title)
        self._tab_widget = widget
        logger.info("Puppet tab installed at index %d", tabs.indexOf(widget))


def _build_workspace_widget():
    """Build the workspace widget that the plugin docks into the tab.

    Pulled out so unit tests can instantiate without going through
    ``PuppetPlugin.__init__`` (which needs an ImervueMainWindow).
    """
    from puppet.workspace import PuppetWorkspace

    return PuppetWorkspace()
