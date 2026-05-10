"""Top-level Puppet workspace — QMainWindow that hosts the canvas,
toolbar, recent files, parameter dock, and (future) timeline /
expression / physics docks.

Recent puppet paths are persisted to
``user_setting_dict["puppet_recent_files"]`` so they survive across
launches; missing files are pruned silently the next time the menu is
rebuilt (matches the recent-folder behaviour in
``Imervue/menu/recent_menu.py``).
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStatusBar,
    QToolBar,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict
from puppet.auto_mesh import DEFAULT_CELL_SIZE, puppet_from_png
from puppet.canvas import PuppetCanvas
from puppet.document_io import PuppetFormatError, load_puppet
from puppet.parameter_dock import ParameterDock

logger = logging.getLogger("Imervue.plugin.puppet.workspace")

_RECENT_KEY = "puppet_recent_files"
_RECENT_LIMIT = 10


class PuppetWorkspace(QMainWindow):
    """Top-level QMainWindow hosted by the Puppet plugin tab.

    Inherits from QMainWindow so QToolBar / QDockWidget / QStatusBar
    plug in via the standard Qt APIs (matches the pattern used by
    ``Imervue/paint/paint_workspace.py``).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # The window flag keeps QMainWindow from being treated as a
        # real top-level window when embedded in a tab.
        self.setWindowFlags(Qt.WindowType.Widget)

        self._canvas = PuppetCanvas(self)
        self.setCentralWidget(self._canvas)

        self.addToolBar(self._build_toolbar())

        self._parameter_dock = ParameterDock(self._canvas, self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._parameter_dock,
        )

        self._status_label = QLabel("")
        bar = QStatusBar()
        bar.addWidget(self._status_label, stretch=1)
        self.setStatusBar(bar)
        self._refresh_status_for_no_document()

    def canvas(self) -> PuppetCanvas:
        return self._canvas

    def parameter_dock(self) -> ParameterDock:
        return self._parameter_dock

    # ---- toolbar --------------------------------------------------------

    def _build_toolbar(self) -> QToolBar:
        lang = language_wrapper.language_word_dict
        bar = QToolBar(lang.get("puppet_toolbar_title", "Puppet"), self)
        bar.setMovable(False)

        open_action = QAction(lang.get("puppet_open", "Open Puppet…"), self)
        open_action.triggered.connect(self._open_via_dialog)
        bar.addAction(open_action)

        import_action = QAction(lang.get("puppet_import_png", "Import PNG…"), self)
        import_action.triggered.connect(self._import_png_via_dialog)
        bar.addAction(import_action)

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
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_open_failed", "Failed to open puppet: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._canvas.load_document(doc)
        self._status_label.setText(
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

    # ---- import PNG -----------------------------------------------------

    def _import_png_via_dialog(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_import_png_title", "Import PNG"),
            "",
            "PNG (*.png);;Images (*.png *.jpg *.jpeg *.bmp *.tiff)",
        )
        if not path:
            return
        cell_size = self._prompt_cell_size()
        if cell_size is None:
            return
        self.import_png(path, cell_size=cell_size)

    def _prompt_cell_size(self) -> int | None:
        lang = language_wrapper.language_word_dict
        value, ok = QInputDialog.getInt(
            self,
            lang.get("puppet_cell_size_title", "Mesh density"),
            lang.get(
                "puppet_cell_size_prompt",
                "Cell size in pixels (smaller = denser mesh):",
            ),
            DEFAULT_CELL_SIZE, 4, 1024, 4,
        )
        return value if ok else None

    def import_png(self, path: str | Path, *, cell_size: int = DEFAULT_CELL_SIZE) -> bool:
        """Build a single-drawable puppet from ``path``'s PNG and load
        it into the canvas. Returns ``True`` on success."""
        try:
            doc = puppet_from_png(path, cell_size=cell_size)
        except (FileNotFoundError, ValueError, OSError) as exc:
            logger.warning("PNG import failed for %s: %s", path, exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_import_failed",
                    "PNG import failed: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._canvas.load_document(doc)
        n_verts = len(doc.drawables[0].vertices)
        n_tris = len(doc.drawables[0].indices) // 3
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_imported",
                "Imported {name} ({w}×{h}, {v} vertices, {t} triangles)",
            ).format(
                name=Path(str(path)).name,
                w=doc.size[0], h=doc.size[1],
                v=n_verts, t=n_tris,
            ),
        )
        return True

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
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_empty",
                "No puppet loaded — use Open to load a .puppet file.",
            ),
        )

    # ---- compatibility shim for older tests / callers -------------------
    # Phase 0–3 tests reach into ``_status`` for status-text assertions;
    # the QMainWindow now exposes that through the QStatusBar's label.
    @property
    def _status(self) -> QLabel:
        return self._status_label


def _push_recent(path: str) -> None:
    """Move ``path`` to the front of the recent-files list, dedupe,
    truncate to ``_RECENT_LIMIT``."""
    existing = [p for p in user_setting_dict.get(_RECENT_KEY, []) if p != path]
    existing.insert(0, path)
    user_setting_dict[_RECENT_KEY] = existing[:_RECENT_LIMIT]
