"""Document-content commands for the Paint workspace.

Groups the dock-driven content operations that mutate the active
document: animation frames + onion skin, pose / stamp insertion, the
auto-region fill, comic-project page swapping, quick-mask mode, material
drops, and the secondary preview windows. Extracted from
:mod:`paint_workspace` and composed via :class:`ContentOpsMixin`.
"""
from __future__ import annotations

import numpy as np

POSE_LAYER_NAME = "Pose"

# Stamp sizing relative to the canvas — large enough to read, small
# enough to reposition without immediately clipping the edges.
_STAMP_WIDTH_FRACTION = 0.35
_STAMP_HEIGHT_FRACTION = 0.30
_STAMP_MIN_PX = 64

_TILE_CATEGORIES = ("texture", "tone", "pattern")


class ContentOpsMixin:
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
        self._canvas.set_document(document)
        if hasattr(self._layer_dock, "set_document"):
            self._layer_dock.set_document(document)
        self._canvas.update()

    # ---- quick mask mode -----------------------------------------------

    def is_quick_mask_active(self) -> bool:
        return getattr(self, "_quick_mask_state", None) is not None

    def enter_quick_mask(self) -> bool:
        """Toggle the active layer into a paintable selection overlay.

        Returns ``True`` if the mode was entered. Refuses gracefully
        when there's no active layer (the user has nothing to paint
        on); the caller can ignore the return.
        """
        if self.is_quick_mask_active():
            return False
        from Imervue.paint.quick_mask import enter_mode
        canvas = self.canvas()
        document = canvas.document()
        layer = document.active_layer()
        if layer is None:
            return False
        layer_index = document._active_index   # noqa: SLF001
        state = enter_mode(
            layer.image, document.selection(), layer_index=layer_index,
        )
        # Swap the layer's pixels for the proxy buffer so brushes paint
        # into the overlay rather than the underlying art.
        layer.image = state.buffer
        self._quick_mask_state = state
        document.invalidate_composite()
        canvas.update()
        return True

    def exit_quick_mask(self) -> bool:
        """Convert the painted overlay back into a selection and
        restore the layer's original pixels."""
        if not self.is_quick_mask_active():
            return False
        from Imervue.paint.quick_mask import exit_mode
        state = self._quick_mask_state   # noqa: SLF001
        canvas = self.canvas()
        document = canvas.document()
        if state.layer_index < 0 or state.layer_index >= document.layer_count:
            # The active layer disappeared while in quick-mask mode;
            # drop the state without touching anything.
            self._quick_mask_state = None
            return False
        layer = document.layer_at(state.layer_index)
        restored, selection = exit_mode(state)
        layer.image = restored
        canvas.set_selection(selection)
        self._quick_mask_state = None
        document.invalidate_composite()
        canvas.update()
        return True

    # ---- material drops ------------------------------------------------

    def _on_material_chosen(self, path: str) -> None:
        """Drop a material onto the canvas based on its category.

        * ``pose`` — load full image, fit to canvas, paste into a new layer.
        * ``texture`` / ``tone`` / ``pattern`` — tile across the canvas.
        * ``brush_tip`` — bind the tip PNG to the active brush.
        """
        from pathlib import Path

        from Imervue.paint.material_library import MaterialEntry

        entry = next(
            (e for e in self._material_dock.index().entries
             if str(e.path) == path),
            None,
        )
        if entry is None:
            entry = MaterialEntry(name=Path(path).stem, path=Path(path))
        if entry.category == "pose":
            self._drop_pose_material(entry)
        elif entry.category in _TILE_CATEGORIES:
            self._drop_tile_material(entry)
        elif entry.category == "brush_tip":
            self._drop_brush_tip_material(entry)

    def _drop_brush_tip_material(self, entry) -> None:
        """Bind the picked tip's PNG path to the active brush.

        Procedural ``brush_tip`` entries that don't have an on-disk
        path are silently ignored — the brush engine reads tips from
        a file path, so a virtual entry has nothing to point at.
        """
        if entry.is_procedural():
            return
        path = str(entry.path)
        if not path or path.startswith("procedural://"):
            return
        self._state.set_brush(tip_path=path)

    def _drop_pose_material(self, entry) -> None:
        from Imervue.paint.pose_drop import fit_pose_to_canvas, load_pose_image
        canvas_doc = self._canvas.document()
        if canvas_doc.shape is None:
            return
        try:
            pose = load_pose_image(entry.path)
        except (OSError, ValueError):
            return
        fitted = fit_pose_to_canvas(pose, canvas_doc.shape)
        layer = canvas_doc.add_layer(name=f"Pose · {entry.name}")
        np.copyto(layer.image, fitted)
        canvas_doc.invalidate_composite()
        self._canvas.update()

    def _drop_tile_material(self, entry) -> None:
        """Tile a procedural / on-disk material across the canvas as a
        fresh layer. Honours the active selection: if one exists, the
        tiled fill is masked to it."""
        from Imervue.paint.material_procedural import tile_to_canvas
        canvas_doc = self._canvas.document()
        if canvas_doc.shape is None:
            return
        tile = self._load_material_tile(entry)
        if tile is None:
            return
        h, w = canvas_doc.shape
        filled = tile_to_canvas(tile, (h, w))
        selection = self._canvas.current_selection()
        layer = canvas_doc.add_layer(name=f"{entry.category.title()} · {entry.name}")
        if selection is None:
            np.copyto(layer.image, filled)
        else:
            layer.image[selection] = filled[selection]
        canvas_doc.invalidate_composite()
        self._canvas.update()

    @staticmethod
    def _load_material_tile(entry):
        """Return an HxWx4 RGBA tile for ``entry``, or ``None`` on failure.

        Procedural entries call their provider; path entries are
        decoded via PIL. Both paths validate the array shape before
        returning so the caller can treat ``None`` as "nothing to paste".
        """
        if entry.is_procedural():
            try:
                tile = entry.render()
            except (ValueError, RuntimeError):
                return None
        else:
            from PIL import Image
            try:
                with Image.open(entry.path) as img:
                    tile = np.array(img.convert("RGBA"))
            except (OSError, ValueError):
                return None
        if (
            tile is None
            or tile.ndim != 3
            or tile.shape[2] != 4
            or tile.dtype != np.uint8
        ):
            return None
        return tile

    # ---- secondary preview windows -------------------------------------

    def open_secondary_view(self):
        """Spawn an independent overview window onto the same composite."""
        return self._open_secondary_view(mirror_horizontal=False)

    def open_mirror_preview(self):
        """Spawn a horizontally-flipped read-only preview window.

        The flip is a view-only transform on the composite so the
        underlying document is unaffected — the "anatomy check" workflow.
        """
        return self._open_secondary_view(mirror_horizontal=True)

    def open_tile_preview(self):
        """Spawn a 3×3 tiled preview window for seamless-tile checking."""
        return self._open_secondary_view(tile_preview=True)

    def _open_secondary_view(
        self, *,
        mirror_horizontal: bool = False,
        tile_preview: bool = False,
    ):
        from Imervue.paint.multi_view import SecondaryView, composite_to_pixmap
        view = SecondaryView(
            self,
            mirror_horizontal=mirror_horizontal,
            tile_preview=tile_preview,
        )
        if not hasattr(self, "_secondary_views"):
            self._secondary_views = []
        self._secondary_views.append(view)
        view.closed.connect(lambda v=view: self._on_secondary_view_closed(v))
        composite = self._canvas.document().composite()
        view.set_composite(composite_to_pixmap(composite))
        view.show()
        return view

    def secondary_view_count(self) -> int:
        return len(getattr(self, "_secondary_views", ()))

    def _on_secondary_view_closed(self, view) -> None:
        if hasattr(self, "_secondary_views") and view in self._secondary_views:
            self._secondary_views.remove(view)

    def _push_composite_to_secondary_views(self, composite) -> None:
        from Imervue.paint.multi_view import composite_to_pixmap
        views = getattr(self, "_secondary_views", ())
        if not views:
            return
        pixmap = composite_to_pixmap(composite)
        for view in views:
            view.set_composite(pixmap)
