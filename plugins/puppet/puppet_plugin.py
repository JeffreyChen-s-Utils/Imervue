"""Puppet plugin — top-level tab for the from-scratch 2D rigged
animation system.

Phase 0 ships only the tab skeleton: a placeholder QWidget that lands
in the main window's tab strip after Paint. Subsequent phases fill in
the file format, renderer, mesh editor, parameter rig, motion timeline,
physics, and runtime tracking — see ``~/.claude/plans/wise-whistling-church.md``
for the full roadmap.

Plugin-vs-main rationale: Puppet pulls in numpy-heavy mesh deformation
plus optional ``sounddevice`` / ``mediapipe`` deps for lip-sync and
webcam tracking. Per ``CLAUDE.md`` plugin guidance (heavy deps, failure
isolation, independent release cadence) it lives outside the main
package.
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
    plugin_version = "0.1.0"
    plugin_description = (
        "From-scratch 2D rigged-puppet animation tab "
        "(placeholder; see roadmap for upcoming phases)."
    )
    plugin_author = "Imervue"

    def __init__(self, main_window):
        super().__init__(main_window)
        self._tab_widget = None

    def on_build_main_tabs(self, tabs: QTabWidget) -> None:
        widget = _build_placeholder_widget()
        lang = language_wrapper.language_word_dict
        title = lang.get("puppet_tab_title", "Puppet")
        tabs.addTab(widget, title)
        self._tab_widget = widget
        logger.info("Puppet tab installed at index %d", tabs.indexOf(widget))


def _build_placeholder_widget():
    """Construct the Phase 0 placeholder. Pulled out so unit tests can
    instantiate the widget directly without spinning up a full plugin."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lang = language_wrapper.language_word_dict
    headline = QLabel(lang.get("puppet_tab_title", "Puppet"))
    headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
    headline.setStyleSheet("font-size: 24px; font-weight: 600;")
    subtitle = QLabel(
        lang.get(
            "puppet_placeholder_subtitle",
            "From-scratch 2D rigged animation — coming soon.",
        ),
    )
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setStyleSheet("color: #888; padding-top: 8px;")
    layout.addWidget(headline)
    layout.addWidget(subtitle)
    return widget
