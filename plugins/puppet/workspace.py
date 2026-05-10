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
from puppet.document_io import PuppetFormatError, load_puppet, save_puppet
from puppet.operations import (
    add_parameter,
    add_rotation_deformer,
    add_warp_deformer,
    remove_key,
    set_key_at_value,
    snapshot_current_forms,
)
from puppet.input_engine import InputEngine
from puppet.motion_dock import MotionDock
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

        self._parameter_dock = ParameterDock(self._canvas, self, workspace=self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._parameter_dock,
        )

        self._motion_dock = MotionDock(self._canvas, self)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self._motion_dock,
        )

        self._input_engine = InputEngine(self._canvas, self)

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

        save_action = QAction(lang.get("puppet_save_as", "Save As…"), self)
        save_action.triggered.connect(self._save_via_dialog)
        bar.addAction(save_action)

        bar.addSeparator()

        add_rot_action = QAction(
            lang.get("puppet_add_rotation", "Add Rotation Deformer"), self,
        )
        add_rot_action.triggered.connect(self._add_rotation_deformer)
        bar.addAction(add_rot_action)

        add_warp_action = QAction(
            lang.get("puppet_add_warp", "Add Warp Deformer"), self,
        )
        add_warp_action.triggered.connect(self._add_warp_deformer)
        bar.addAction(add_warp_action)

        add_param_action = QAction(
            lang.get("puppet_add_parameter", "Add Parameter"), self,
        )
        add_param_action.triggered.connect(self._add_parameter)
        bar.addAction(add_param_action)

        bar.addSeparator()

        self._drag_toggle = QAction(
            lang.get("puppet_drag_track", "Drag-track head"), self,
        )
        self._drag_toggle.setCheckable(True)
        self._drag_toggle.toggled.connect(self._toggle_drag)
        bar.addAction(self._drag_toggle)

        self._blink_toggle = QAction(
            lang.get("puppet_auto_blink", "Auto-blink"), self,
        )
        self._blink_toggle.setCheckable(True)
        self._blink_toggle.toggled.connect(self._toggle_blink)
        bar.addAction(self._blink_toggle)

        self._lipsync_toggle = QAction(
            lang.get("puppet_lipsync", "Mic lip-sync"), self,
        )
        self._lipsync_toggle.setCheckable(True)
        self._lipsync_toggle.toggled.connect(self._toggle_lipsync)
        bar.addAction(self._lipsync_toggle)

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

    # ---- save -----------------------------------------------------------

    def _save_via_dialog(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            return
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("puppet_save_dialog_title", "Save Puppet As"),
            "",
            "Puppet (*.puppet)",
        )
        if not path:
            return
        if not path.lower().endswith(".puppet"):
            path = f"{path}.puppet"
        self.save_puppet(path)

    def save_puppet(self, path: str | Path) -> bool:
        doc = self._canvas.document()
        if doc is None:
            return False
        try:
            save_puppet(doc, path)
        except OSError as exc:
            logger.warning("puppet save failed: %s", exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_save_failed", "Save failed: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_save_done", "Saved to {name}",
            ).format(name=Path(str(path)).name),
        )
        _push_recent(str(path))
        return True

    # ---- editor authoring ----------------------------------------------

    def _add_rotation_deformer(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            return
        deformer_id = self._unique_deformer_id("rotation")
        if add_rotation_deformer(doc, deformer_id):
            self._canvas.load_document(doc)
            self._announce(
                "puppet_added_deformer", "Added deformer {id}",
                id=deformer_id,
            )

    def _add_warp_deformer(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            return
        deformer_id = self._unique_deformer_id("warp")
        if add_warp_deformer(doc, deformer_id):
            self._canvas.load_document(doc)
            self._announce(
                "puppet_added_deformer", "Added deformer {id}",
                id=deformer_id,
            )

    def _add_parameter(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            return
        param_id = self._unique_parameter_id("Param")
        if add_parameter(doc, param_id):
            # Force the dock to rebuild itself by replaying load_document
            self._canvas.load_document(doc)
            self._announce(
                "puppet_added_parameter", "Added parameter {id}",
                id=param_id,
            )

    def set_key_at_current_slider(self, param_id: str) -> bool:
        """Snapshot current deformer forms at the slider's current
        value and write them as a key on ``param_id``. Wired by the
        parameter dock's per-row Set Key button."""
        doc = self._canvas.document()
        if doc is None:
            return False
        value = self._canvas.parameter_values().get(param_id)
        if value is None:
            return False
        forms = snapshot_current_forms(doc)
        ok = set_key_at_value(doc, param_id, value, forms)
        if ok:
            self._announce(
                "puppet_key_set", "Set key on {id} at {value:.2f}",
                id=param_id, value=value,
            )
        return ok

    def remove_key_at_current_slider(self, param_id: str) -> bool:
        doc = self._canvas.document()
        if doc is None:
            return False
        value = self._canvas.parameter_values().get(param_id)
        if value is None:
            return False
        ok = remove_key(doc, param_id, value)
        if ok:
            self._canvas.load_document(doc)   # re-evaluate at neutral keys
            self._canvas.set_parameter_value(param_id, value)
            self._announce(
                "puppet_key_removed", "Removed key from {id} at {value:.2f}",
                id=param_id, value=value,
            )
        return ok

    # ---- helpers --------------------------------------------------------

    def _unique_deformer_id(self, prefix: str) -> str:
        doc = self._canvas.document()
        existing = {d.id for d in (doc.deformers if doc else [])}
        i = 1
        while True:
            candidate = f"{prefix}_{i}"
            if candidate not in existing:
                return candidate
            i += 1

    def _unique_parameter_id(self, prefix: str) -> str:
        doc = self._canvas.document()
        existing = {p.id for p in (doc.parameters if doc else [])}
        i = 1
        while True:
            candidate = f"{prefix}{i}"
            if candidate not in existing:
                return candidate
            i += 1

    def _announce(self, key: str, fallback: str, **fmt) -> None:
        self._status_label.setText(
            language_wrapper.language_word_dict.get(key, fallback).format(**fmt),
        )

    # ---- live input toggles --------------------------------------------

    def _toggle_drag(self, enabled: bool) -> None:
        self._input_engine.set_drag_enabled(enabled)

    def _toggle_blink(self, enabled: bool) -> None:
        self._input_engine.set_blink_enabled(enabled)

    def _toggle_lipsync(self, enabled: bool) -> None:
        ok = self._input_engine.set_lipsync_enabled(enabled)
        if enabled and not ok:
            # sounddevice missing or mic open failed — bounce the toggle
            self._lipsync_toggle.blockSignals(True)
            self._lipsync_toggle.setChecked(False)
            self._lipsync_toggle.blockSignals(False)
            self._announce(
                "puppet_lipsync_unavailable",
                "Lip-sync unavailable (install sounddevice for mic input)",
            )

    def input_engine(self) -> InputEngine:
        return self._input_engine

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
