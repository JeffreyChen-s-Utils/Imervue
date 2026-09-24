"""Modify panel — inline annotation + non-destructive image adjustments.

A QWidget that provides ``build_left_panel()``, ``build_right_panel()``,
and an inline ``AnnotationCanvas`` to populate the Modify tab's
three-column layout:

    left tool strip | annotation canvas | right properties

- **Left panel**: annotation tool buttons (select, shapes, freehand,
  text, mosaic, blur) + orientation (rotate/flip)
- **Center**: an ``AnnotationCanvas`` showing the current image —
  drawing happens directly here, no dialog needed.
- **Right panel**: drawing properties (color, stroke width, brush,
  opacity, spacing), annotation undo/redo + save, develop sliders
  (exposure/brightness/contrast/saturation), recipe reset/undo/redo.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING
from collections.abc import Callable

import numpy as np
from PIL import Image
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QUndoStack
from PySide6.QtWidgets import (
    QColorDialog,
    QMenu,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui.develop_right_panel import DevelopRightPanelMixin
from Imervue.image.orientation import exif_orientation, transpose_for
from Imervue.gui.modify_splitter import ModifySplitterMixin
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.best_effort import best_effort
import contextlib

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView
    from Imervue.gui.annotation_dialog import AnnotationCanvas

logger = logging.getLogger("Imervue.develop_panel")


def _rebind_target_after_delete(images: list[str], current_index: int) -> str | None:
    """Image to rebind the Modify canvas to after deleting the current one.

    ``delete_current_image`` already advanced ``current_index`` onto the next
    surviving image; return it, or ``None`` when the folder is now empty so the
    caller clears the canvas.
    """
    if images and 0 <= current_index < len(images):
        return images[current_index]
    return None


class DevelopPanel(DevelopRightPanelMixin, ModifySplitterMixin, QWidget):
    """Controller that builds the left/right panels for the Modify tab.

    Emits ``recipe_committed(path, old_recipe, new_recipe)`` whenever a
    develop-slider change is finalised (after the debounce timer fires).
    """

    recipe_committed = Signal(str, object, object)

    _COLOR_RANGE = 100
    _EXPOSURE_RANGE = 200
    _DEBOUNCE_MS = 200

    # Advanced develop sliders: (recipe_field, i18n_key, fallback_label)
    _ADVANCED_SLIDERS = [
        ("temperature", "develop_temperature", "Temperature"),
        ("tint",        "develop_tint",        "Tint"),
        ("highlights",  "develop_highlights",  "Highlights"),
        ("shadows",     "develop_shadows",     "Shadows"),
        ("whites",      "develop_whites",      "Whites"),
        ("blacks",      "develop_blacks",      "Blacks"),
        ("vibrance",    "develop_vibrance",    "Vibrance"),
    ]

    # Annotation tool definitions: (tool_key, glyph, i18n_key, fallback)
    _ANNOTATION_TOOLS = [
        ("select",   "⬚", "annotation_tool_select",   "Select"),
        ("crop",     "✂", "annotation_tool_crop",      "Crop"),
        ("rect",     "▢", "annotation_tool_rect",      "Rectangle"),
        ("ellipse",  "◯", "annotation_tool_ellipse",   "Ellipse"),
        ("line",     "╱", "annotation_tool_line",       "Line"),
        ("arrow",    "→", "annotation_tool_arrow",      "Arrow"),
        ("freehand", "✎", "annotation_tool_freehand",   "Freehand"),
        ("text",     "T", "annotation_tool_text",       "Text"),
        ("mosaic",   "▦", "annotation_tool_mosaic",     "Mosaic"),
        ("blur",     "◌", "annotation_tool_blur",       "Blur"),
    ]

    # Crop aspect ratio presets: (label_key, fallback, ratio_w, ratio_h)
    # ratio 0,0 = free
    _CROP_RATIOS = [
        ("crop_ratio_free",  "Free",     0, 0),
        ("crop_ratio_1_1",   "1 : 1",    1, 1),
        ("crop_ratio_4_3",   "4 : 3",    4, 3),
        ("crop_ratio_3_2",   "3 : 2",    3, 2),
        ("crop_ratio_16_9",  "16 : 9",  16, 9),
        ("crop_ratio_9_16",  "9 : 16",   9, 16),
    ]

    # Size of each tool button in the vertical strip.
    _TOOL_BTN_SIZE = QSize(86, 66)

    def __init__(self, main_gui: GPUImageView):
        super().__init__()
        self._main_gui = main_gui
        self._path: str | None = None
        self._current = Recipe()
        self._committed = Recipe()
        self._suppress_signals = False
        # Guards re-entrancy: the commit handler reloads the image, which can
        # synchronously rebind the panel; without this flag a stray slider tick
        # during that reload could fire a second, nested commit.
        self._committing = False

        self._undo_stack = QUndoStack(self)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(self._DEBOUNCE_MS)
        self._debounce.timeout.connect(self._preview_debounced)

        self._interactive_widgets: list[QWidget] = []

        # Inline annotation canvas — created lazily when an image is bound.
        self._canvas: AnnotationCanvas | None = None
        self._canvas_undo_stack = QUndoStack(self)
        self._canvas_source_path: str | None = None
        # Save-feedback toast, parented to (and freed with) the current canvas.
        self._canvas_toast = None

        # Drawing state (mirrored by the right-panel controls)
        self._draw_color: tuple[int, int, int, int] = (255, 0, 0, 255)

        # Decoded-source cache: maps the currently bound path to its raw RGBA
        # PIL image (post-decode, pre-recipe). Dragging a develop slider is a
        # high-frequency operation; without this every debounce tick would
        # re-open and re-decode the full-resolution file from disk. We keep at
        # most one entry (the current path) so memory stays bounded.
        # (path, EXIF-upright?) of the cached decode — see _decode_source.
        self._decoded_source_key: tuple[str, bool] | None = None
        self._decoded_source: Image.Image | None = None

    # ------------------------------------------------------------------
    # Panel builders — called by ImervueMainWindow
    # ------------------------------------------------------------------

    def build_left_panel(self, parent_splitter: QSplitter) -> None:
        """Build a narrow vertical tool strip (annotation + orientation) with a scroll bar."""
        lang = language_wrapper.language_word_dict

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # --- Annotation tools (vertical single-column) ---
        self._tool_buttons: dict[str, QToolButton] = {}
        for tool_key, glyph, i18n_key, fallback in self._ANNOTATION_TOOLS:
            btn = QToolButton()
            label = lang.get(i18n_key, fallback)
            btn.setText(f"{glyph}\n{label}")
            btn.setToolTip(label)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setFixedSize(self._TOOL_BTN_SIZE)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, t=tool_key: self._set_tool(t))
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._interactive_widgets.append(btn)
            self._tool_buttons[tool_key] = btn

        # Default: select tool checked
        if "select" in self._tool_buttons:
            self._tool_buttons["select"].setChecked(True)

        # Crop controls are built in build_right_panel() where there is
        # enough width for the combo box and buttons.

        # --- Separator ---
        layout.addSpacing(4)

        # --- Orientation (also vertical) ---
        orient_buttons: list[tuple[str, str, str, Callable]] = [
            ("⟲", "develop_rotate_ccw", "Rotate 90° CCW", lambda: self._rotate(-1)),
            ("⟳", "develop_rotate_cw",  "Rotate 90° CW",  lambda: self._rotate(1)),
            ("⇆", "develop_flip_h",     "Flip Horizontal", self._flip_h),
            ("⇅", "develop_flip_v",     "Flip Vertical",   self._flip_v),
        ]
        for glyph, i18n_key, fallback, handler in orient_buttons:
            btn = QToolButton()
            label = lang.get(i18n_key, fallback)
            btn.setText(f"{glyph}\n{label}")
            btn.setToolTip(label)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setFixedSize(self._TOOL_BTN_SIZE)
            btn.clicked.connect(handler)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._interactive_widgets.append(btn)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(panel)
        scroll.setFixedWidth(self._TOOL_BTN_SIZE.width() + 24)
        parent_splitter.addWidget(scroll)


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # Public API — called by GPUImageView / ImervueMainWindow
    # ------------------------------------------------------------------

    def canvas(self) -> AnnotationCanvas | None:
        """Return the current inline AnnotationCanvas, or None."""
        return self._canvas

    def bind_to_path(self, path: str | None) -> None:
        """Load the recipe for ``path`` (or clear if None) and refresh the UI.

        Also creates / updates the inline AnnotationCanvas with the
        image at *path*.  When re-binding to the *same* path (e.g. after a
        tab switch) the working recipe (``_current``) is preserved so unsaved
        slider/rotate/flip changes are not lost.
        """
        self._path = path
        if path is None:
            self._current = Recipe()
            self._committed = Recipe()
            self._invalidate_decoded_source()
            self._set_enabled(False)
            self._sync_sliders()
            self._destroy_canvas()
            return

        if self._canvas_source_path != path:
            # New image — load the saved recipe from the store.
            self._current = recipe_store.get_for_path(path) or Recipe()
            self._committed = Recipe.from_dict(self._current.to_dict())
            self._set_enabled(True)
            self._sync_sliders()
            self._create_canvas(path)
        else:
            # Same path — keep the working recipe to preserve unsaved edits.
            self._set_enabled(True)

    def current_recipe(self) -> Recipe:
        return Recipe.from_dict(self._current.to_dict())

    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    # ------------------------------------------------------------------
    # Inline AnnotationCanvas management
    # ------------------------------------------------------------------

    def _decode_source(self, path: str) -> Image.Image | None:
        """Return the raw RGBA source image for *path*, decoding once.

        The decoded image (post-decode, pre-recipe) is cached keyed by *path*
        so repeated recipe previews for the same image reuse it instead of
        re-reading and re-decoding the file on every debounce tick. Only the
        current path is retained; binding to a different path discards it.

        The source is turned upright by its EXIF orientation, as the viewer
        loads it, unless the working recipe's geometry predates that
        (``Recipe.base_is_oriented``).
        """
        orient = self._current.base_is_oriented()
        if self._decoded_source_key == (path, orient) and self._decoded_source is not None:
            return self._decoded_source

        try:
            img = Image.open(path)
            code = exif_orientation(img) if orient else 1
            if img.mode not in ("RGB", "RGBA", "L"):
                img = img.convert("RGBA")
            else:
                img.load()
        except Exception:
            logger.exception("Failed to load image: %s", path)
            self._invalidate_decoded_source()
            return None

        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img = transpose_for(img, code)

        self._decoded_source_key = (path, orient)
        self._decoded_source = img
        return img

    def _invalidate_decoded_source(self) -> None:
        """Drop the cached decoded source so the next load re-decodes."""
        self._decoded_source_key = None
        self._decoded_source = None

    def _load_image_with_recipe(self, path: str) -> Image.Image | None:
        """Load *path* (cached decode) and apply the current recipe.

        Returns an RGBA PIL image or None on failure. The decode step is
        cached by path; only the recipe re-application runs on every call.
        """
        img = self._decode_source(path)
        if img is None:
            return None

        if not self._current.is_identity():
            arr = self._current.apply(np.array(img))
            img = Image.fromarray(arr, "RGBA")
        return img

    def _create_canvas(self, path: str) -> None:
        """Load *path* as PIL and create a fresh AnnotationCanvas."""
        from Imervue.gui.annotation_dialog import AnnotationCanvas

        img = self._load_image_with_recipe(path)
        if img is None:
            self._destroy_canvas()
            return

        # Tear down old canvas completely before creating a new one
        self._cleanup_old_canvas()

        self._canvas = AnnotationCanvas(img, self._canvas_undo_stack)
        self._canvas_source_path = path

        # Re-apply the full drawing state so the active tool (mosaic, blur, …),
        # brush, colour, stroke, opacity and font keep working after an image
        # switch instead of silently resetting to the fresh canvas's defaults.
        self._apply_state_to_canvas()

        # Allow Left/Right arrow keys to switch images
        self._canvas.navigate_image.connect(self._on_navigate_image)
        # Ctrl+S saves (with a toast), matching the Save button.
        self._canvas.save_requested.connect(self._save_annotation)
        # Right-click → image operations (save / navigate / delete).
        self._canvas.context_menu_requested.connect(self._show_canvas_menu)
        # Delete (no annotation selected) trashes the current image, matching
        # the Imervue tab — the viewer is hidden here so it can't receive keys.
        self._canvas.delete_image_requested.connect(self._delete_current_image)

        # Insert the canvas into the modify splitter (index 1).
        splitter = getattr(self._main_gui.main_window, "_modify_splitter", None)
        if splitter is not None:
            splitter.insertWidget(1, self._canvas)
            splitter.setStretchFactor(0, 0)   # fixed tool strip
            splitter.setStretchFactor(1, 1)    # canvas takes the slack
            splitter.setStretchFactor(2, 0)    # properties panel
            self._size_modify_splitter(splitter)
        # Focus the canvas so key shortcuts (Delete, arrows, Ctrl+S) land on it
        # rather than a develop slider that ignores them.
        self._canvas.setFocus()


    def _cleanup_old_canvas(self) -> None:
        """Disconnect signals, clear undo stack, and detach the old canvas.

        Avoids both ``shiboken_delete`` and ``deleteLater`` — both of them
        race with Qt's widget-tree teardown on Windows and cause heap
        corruption (0xC0000374).  Instead we:

        1. Clear shiboken-managed Python attrs on the canvas so their C++
           counterparts are freed NOW (while Qt is still alive), rather than
           during Python-shutdown GC when Qt is half-destroyed.
        2. Detach from the splitter (``setParent(None)``).
        3. Drop the Python reference — CPython's refcount immediately frees
           the wrapper; shiboken sees no parent → deletes the C++ QWidget
           deterministically, all within normal execution.
        """
        self._canvas_undo_stack.clear()
        if self._canvas is not None:
            # Disconnect signals we connected
            with contextlib.suppress(RuntimeError, TypeError):
                self._canvas.navigate_image.disconnect(self._on_navigate_image)
            with contextlib.suppress(RuntimeError, TypeError):
                self._canvas.save_requested.disconnect(self._save_annotation)
            with contextlib.suppress(RuntimeError, TypeError):
                self._canvas.context_menu_requested.disconnect(self._show_canvas_menu)
            # Cancel any in-flight text editor (its deleteLater would
            # otherwise outlive the canvas).
            with best_effort("cancel the canvas text edit", logger):
                self._canvas._cancel_text_edit()
            # Release shiboken-tracked objects held by the canvas so they
            # are freed deterministically right now.
            self._canvas._base_qimg = None
            self._canvas._preview_qimg = None
            self._canvas.hide()
            self._canvas.setParent(None)
            self._canvas = None
            # The toast was a child of the now-detached canvas — drop the stale
            # reference so the next one is re-created on the new canvas.
            self._canvas_toast = None

    def _destroy_canvas(self) -> None:
        self._debounce.stop()
        self._cleanup_old_canvas()
        self._canvas_source_path = None

    def _refresh_canvas_base(self) -> None:
        """Re-apply the current recipe to the raw image and update the canvas.

        Called when recipe sliders change without a path change.  If the
        image geometry (dimensions) changed — e.g. after a rotation — any
        existing annotations are cleared because their coordinates would be
        invalid in the new coordinate space.
        """
        if self._canvas is None or self._canvas_source_path is None:
            return
        img = self._load_image_with_recipe(self._canvas_source_path)
        if img is None:
            return

        old_w, old_h = self._canvas._base.width, self._canvas._base.height
        if (img.width, img.height) != (old_w, old_h):
            self._canvas.set_annotations([])
            self._canvas.clear_crop()

        self._canvas._set_base_image(img)

    # ------------------------------------------------------------------
    # Left-panel tool selection
    # ------------------------------------------------------------------

    def _current_tool(self) -> str:
        """The annotation tool whose button is checked (default ``select``)."""
        for key, btn in self._tool_buttons.items():
            if btn.isChecked():
                return key
        return "select"

    def _current_brush(self) -> str:
        """The freehand brush whose button is checked (default ``pen``)."""
        for key, btn in self._brush_buttons.items():
            if btn.isChecked():
                return key
        return "pen"

    def _apply_state_to_canvas(self) -> None:
        """Push the full current drawing state onto the live canvas.

        Called after a fresh canvas is created (image switch / reload) so the
        active tool, brush, colour, stroke, opacity and font survive instead of
        resetting to the new canvas's defaults.
        """
        canvas = self._canvas
        if canvas is None:
            return
        canvas.set_color(self._draw_color)
        canvas.set_stroke_width(self._width_slider.value())
        canvas.set_brush_opacity(self._opacity_slider.value())
        canvas.set_brush_type(self._current_brush())
        canvas.set_font_family(self._font_combo.currentFont().family())
        canvas.set_font_size(self._font_size_spin.value())
        tool = self._current_tool()
        canvas.set_tool(tool)
        if tool == "crop":
            rw, rh = self._crop_ratio_combo.currentData() or (0, 0)
            canvas.set_crop_ratio(rw, rh)

    def _set_tool(self, tool: str) -> None:
        # Update button checked state
        for key, btn in self._tool_buttons.items():
            btn.setChecked(key == tool)
        # Show/hide crop controls
        self._crop_widget.setVisible(tool == "crop")
        if tool != "crop" and self._canvas is not None:
            self._canvas.clear_crop()
        if self._canvas is not None:
            self._canvas.set_tool(tool)
            if tool == "crop":
                rw, rh = self._crop_ratio_combo.currentData() or (0, 0)
                self._canvas.set_crop_ratio(rw, rh)

    def _on_crop_ratio_changed(self, _index: int) -> None:
        rw, rh = self._crop_ratio_combo.currentData() or (0, 0)
        if self._canvas is not None:
            self._canvas.set_crop_ratio(rw, rh)

    def _apply_crop(self) -> None:
        if self._canvas is None or self._canvas_source_path is None:
            return
        crop_rect = self._canvas.get_crop_rect()
        if crop_rect is None:
            return
        x, y, w, h = crop_rect
        if w < 2 or h < 2:
            return
        base = self._canvas.get_base_pil()
        cropped = base.crop((x, y, x + w, y + h))
        # Save atomically
        path = self._canvas_source_path
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        ext = target.suffix.lower()
        fmt_map = {
            ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
            ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
            ".webp": "WEBP",
        }
        fmt = fmt_map.get(ext, "PNG")
        try:
            save_img = cropped
            if fmt == "JPEG" and save_img.mode == "RGBA":
                save_img = save_img.convert("RGB")
            save_img.save(str(tmp), format=fmt)
            os.replace(tmp, target)
        except Exception:
            logger.exception("Failed to save crop to %s", path)
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            return
        # The recipe adjustments are now baked into the saved file — reset
        # the recipe so they won't be applied again by the viewer.
        self._current = Recipe()
        self._committed = Recipe()
        recipe_store.set_for_path(path, Recipe())
        self._sync_sliders()

        # The on-disk pixels changed — the cached decode for this path is stale.
        self._invalidate_decoded_source()

        # Reload
        self._canvas.clear_crop()
        self._create_canvas(path)
        try:
            from Imervue.gpu_image_view.images.image_loader import open_path
            self._main_gui._clear_deep_zoom()
            open_path(main_gui=self._main_gui, path=path)
        except Exception:
            logger.exception("Viewer reload after crop failed")

    def _cancel_crop(self) -> None:
        if self._canvas is not None:
            self._canvas.clear_crop()
        self._set_tool("select")

    # ------------------------------------------------------------------
    # Right-panel drawing controls
    # ------------------------------------------------------------------

    def _pick_color(self) -> None:
        r, g, b, a = self._draw_color
        color = QColorDialog.getColor(
            QColor(r, g, b, a),
            self,
            language_wrapper.language_word_dict.get("annotation_color", "Color"),
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self._draw_color = (color.red(), color.green(), color.blue(), color.alpha())
            self._update_color_button_style()
            if self._canvas is not None:
                self._canvas.set_color(self._draw_color)

    def _update_color_button_style(self) -> None:
        r, g, b, a = self._draw_color
        self._color_btn.setStyleSheet(
            f"QToolButton {{ background-color: rgba({r},{g},{b},{a}); "
            f"color: {'#000' if (r + g + b) > 384 else '#fff'}; "
            f"border: 1px solid #555; border-radius: 3px; }}"
        )


    def _on_brush_selected(self, key: str) -> None:
        if self._canvas is not None:
            self._canvas.set_brush_type(key)


    def _on_font_changed(self, font: QFont) -> None:
        if self._canvas is not None:
            self._canvas.set_font_family(font.family())

    def _on_font_size_changed(self, v: int) -> None:
        if self._canvas is not None:
            self._canvas.set_font_size(v)

    # ------------------------------------------------------------------
    # Image navigation (Left / Right arrow in canvas)
    # ------------------------------------------------------------------

    def navigate_image(self, direction: int) -> None:
        """Public image-nav entry point (main-window tab-bar arrow routing).

        Thin wrapper over :meth:`_on_navigate_image` so callers outside the
        canvas signal wiring don't reach into a private method.
        """
        self._on_navigate_image(direction)

    def _on_navigate_image(self, direction: int) -> None:
        """Switch to prev/next image via the viewer, then rebind the canvas."""
        from Imervue.gpu_image_view.actions.select import (
            switch_to_next_image,
            switch_to_previous_image,
        )
        viewer = self._main_gui
        if direction > 0:
            switch_to_next_image(main_gui=viewer)
        else:
            switch_to_previous_image(main_gui=viewer)
        # Rebind to the new current image
        images = viewer.model.images
        path = None
        if images and 0 <= viewer.current_index < len(images):
            path = images[viewer.current_index]
        self.bind_to_path(path)

    # ------------------------------------------------------------------
    # Save annotation
    # ------------------------------------------------------------------

    def _build_canvas_menu(self) -> QMenu:
        """Build the right-click image menu (save / navigate / delete)."""
        lang = language_wrapper.language_word_dict
        menu = QMenu(self._canvas)
        menu.addAction(
            lang.get("annotation_save", "Save"), self._save_annotation)
        menu.addAction(
            lang.get("right_click_menu_previous_image", "Previous Image"),
            lambda: self._on_navigate_image(-1))
        menu.addAction(
            lang.get("right_click_menu_next_image", "Next Image"),
            lambda: self._on_navigate_image(1))
        menu.addSeparator()
        menu.addAction(
            lang.get("right_click_menu_delete_current", "Delete Current Image"),
            self._delete_current_image)
        return menu

    def _show_canvas_menu(self, global_pos) -> None:
        """Pop up the right-click image menu at *global_pos*."""
        if self._canvas is None or self._canvas_source_path is None:
            return
        self._build_canvas_menu().exec(global_pos)

    def _delete_current_image(self) -> None:
        """Soft-delete the current image (undoable) and rebind to the next.

        Reuses the viewer's delete so the undo stack / plugin hooks / recycle
        flow are identical to deleting from the browse view. A GL context is
        made current first because the viewer is hidden on the Modify tab.
        """
        from Imervue.gpu_image_view.actions.delete import delete_current_image
        viewer = self._main_gui
        images = list(getattr(viewer.model, "images", []) or [])
        if not (0 <= viewer.current_index < len(images)):
            return
        with best_effort("make the viewer GL context current", logger):
            viewer.makeCurrent()
        try:
            delete_current_image(viewer)
        finally:
            with best_effort("release the viewer GL context", logger):
                viewer.doneCurrent()
        target = _rebind_target_after_delete(
            list(viewer.model.images), viewer.current_index)
        self.bind_to_path(target)

    def _toast(self, message: str, level: str = "info") -> None:
        """Show a status toast on the (visible) Modify canvas.

        The shared window toast is parented to the viewer, which is hidden
        while the Modify tab is active, so its notifications wouldn't be seen
        here. Parent our own toast to the canvas instead — a plain widget on
        the active tab — so save feedback is actually visible.
        """
        canvas = self._canvas
        if canvas is None:
            return
        from Imervue.gui.toast import ToastWidget
        if self._canvas_toast is None:
            self._canvas_toast = ToastWidget(canvas)
        self._canvas_toast.show_message(message, level)

    def _save_annotation(self) -> None:
        """Bake annotations into the image and save back to the source file."""
        if self._canvas is None or self._canvas_source_path is None:
            return
        from Imervue.gui.annotation_models import bake

        path = self._canvas_source_path
        img = bake(self._canvas.get_base_pil(), self._canvas.get_annotations())
        ext = Path(path).suffix.lower()
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        fmt_map = {
            ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
            ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
            ".webp": "WEBP",
        }
        fmt = fmt_map.get(ext, "PNG")
        try:
            save_img = img
            if fmt == "JPEG" and save_img.mode == "RGBA":
                save_img = save_img.convert("RGB")
            save_img.save(str(tmp), format=fmt)
            os.replace(tmp, target)
        except Exception:
            logger.exception("Failed to save annotation to %s", path)
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            self._toast(
                language_wrapper.language_word_dict.get(
                    "annotation_save_failed", "Save failed"),
                "warning")
            return

        # The recipe adjustments are now baked into the saved file — reset
        # the recipe so they won't be applied again by the viewer.
        self._current = Recipe()
        self._committed = Recipe()
        recipe_store.set_for_path(path, Recipe())
        self._sync_sliders()

        # The on-disk pixels changed — the cached decode for this path is stale.
        self._invalidate_decoded_source()

        # Reload the image in both the canvas and the main viewer
        self._create_canvas(path)
        try:
            from Imervue.gpu_image_view.images.image_loader import open_path
            self._main_gui._clear_deep_zoom()
            open_path(main_gui=self._main_gui, path=path)
        except Exception:
            logger.exception("Viewer reload after annotation save failed")

        # Toast AFTER the reload so it isn't torn down with the old canvas.
        self._toast(
            language_wrapper.language_word_dict.get("annotation_saved", "Saved"),
            "success")

    # ------------------------------------------------------------------
    # Slider → recipe mapping
    # ------------------------------------------------------------------

    def _set_enabled(self, enabled: bool) -> None:
        for w in self._interactive_widgets:
            w.setEnabled(enabled)

    def _sync_sliders(self) -> None:
        """Push recipe values into the sliders without triggering emissions."""
        self._suppress_signals = True
        try:
            self._exposure.setValue(int(round(self._current.exposure * 100)))
            self._brightness.setValue(int(round(self._current.brightness * 100)))
            self._contrast.setValue(int(round(self._current.contrast * 100)))
            self._saturation.setValue(int(round(self._current.saturation * 100)))
            for field_name, slider in self._adv_sliders.items():
                value = getattr(self._current, field_name)
                slider.setValue(int(round(value * 100)))
        finally:
            self._suppress_signals = False
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        lang = language_wrapper.language_word_dict
        self._exposure_label.setText(
            f"{lang.get('develop_exposure', 'Exposure')}: {self._current.exposure:+.2f}"
        )
        bri = int(self._current.brightness * 100)
        con = int(self._current.contrast * 100)
        sat = int(self._current.saturation * 100)
        self._brightness_label.setText(
            f"{lang.get('develop_brightness', 'Brightness')}: {bri:+d}"
        )
        self._contrast_label.setText(
            f"{lang.get('develop_contrast', 'Contrast')}: {con:+d}"
        )
        self._saturation_label.setText(
            f"{lang.get('develop_saturation', 'Saturation')}: {sat:+d}"
        )
        for field_name, i18n_key, fallback in self._ADVANCED_SLIDERS:
            value_pct = int(round(getattr(self._current, field_name) * 100))
            title = lang.get(i18n_key, fallback)
            self._adv_labels[field_name].setText(f"{title}: {value_pct:+d}")

    def _make_advanced_handler(self, field_name: str) -> Callable[[int], None]:
        """Return a slider handler that writes to ``self._current.<field_name>``."""
        def handler(v: int) -> None:
            if self._suppress_signals:
                return
            setattr(self._current, field_name, v / 100.0)
            self._refresh_labels()
            self._schedule_preview()
        return handler

    def _on_exposure(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.exposure = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    def _on_brightness(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.brightness = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    def _on_contrast(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.contrast = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    def _on_saturation(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.saturation = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    # ------------------------------------------------------------------
    # Rotate / flip — preview only (no commit until save)
    # ------------------------------------------------------------------

    def _rotate(self, delta: int) -> None:
        if self._path is None:
            return
        self._current.rotate_steps = (self._current.rotate_steps + delta) % 4
        self._refresh_canvas_base()

    def _flip_h(self) -> None:
        if self._path is None:
            return
        self._current.flip_h = not self._current.flip_h
        self._refresh_canvas_base()

    def _flip_v(self) -> None:
        if self._path is None:
            return
        self._current.flip_v = not self._current.flip_v
        self._refresh_canvas_base()

    def _reset(self) -> None:
        if self._path is None:
            return
        self._current = Recipe()
        self._sync_sliders()
        self._refresh_canvas_base()
        self._commit_recipe()

    # ------------------------------------------------------------------
    # Preview + commit logic — debounced canvas refresh, then write-back
    # ------------------------------------------------------------------

    def _schedule_preview(self) -> None:
        """Debounce canvas refresh so rapid slider drags don't reload on
        every tick."""
        self._debounce.start()

    def _preview_debounced(self) -> None:
        """Refresh the inline preview, then finalise the edit.

        Firing the debounce timer is the signal that the user has paused —
        the working recipe is now considered committed. We update the canvas
        preview first (cheap, local) and then push the recipe to the store and
        notify the viewer via ``recipe_committed`` so the edit survives a tab
        or image switch.
        """
        self._refresh_canvas_base()
        self._commit_recipe()

    def _commit_recipe(self) -> None:
        """Persist the working recipe and emit ``recipe_committed``.

        No-op when nothing changed since the last commit, when no image is
        bound, or while a commit is already in flight. The emitted payload is
        ``(path, old_recipe, new_recipe)`` with defensive copies so a later
        in-place mutation of ``self._current`` can't corrupt the undo state.
        """
        if self._committing or self._path is None:
            return
        if self._current == self._committed:
            return
        old_recipe = Recipe.from_dict(self._committed.to_dict())
        new_recipe = Recipe.from_dict(self._current.to_dict())
        self._committed = Recipe.from_dict(self._current.to_dict())
        self._committing = True
        try:
            self.recipe_committed.emit(self._path, old_recipe, new_recipe)
        finally:
            self._committing = False
