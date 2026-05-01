"""Manga-menu actions for the Paint workspace.

Hosts the comic / manga workflow tools that aren't a per-event
brush — currently the **Panel Cutter** dialog, which slices the
canvas into a regular ``rows × cols`` grid of cells, draws the
gutters into a fresh layer, and lets the user resume painting
inside each cell.

The dialog is intentionally minimal — rows / cols spinners + gutter
+ border slider — so a first-time user can produce a usable manga
template without learning a new vocabulary. Power users can call
:func:`Imervue.paint.manga_panels.panel_grid` directly for
non-uniform layouts.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


PANEL_ROWS_DEFAULT = 4
PANEL_COLS_DEFAULT = 1
PANEL_GUTTER_DEFAULT = 24
PANEL_BORDER_DEFAULT = 4
PANEL_MARGIN_DEFAULT = 32


def populate_manga_menu(workspace: PaintWorkspace) -> None:
    """Attach the Manga-menu actions to ``workspace``."""
    bridge = _MangaMenuBridge(workspace)
    workspace._manga_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "manga")
    lang = language_wrapper.language_word_dict
    action = menu.addAction(
        lang.get("paint_manga_panel_cutter", "Panel Cutter…"),
    )
    action.setShortcut(QKeySequence("Ctrl+Shift+P"))
    action.triggered.connect(bridge.open_panel_cutter)
    menu.addSeparator()
    tone_action = menu.addAction(
        lang.get("paint_manga_toggle_tone_layer", "Toggle Tone Layer"),
    )
    tone_action.triggered.connect(bridge.toggle_tone_layer)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _MangaMenuBridge:
    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace

    def open_panel_cutter(self) -> None:  # pragma: no cover - Qt UI
        document = self._workspace.canvas().document()
        if document.shape is None:
            return
        dialog = PanelCutterDialog(parent=self._workspace)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        params = dialog.values()
        commit_panel_layout(self._workspace, params)

    def toggle_tone_layer(self) -> None:
        """Flip the active layer between plain raster and tone-render.

        On → installs default :class:`ToneSettings` so the compositor
        starts producing the dot pattern. Off → drops the tone hint
        and the original soft greys reappear. Re-running the action
        toggles back; the layer pixels are never destructively
        rewritten.
        """
        from Imervue.paint.halftone import ToneSettings
        document = self._workspace.canvas().document()
        layer = document.active_layer()
        if layer is None:
            return
        new_tone = None if layer.tone is not None else ToneSettings()
        if document.set_layer_tone(tone=new_tone):
            self._workspace.canvas().update()


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class PanelCutterDialog(QDialog):
    """Modal dialog collecting rows / cols / gutter / border / margin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            lang.get("paint_manga_panel_cutter", "Panel Cutter…"),
        )
        self.setMinimumWidth(360)

        form = QFormLayout(self)
        self._rows = self._spin(1, 12, PANEL_ROWS_DEFAULT)
        self._cols = self._spin(1, 12, PANEL_COLS_DEFAULT)
        self._gutter = self._spin(0, 200, PANEL_GUTTER_DEFAULT)
        self._border = self._spin(0, 20, PANEL_BORDER_DEFAULT)
        self._margin = self._spin(0, 200, PANEL_MARGIN_DEFAULT)
        form.addRow(lang.get("paint_manga_rows", "Rows"), self._rows)
        form.addRow(lang.get("paint_manga_cols", "Columns"), self._cols)
        form.addRow(lang.get("paint_manga_gutter", "Gutter"), self._gutter)
        form.addRow(lang.get("paint_manga_border", "Border"), self._border)
        form.addRow(lang.get("paint_manga_margin", "Margin"), self._margin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @staticmethod
    def _spin(lo: int, hi: int, default: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(default)
        return s

    def values(self) -> dict[str, int]:
        return {
            "rows": self._rows.value(),
            "cols": self._cols.value(),
            "gutter": self._gutter.value(),
            "border": self._border.value(),
            "margin": self._margin.value(),
        }


# ---------------------------------------------------------------------------
# Commit — pure logic, callable from tests without a dialog
# ---------------------------------------------------------------------------


def commit_panel_layout(
    workspace: PaintWorkspace, params: dict[str, int],
) -> bool:
    """Add a Panels layer that draws the requested grid.

    Returns ``True`` if a layer was added (parameters were valid for
    the canvas size), ``False`` otherwise. Pure-numpy logic so the
    test suite can exercise both branches without a Qt dialog.
    """
    import numpy as np

    from Imervue.paint.manga_panels import draw_panel_borders, panel_grid

    document = workspace.canvas().document()
    if document.shape is None:
        return False
    h, w = document.shape
    try:
        layout = panel_grid(
            width=w, height=h,
            rows=int(params["rows"]),
            cols=int(params["cols"]),
            gutter=int(params["gutter"]),
            border_width=int(params["border"]),
            margin=int(params["margin"]),
        )
    except (KeyError, ValueError):
        return False
    layer_canvas = np.zeros((h, w, 4), dtype=np.uint8)
    draw_panel_borders(layer_canvas, layout)
    layer = document.add_layer(name="Panels")
    np.copyto(layer.image, layer_canvas)
    document.invalidate_composite()
    workspace.canvas().update()
    return True
