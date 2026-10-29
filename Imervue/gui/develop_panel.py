"""Modify panel — inline annotation + non-destructive image adjustments.

A QWidget that provides ``build_left_panel()``, ``build_right_panel()``,
and an inline ``AnnotationCanvas`` to populate the Modify tab:

    tool dock | annotation canvas (centre) | adjustment dock

- **Left panel**: annotation tool buttons (select, shapes, freehand,
  text, mosaic, blur) + orientation (rotate/flip)
- **Center**: an ``AnnotationCanvas`` showing the current image —
  drawing happens directly here, no dialog needed.
- **Right panel**: drawing properties (color, stroke width, brush,
  opacity, spacing), annotation undo/redo + save, develop sliders
  (exposure/brightness/contrast/saturation), recipe reset/undo/redo.

This module keeps the controller state, binding, undo stepping, navigation,
deletion and the recipe commit; the behaviour lives in sibling mixins:
``develop_drawing_tools`` (tool palette + drawing properties),
``develop_canvas_lifecycle`` (decode + canvas creation / teardown),
``develop_canvas_save`` (crop / annotation saves), ``develop_adjustments``
(sliders + rotate / flip), ``develop_right_panel`` and ``develop_preview_panel``.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QSize, QTimer, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QMenu, QWidget

from Imervue.gui.develop_adjustments import DevelopAdjustmentsMixin
from Imervue.gui.develop_canvas_lifecycle import DevelopCanvasLifecycleMixin
from Imervue.gui.develop_canvas_save import DevelopCanvasSaveMixin
from Imervue.gui.develop_drawing_tools import DevelopDrawingToolsMixin
from Imervue.gui.develop_preview_panel import DevelopPreviewMixin
from Imervue.gui.develop_right_panel import DevelopRightPanelMixin
from Imervue.image.in_place_save import can_rewrite_in_place
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.best_effort import best_effort

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


class DevelopPanel(
    DevelopPreviewMixin,
    DevelopRightPanelMixin,
    DevelopDrawingToolsMixin,
    DevelopCanvasLifecycleMixin,
    DevelopCanvasSaveMixin,
    DevelopAdjustmentsMixin,
    QWidget,
):
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

    # Compact icon buttons; translated labels remain in tooltips and accessible names.
    _TOOL_BTN_SIZE = QSize(38, 38)

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
        self._init_preview_controller()

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
            self._sync_save_controls()
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

        self._sync_save_controls()

    def current_recipe(self) -> Recipe:
        return Recipe.from_dict(self._current.to_dict())

    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    def use_undo_stack(self, stack: QUndoStack) -> None:
        """Step Undo / Redo through *stack*: the viewer's, where committed recipe edits are pushed.

        The panel's own stack never received a command, so its Undo and Redo
        buttons did nothing.
        """
        self._undo_stack = stack

    def step_edit(self, backwards: bool) -> None:
        """Undo (or redo) this picture's last committed edit and show the recipe it leaves.

        An edit still waiting for the debounce is committed first, so it is
        what Undo takes back. A command for another picture on top of the
        stack is left alone.
        """
        self._debounce.stop()
        self._commit_recipe()
        stack = self._undo_stack
        command = stack.command(stack.index() - 1 if backwards else stack.index())
        if self._path is None or getattr(command, "path", None) != self._path:
            return
        if backwards:
            stack.undo()
        else:
            stack.redo()
        self._current = recipe_store.get_for_path(self._path) or Recipe()
        self._committed = Recipe.from_dict(self._current.to_dict())
        self._sync_sliders()
        self._refresh_canvas_base()

    def _reload_after_overwrite(self, path: str, failure_message: str) -> None:
        """Reset the recipe now baked into *path*, then reload the canvas and the viewer.

        Kept here because this module owns ``recipe_store`` (tests and the
        benchmark rebind it on this module).
        """
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
            logger.exception(failure_message)

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
    # Canvas context menu + delete current image
    # ------------------------------------------------------------------

    def _build_canvas_menu(self) -> QMenu:
        """Build the right-click image menu (save / navigate / delete)."""
        lang = language_wrapper.language_word_dict
        menu = QMenu(self._canvas)
        overwrite = menu.addAction(
            lang.get("modify_overwrite", "Overwrite original"), self._save_annotation)
        overwrite.setEnabled(bool(self._path and can_rewrite_in_place(self._path)))
        menu.addAction(lang.get("modify_save_copy", "Save copy…"), self._save_copy)
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

    # ------------------------------------------------------------------
    # Preview + commit logic — debounced canvas refresh, then write-back
    # ------------------------------------------------------------------

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
