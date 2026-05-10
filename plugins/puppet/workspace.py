"""Top-level Puppet workspace widget.

Phase 2: a toolbar with Open / Recent buttons sitting above a
``PuppetCanvas``. Recent puppet paths are persisted to
``user_setting_dict["puppet_recent_files"]`` so they survive across
launches; missing files are pruned silently the next time the menu is
rebuilt (matches the recent-folder behaviour in
``Imervue/menu/recent_menu.py``).

Later phases dock parameter panels and motion timelines onto this
widget — the workspace is the parent for all Puppet UI.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict
from puppet.canvas import PuppetCanvas
from puppet.document_io import PuppetFormatError, load_puppet

logger = logging.getLogger("Imervue.plugin.puppet.workspace")

_RECENT_KEY = "puppet_recent_files"
_RECENT_LIMIT = 10


class PuppetWorkspace(QWidget):
    """Top-level widget hosted by the Puppet plugin tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())
        self._canvas = PuppetCanvas(self)
        layout.addWidget(self._canvas, stretch=1)
        self._status = _build_status_label()
        layout.addWidget(self._status)
        self._refresh_status_for_no_document()

    def canvas(self) -> PuppetCanvas:
        return self._canvas

    # ---- toolbar --------------------------------------------------------

    def _build_toolbar(self) -> QToolBar:
        lang = language_wrapper.language_word_dict
        bar = QToolBar(lang.get("puppet_toolbar_title", "Puppet"), self)
        bar.setMovable(False)

        open_action = QAction(lang.get("puppet_open", "Open Puppet…"), self)
        open_action.triggered.connect(self._open_via_dialog)
        bar.addAction(open_action)

        self._recent_button = QPushButton(lang.get("puppet_recent", "Recent"))
        self._recent_button.setFlat(True)
        self._recent_menu = QMenu(self._recent_button)
        self._recent_button.setMenu(self._recent_menu)
        self._recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        bar.addWidget(self._recent_button)

        bar.addSeparator()

        fit_action = QAction(lang.get("puppet_fit_view", "Fit to Window"), self)
        fit_action.triggered.connect(self._canvas_reset_view)
        bar.addAction(fit_action)

        return bar

    # ---- file ops -------------------------------------------------------

    def _open_via_dialog(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_open_dialog_title", "Open Puppet"),
            "",
            "Puppet (*.puppet)",
        )
        if not path:
            return
        self.open_puppet(path)

    def open_puppet(self, path: str | Path) -> bool:
        """Load ``path`` into the canvas. Returns ``True`` on success."""
        path_str = str(path)
        try:
            doc = load_puppet(path_str)
        except (FileNotFoundError, PuppetFormatError) as exc:
            logger.warning("failed to open puppet %s: %s", path_str, exc)
            self._status.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_open_failed", "Failed to open puppet: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._canvas.load_document(doc)
        self._status.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_loaded",
                "Loaded {name} ({w}×{h}, {n} drawables)",
            ).format(
                name=Path(path_str).name,
                w=doc.size[0], h=doc.size[1],
                n=len(doc.drawables),
            ),
        )
        _push_recent(path_str)
        return True

    def _canvas_reset_view(self) -> None:
        self._canvas.reset_view()

    # ---- recent menu ----------------------------------------------------

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        lang = language_wrapper.language_word_dict
        valid: list[str] = []
        for path in user_setting_dict.get(_RECENT_KEY, []):
            if Path(path).is_file():
                valid.append(path)
                action = self._recent_menu.addAction(Path(path).name)
                action.setToolTip(path)
                action.triggered.connect(
                    lambda _checked=False, p=path: self.open_puppet(p),
                )
        user_setting_dict[_RECENT_KEY] = valid
        if not valid:
            empty = self._recent_menu.addAction(
                lang.get("puppet_recent_empty", "(No recent puppets)"),
            )
            empty.setEnabled(False)

    # ---- status ---------------------------------------------------------

    def _refresh_status_for_no_document(self) -> None:
        self._status.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_empty",
                "No puppet loaded — use Open to load a .puppet file.",
            ),
        )


def _build_status_label() -> QLabel:
    label = QLabel("")
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    label.setStyleSheet("padding: 4px 8px; color: #aaa; background: #1a1a1c;")
    return label


def _push_recent(path: str) -> None:
    """Move ``path`` to the front of the recent-files list, dedupe,
    truncate to ``_RECENT_LIMIT``."""
    existing = [p for p in user_setting_dict.get(_RECENT_KEY, []) if p != path]
    existing.insert(0, path)
    user_setting_dict[_RECENT_KEY] = existing[:_RECENT_LIMIT]


# ---- helper layouts (kept here so tests can grab them without Qt) -------

def _flank(left: QWidget, right: QWidget) -> QWidget:
    """Compose a QWidget with ``left`` and ``right`` side-by-side. Used
    by future phases to hang docks beside the canvas; kept module-level
    so tests can exercise the layout glue without spinning a workspace."""
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(left)
    row.addWidget(right, stretch=1)
    return holder
