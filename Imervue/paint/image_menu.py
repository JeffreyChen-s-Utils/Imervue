"""Image-menu actions for the Paint workspace.

Phase 25a populates the new Image menu with whole-canvas verbs:
flip horizontal / flip vertical / rotate 90° CW & CCW / rotate 180°.
Future image-level commands (image size, canvas size) plug in here.

Each action delegates to the existing :class:`PaintDocument`
in-place transforms; the bridge just resolves the active canvas's
document and refreshes after the mutation lands.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.image_resize import (
    DEFAULT_RESAMPLE,
    RESAMPLE_FILTERS,
    RESIZE_DIM_MAX,
    RESIZE_DIM_MIN,
    scaled_dims_keep_aspect,
)
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


def populate_image_menu(workspace: PaintWorkspace) -> None:
    """Attach the Image-menu actions to ``workspace``."""
    bridge = _ImageMenuBridge(workspace)
    workspace._image_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "image")
    lang = language_wrapper.language_word_dict
    for key, fallback, slot, shortcut in (
        ("paint_image_size", "Image Size…",
         bridge.open_image_size, "Ctrl+Alt+I"),
        (None, None, None, None),
        ("paint_image_flip_horizontal", "Flip Horizontal",
         bridge.flip_horizontal, ""),
        ("paint_image_flip_vertical", "Flip Vertical",
         bridge.flip_vertical, ""),
        (None, None, None, None),
        ("paint_image_rotate_90_cw", "Rotate 90° CW",
         bridge.rotate_90_cw, ""),
        ("paint_image_rotate_90_ccw", "Rotate 90° CCW",
         bridge.rotate_90_ccw, ""),
        ("paint_image_rotate_180", "Rotate 180°",
         bridge.rotate_180, ""),
    ):
        if key is None:
            menu.addSeparator()
            continue
        action = menu.addAction(lang.get(key, fallback))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _ImageMenuBridge:
    """Routes Image-menu actions to PaintDocument verbs + canvas refresh."""

    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace

    def flip_horizontal(self) -> None:
        document = self._workspace.canvas().document()
        if document.flip_horizontal():
            self._refresh_canvas()

    def flip_vertical(self) -> None:
        document = self._workspace.canvas().document()
        if document.flip_vertical():
            self._refresh_canvas()

    def rotate_90_cw(self) -> None:
        document = self._workspace.canvas().document()
        if document.rotate_90_cw():
            self._refresh_canvas()

    def rotate_90_ccw(self) -> None:
        document = self._workspace.canvas().document()
        if document.rotate_90_ccw():
            self._refresh_canvas()

    def rotate_180(self) -> None:
        document = self._workspace.canvas().document()
        if document.rotate_180():
            self._refresh_canvas()

    def open_image_size(self) -> None:  # pragma: no cover - Qt UI
        document = self._workspace.canvas().document()
        if document.shape is None:
            return
        h, w = document.shape
        dialog = ImageSizeDialog(
            initial_w=w, initial_h=h, parent=self._workspace,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        params = dialog.values()
        commit_image_resize(self._workspace, params)

    # ---- internals ------------------------------------------------------

    def _refresh_canvas(self) -> None:
        canvas = self._workspace.canvas()
        canvas.document().invalidate_composite()
        canvas.update()


# ---------------------------------------------------------------------------
# Image Size dialog
# ---------------------------------------------------------------------------


class ImageSizeDialog(QDialog):
    """Width × height + resample method, with constrain-proportions."""

    def __init__(self, initial_w: int, initial_h: int, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("paint_image_size", "Image Size"))
        self.setMinimumWidth(360)
        self._initial_w = max(1, int(initial_w))
        self._initial_h = max(1, int(initial_h))
        self._suspend = False

        form = QFormLayout(self)
        self._width = self._spin(self._initial_w)
        self._height = self._spin(self._initial_h)
        form.addRow(lang.get("paint_image_size_width", "Width"), self._width)
        form.addRow(lang.get("paint_image_size_height", "Height"), self._height)

        self._constrain = QCheckBox(
            lang.get("paint_image_size_constrain", "Constrain proportions"),
        )
        self._constrain.setChecked(True)
        form.addRow("", self._constrain)
        self._width.valueChanged.connect(self._on_width_changed)
        self._height.valueChanged.connect(self._on_height_changed)

        self._resample = QComboBox()
        for name in RESAMPLE_FILTERS:
            self._resample.addItem(name)
        self._resample.setCurrentText(DEFAULT_RESAMPLE)
        form.addRow(
            lang.get("paint_image_size_resample", "Resample"), self._resample,
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @staticmethod
    def _spin(value: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(RESIZE_DIM_MIN, RESIZE_DIM_MAX)
        s.setValue(int(value))
        return s

    def _on_width_changed(self, value: int) -> None:  # pragma: no cover - Qt UI
        if self._suspend or not self._constrain.isChecked():
            return
        new_w, new_h = scaled_dims_keep_aspect(
            self._initial_w, self._initial_h,
            int(value), self._initial_h,
        )
        self._suspend = True
        try:
            self._height.setValue(new_h)
        finally:
            self._suspend = False

    def _on_height_changed(self, value: int) -> None:  # pragma: no cover - Qt UI
        if self._suspend or not self._constrain.isChecked():
            return
        new_w, new_h = scaled_dims_keep_aspect(
            self._initial_w, self._initial_h,
            self._initial_w, int(value),
        )
        self._suspend = True
        try:
            self._width.setValue(new_w)
        finally:
            self._suspend = False

    def values(self) -> dict:
        return {
            "width": self._width.value(),
            "height": self._height.value(),
            "resample": self._resample.currentText(),
        }


# ---------------------------------------------------------------------------
# Commit — pure logic, callable from tests without a dialog
# ---------------------------------------------------------------------------


def commit_image_resize(workspace, params: dict) -> bool:
    """Apply ``params`` to the workspace's active document.

    Returns ``True`` when the document was actually resized;
    ``False`` for invalid params or empty document — never raises so
    the dialog can ignore the return value.
    """
    document = workspace.canvas().document()
    if document.shape is None:
        return False
    try:
        new_w = int(params.get("width", 0))
        new_h = int(params.get("height", 0))
        resample = str(params.get("resample", DEFAULT_RESAMPLE))
    except (TypeError, ValueError):
        return False
    try:
        ok = document.resize(new_w, new_h, resample=resample)
    except ValueError:
        return False
    if ok:
        document.invalidate_composite()
        workspace.canvas().update()
    return ok
