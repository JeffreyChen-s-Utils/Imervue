"""Edit-menu actions for the Paint workspace.

Phase 24e introduces the Edit menu with a single Quick Mask Mode
toggle — future selection / clipboard verbs (Cut, Copy, Paste,
Select All) plug in here too.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.paint_menu_bar import menu_for
from Imervue.paint.stroke_selection import (
    DEFAULT_PLACEMENT,
    MAX_STROKE_WIDTH,
    MIN_STROKE_WIDTH,
    STROKE_PLACEMENTS,
)

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


def populate_edit_menu(workspace: PaintWorkspace) -> None:
    """Attach the Edit-menu actions to ``workspace``."""
    bridge = _EditMenuBridge(workspace)
    workspace._edit_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "edit")
    lang = language_wrapper.language_word_dict

    quick_mask_action = menu.addAction(
        lang.get("paint_edit_quick_mask", "Quick Mask Mode"),
    )
    quick_mask_action.setCheckable(True)
    quick_mask_action.setShortcut(QKeySequence("Q"))
    quick_mask_action.triggered.connect(bridge.toggle_quick_mask)
    bridge._quick_mask_action = quick_mask_action  # noqa: SLF001

    menu.addSeparator()
    stroke_action = menu.addAction(
        lang.get("paint_edit_stroke_selection", "Stroke Selection…"),
    )
    stroke_action.triggered.connect(bridge.open_stroke_selection)

    capture_action = menu.addAction(
        lang.get("paint_edit_capture_brush_tip", "Capture Brush Tip…"),
    )
    capture_action.triggered.connect(bridge.capture_brush_tip)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _EditMenuBridge:
    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace
        self._quick_mask_action = None

    def toggle_quick_mask(self) -> None:
        """Flip the workspace's quick-mask mode and sync the action's
        check state."""
        was_active = self._workspace.is_quick_mask_active()
        if was_active:
            self._workspace.exit_quick_mask()
        else:
            self._workspace.enter_quick_mask()
        if self._quick_mask_action is not None:
            self._quick_mask_action.setChecked(
                self._workspace.is_quick_mask_active(),
            )

    def open_stroke_selection(self) -> None:  # pragma: no cover - Qt UI
        document = self._workspace.canvas().document()
        if document.selection() is None:
            return
        dialog = StrokeSelectionDialog(parent=self._workspace)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        params = dialog.values()
        commit_stroke_selection(self._workspace, params)

    def capture_brush_tip(self) -> None:  # pragma: no cover - Qt UI
        from PySide6.QtWidgets import QInputDialog
        document = self._workspace.canvas().document()
        if document.selection() is None or document.active_layer() is None:
            return
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self._workspace,
            lang.get("paint_edit_capture_brush_tip", "Capture Brush Tip…"),
            lang.get("paint_edit_capture_brush_tip_name", "Tip name"),
            text="my_tip",
        )
        if not ok:
            return
        commit_capture_brush_tip(self._workspace, str(name))


# ---------------------------------------------------------------------------
# Stroke Selection dialog
# ---------------------------------------------------------------------------


class StrokeSelectionDialog(QDialog):
    """Width spinner + placement combo. Colour comes from the active FG."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            lang.get("paint_edit_stroke_selection", "Stroke Selection…"),
        )
        self.setMinimumWidth(320)

        form = QFormLayout(self)
        self._width = QSpinBox()
        self._width.setRange(MIN_STROKE_WIDTH, MAX_STROKE_WIDTH)
        self._width.setValue(2)
        form.addRow(
            lang.get("paint_edit_stroke_width", "Width"), self._width,
        )

        self._placement = QComboBox()
        for name in STROKE_PLACEMENTS:
            label = lang.get(
                f"paint_edit_stroke_placement_{name}", name.title(),
            )
            self._placement.addItem(label, userData=name)
        # Default to the documented placement.
        idx = self._placement.findData(DEFAULT_PLACEMENT)
        if idx >= 0:
            self._placement.setCurrentIndex(idx)
        form.addRow(
            lang.get("paint_edit_stroke_placement", "Placement"),
            self._placement,
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        return {
            "width": self._width.value(),
            "placement": self._placement.currentData(),
        }


# ---------------------------------------------------------------------------
# Commit — pure logic, callable from tests without a dialog
# ---------------------------------------------------------------------------


def commit_capture_brush_tip(
    workspace, name: str, *, target_dir=None,
) -> str | None:
    """Capture the active document's selection as a brush-tip PNG.

    Returns the absolute path of the saved tip on success, or
    ``None`` when capture fails (no selection, empty selection,
    too-large bbox). Side effects: registers the new tip in the
    workspace's MaterialDock so the user sees it appear immediately.
    """
    from Imervue.paint.brush_tip_capture import (
        capture_brush_tip,
        save_brush_tip,
    )
    from Imervue.paint.material_library import MaterialEntry
    document = workspace.canvas().document()
    layer = document.active_layer()
    if layer is None:
        return None
    selection = document.selection()
    if selection is None:
        return None
    try:
        tip = capture_brush_tip(layer.image, selection)
        path = save_brush_tip(tip, name, target_dir=target_dir)
    except (OSError, ValueError):
        return None
    # Surface the new tip in the material panel — append to the
    # live index so the user can click it without reloading.
    if hasattr(workspace, "_material_dock"):
        index = workspace._material_dock.index()  # noqa: SLF001
        index.entries.append(MaterialEntry(
            name=path.stem, path=path, category="brush_tip", tags=("user",),
        ))
        workspace._material_dock._refresh_grid()  # noqa: SLF001
    return str(path)


def commit_stroke_selection(workspace, params: dict) -> bool:
    """Stroke the active document's selection on the active layer."""
    from Imervue.paint.stroke_selection import stroke_selection
    document = workspace.canvas().document()
    layer = document.active_layer()
    if layer is None:
        return False
    selection = document.selection()
    if selection is None:
        return False
    fg = tuple(int(c) for c in workspace.state().foreground)
    color = (fg[0], fg[1], fg[2], 255)
    width = int(params.get("width", 2))
    placement = str(params.get("placement", DEFAULT_PLACEMENT))
    try:
        ok = stroke_selection(
            layer.image, selection, color,
            width=width, placement=placement,
        )
    except ValueError:
        return False
    if ok:
        document.invalidate_composite()
        workspace.canvas().update()
    return ok
