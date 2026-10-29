"""The Modify tab's inline AnnotationCanvas: source decode, creation and teardown.

:class:`DevelopCanvasLifecycleMixin` decodes the bound image once (cached per
path and EXIF orientation), builds a fresh
:class:`~Imervue.gui.annotation_dialog.AnnotationCanvas` for it on the owning
:class:`~Imervue.gui.develop_panel.DevelopPanel`, re-applies the drawing state
and detaches the old canvas deterministically.
"""
from __future__ import annotations

import contextlib
import logging

import numpy as np
from PIL import Image

from Imervue.gpu_image_view.images.image_loader import decode_image_file
from Imervue.image.recipe import Recipe
from Imervue.system.best_effort import best_effort

# Shares the panel's logger so decode failures keep reporting under it.
logger = logging.getLogger("Imervue.develop_panel")


class DevelopCanvasLifecycleMixin:
    """Decoded-source cache and inline canvas lifecycle of :class:`DevelopPanel`."""

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
            # The viewer's decode: RAW developed (Pillow alone reads a RAW's small
            # embedded preview), sRGB, and upright unless a legacy recipe says not.
            img = Image.fromarray(decode_image_file(path, orient=orient), "RGBA")
        except Exception:
            logger.exception("Failed to load image: %s", path)
            self._invalidate_decoded_source()
            return None

        if img.mode != "RGBA":
            img = img.convert("RGBA")

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

        self._preview.cancel()
        img = self._decode_source(path)
        if img is None:
            self._destroy_canvas()
            return

        # Tear down old canvas completely before creating a new one
        self._cleanup_old_canvas()

        self._canvas = AnnotationCanvas(
            img, self._canvas_undo_stack, full_base_resolver=self._ensure_full_canvas,
        )
        self._canvas_source_path = path
        self._canvas_recipe = (Recipe.from_dict(self._current.to_dict())
                               if self._current.is_identity() else None)
        self._canvas.base_changed.connect(self._on_canvas_base_changed)

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

        # Show the canvas in the centre of the Modify tab, between its docks.
        host = getattr(self._main_gui.main_window, "_modify_canvas_host", None)
        if host is not None:
            host.set_canvas(self._canvas)
        # Focus the canvas so key shortcuts (Delete, arrows, Ctrl+S) land on it
        # rather than a develop slider that ignores them.
        self._canvas.setFocus()
        if not self._current.is_identity():
            self._request_preview(final=True)

    def _cleanup_old_canvas(self) -> None:
        """Disconnect signals, clear undo stack, and detach the old canvas.

        Avoids both ``shiboken_delete`` and ``deleteLater`` — both of them
        race with Qt's widget-tree teardown on Windows and cause heap
        corruption (0xC0000374).  Instead we:

        1. Clear shiboken-managed Python attrs on the canvas so their C++
           counterparts are freed NOW (while Qt is still alive), rather than
           during Python-shutdown GC when Qt is half-destroyed.
        2. Detach from the canvas host (``setParent(None)``), which shows its hint again.
        3. Drop the Python reference — CPython's refcount immediately frees
           the wrapper; shiboken sees no parent → deletes the C++ QWidget
           deterministically, all within normal execution.
        """
        self._preview.cancel()
        self._set_preview_status("")
        self._canvas_undo_stack.clear()
        if self._canvas is not None:
            self._canvas.full_base_resolver = None
            self._canvas.base_changed.disconnect(self._on_canvas_base_changed)
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

    # ------------------------------------------------------------------
    # Drawing state carried across canvases
    # ------------------------------------------------------------------

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
