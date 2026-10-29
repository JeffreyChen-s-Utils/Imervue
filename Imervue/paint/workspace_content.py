"""Document-content commands for the Paint workspace.

Groups the dock-driven content operations that mutate the active
document: animation frames + onion skin, pose / stamp insertion, the
auto-region fill and comic-project page swapping. Quick-mask mode,
material drops and the secondary preview windows live in
:mod:`workspace_quick_mask`, :mod:`workspace_materials` and
:mod:`workspace_secondary_views`; :class:`ContentOpsMixin` composes them.
Extracted from :mod:`paint_workspace`.
"""
from __future__ import annotations

import numpy as np

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.workspace_materials import MaterialDropMixin
from Imervue.paint.workspace_quick_mask import QuickMaskMixin
from Imervue.paint.workspace_secondary_views import SecondaryViewMixin

POSE_LAYER_NAME = "Pose"

# Stamp sizing relative to the canvas — large enough to read, small
# enough to reposition without immediately clipping the edges.
_STAMP_WIDTH_FRACTION = 0.35
_STAMP_HEIGHT_FRACTION = 0.30
_STAMP_MIN_PX = 64


class ContentOpsMixin(QuickMaskMixin, MaterialDropMixin, SecondaryViewMixin):
    """Dock-driven operations that add / replace document content.

    Expects the host to provide ``_canvas``, ``_state``, ``_undo_stack``,
    ``_animation_dock``, ``_material_dock``, ``_layer_dock`` and the
    ``toast`` manager.
    """

    # ---- animation timeline --------------------------------------------

    def _on_animation_add_frame(self) -> None:
        """Snapshot the active canvas composite and append it to the
        animation timeline as a fresh frame."""
        composite = self._canvas.document().composite()
        if composite is None:
            return
        timeline = self._animation_dock.timeline()
        timeline.add_frame(composite)
        self._animation_dock.refresh()
        self._refresh_onion_skin_source()

    def _on_animation_remove_frame(self, index: int) -> None:
        timeline = self._animation_dock.timeline()
        if timeline.remove_frame(index):
            self._animation_dock.refresh()
            self._refresh_onion_skin_source()

    def _on_animation_frame_selected(self, index: int) -> None:
        """Load the selected frame's image into the active layer.

        Treats the active layer as the "current frame canvas" — the
        user picks frames; we paste them. Existing layer pixels are
        replaced. Onion-skin source is refreshed so the previous
        frame ghost stays current.
        """
        timeline = self._animation_dock.timeline()
        frame = timeline.frame_at(index)
        if frame is None:
            return
        document = self._canvas.document()
        layer = document.active_layer()
        if layer is None or layer.image.shape != frame.image.shape:
            return
        np.copyto(layer.image, frame.image)
        document.invalidate_composite()
        self._canvas.update()
        self._refresh_onion_skin_source()

    def _refresh_onion_skin_source(self) -> None:
        """Point the canvas onion-skin overlay at the previous frame."""
        if not hasattr(self._canvas, "set_onion_skin_source"):
            return
        timeline = self._animation_dock.timeline()
        prev = timeline.previous_frame()
        if prev is None:
            self._canvas.set_onion_skin_source(None)
            return
        # The canvas accepts a zero-arg callable that returns the
        # buffer, so wrap our cached reference in a thunk.
        buffer = prev.image
        self._canvas.set_onion_skin_source(lambda: buffer)

    # ---- pose / stamp insertion ----------------------------------------

    def _on_pose_insert(self, skeleton) -> None:
        """User clicked "Insert" on the pose dock. Render the
        skeleton into a fresh layer at canvas size."""
        from Imervue.paint.pose_skeleton import render_skeleton

        document = self._canvas.document()
        shape = document.shape
        if shape is None:
            return
        h, w = shape
        rendered = render_skeleton(skeleton, height=h, width=w)
        layer = document.add_layer(name=POSE_LAYER_NAME)
        np.copyto(layer.image, rendered)
        document.invalidate_composite()
        self._undo_stack.commit()
        self._canvas.update()

    def _on_stamp_chosen(self, key: str) -> None:
        """User clicked a stamp thumbnail. Render it at ~1/3 of the
        canvas size and paste it into a new layer at canvas centre."""
        from Imervue.paint.comic_stamps import render_stamp

        document = self._canvas.document()
        shape = document.shape
        if shape is None:
            return
        h, w = shape
        target_w = max(_STAMP_MIN_PX, int(w * _STAMP_WIDTH_FRACTION))
        target_h = max(_STAMP_MIN_PX, int(h * _STAMP_HEIGHT_FRACTION))
        stamp = render_stamp(key, target_w, target_h)
        sh, sw = stamp.shape[:2]
        # Going through ``add_layer`` keeps the document's invariants
        # (active-index update, reference shift, listener notify) intact.
        layer = document.add_layer(name=key)
        x0 = max(0, (w - sw) // 2)
        y0 = max(0, (h - sh) // 2)
        x1 = min(w, x0 + sw)
        y1 = min(h, y0 + sh)
        layer.image[y0:y1, x0:x1] = stamp[: y1 - y0, : x1 - x0]
        document.invalidate_composite()
        self._undo_stack.commit()
        self._canvas.update()

    # ---- auto-region fill ----------------------------------------------

    def _auto_fill_closed_regions(self) -> None:
        """Paint the foreground colour into every enclosed region of
        the document's reference layer (or the active layer when no
        reference layer is set). Pushes one undo entry on success."""
        from Imervue.paint.auto_region_fill import auto_region_fill

        document = self._canvas.document()
        target = document.active_layer()
        if target is None:
            return
        ref_idx = document.reference_layer_index()
        line_art = (
            target.image if ref_idx is None
            else document.layer_at(ref_idx).image
        )
        if self._state.foreground is None:
            return
        result = auto_region_fill(
            target.image,
            line_art,
            self._state.foreground,
        )
        if result.is_empty:
            return
        document.invalidate_composite()
        self._undo_stack.commit()
        self._canvas.update()

    def _auto_base_colours(self) -> int:
        """Flat-colour every closed region of the line art on a new layer just under it.

        The line art is the reference layer when one is set, else the active
        layer. Regions take the Swatches dock's colours when it shows any,
        else a default ring. Returns how many regions were filled (0: nothing
        added, and the user is told no closed region was found).
        """
        from Imervue.paint.auto_base_color import base_colour_layer
        from Imervue.paint.color_palette import palette_colours

        document = self._canvas.document()
        ref_idx = document.reference_layer_index()
        line_idx = document.active_layer_index() if ref_idx is None else ref_idx
        if not 0 <= line_idx < len(document.layers()):
            return 0
        swatches = palette_colours(self._state.swatch_palette, self._state.color_history)
        image, count = base_colour_layer(document.layer_at(line_idx).image,
                                         palette=swatches or None,
                                         gap_close=int(self._state.fill.gap_close_px))
        lang = language_wrapper.language_word_dict
        if count == 0:
            self.toast.warning(lang.get("paint_fill_base_colours_none",
                                        "No closed region found in the line art"))
            return 0
        document.set_active_layer(line_idx)
        layer = document.add_layer(name=lang.get("paint_fill_base_colours_layer", "Base colours"))
        layer.image[...] = image
        document.move_active_layer(up=False)       # under the line art
        document.invalidate_composite()
        self._undo_stack.commit()
        self._canvas.update()
        return count

    # ---- comic-project page browser ------------------------------------

    def set_paint_project(self, project) -> None:
        """Bind ``project`` (a :class:`PaintProject` or ``None``) to the
        workspace and refresh the page dock. The dock degrades to its
        empty state when ``project`` is ``None``."""
        self._paint_project = project
        page_dock = getattr(self, "_page_dock", None)
        if page_dock is not None:
            page_dock.refresh()
        if project is not None and project.active_page() is not None:
            self._swap_canvas_document(project.active_page().document)

    def _on_page_selected(self, index: int) -> None:
        """Page-list click — swap the active canvas's document with the
        selected page's document."""
        project = getattr(self, "_paint_project", None)
        if project is None:
            return
        try:
            page = project.page_at(index)
        except IndexError:
            return
        self._swap_canvas_document(page.document)

    def _swap_canvas_document(self, document) -> None:
        """Replace the active canvas's PaintDocument with ``document``.

        Re-binds the layer dock so it reads from the new document; the
        dispatcher's providers follow because they read ``self._canvas``
        at event time.
        """
        if not hasattr(self._canvas, "set_document"):
            return
        # Resolve any active quick mask before the document under it changes, so
        # the overlay is written back to the layer it was entered on.
        self.exit_quick_mask()
        self._canvas.set_document(document)
        if hasattr(self._layer_dock, "set_document"):
            self._layer_dock.set_document(document)
        self._canvas.update()
