"""Canvas-geometry operations of the paint document.

Crop (to a rectangle, the selection, or the non-transparent pixels), flips,
90 / 180 degree rotations, resize and free canvas transforms. Each one
rewrites every layer, its mask and the saved selections together so they stay
aligned, then invalidates the composite. Pure NumPy, no Qt;
``PaintDocument`` mixes these methods in.
"""
from __future__ import annotations

import numpy as np


class DocumentGeometryMixin:
    """Crop, flip, rotate, resize and transform operations of the paint document."""

    def crop(self, rect: tuple[int, int, int, int]) -> bool:
        """Crop the document to ``(x, y, w, h)`` — every layer + the
        selection are sliced together so they stay aligned."""
        from Imervue.paint.crop import crop_to_rect
        if not self._layers:
            return False
        for layer in self._layers:
            layer.image = crop_to_rect(layer.image, rect)
            if layer.mask is not None:
                layer.mask = crop_to_rect(layer.mask, rect)
        self._remap_all_selections(lambda arr: crop_to_rect(arr, rect))
        self._notify()
        return True

    def crop_to_selection(self) -> bool:
        """Crop to the bounding box of the active selection.

        Returns ``False`` if there is no selection or the selection is
        empty (nothing to crop to)."""
        from Imervue.paint.crop import selection_bounds
        if self._selection is None:
            return False
        rect = selection_bounds(self._selection)
        if rect is None:
            return False
        return self.crop(rect)

    def crop_to_non_transparent(self) -> bool:
        """Crop to the union bbox of every layer's alpha > 0 region.

        Hidden layers are included — the operation is a "trim away
        empty borders" command, not a "crop to what's visible". A
        fully-transparent stack yields ``False`` (nothing to crop to).
        """
        from Imervue.paint.crop import non_transparent_bounds, union_bounds
        if not self._layers:
            return False
        rects = [non_transparent_bounds(layer.image) for layer in self._layers]
        rect = union_bounds(*rects)
        if rect is None:
            return False
        return self.crop(rect)

    def flip_horizontal(self) -> bool:
        """Mirror every layer + mask + selection along the vertical axis.

        In-place numpy view via ``np.fliplr`` on each buffer; returns
        ``True`` once flipped (the operation always succeeds with a
        non-empty document).
        """
        if not self._layers:
            return False
        for layer in self._layers:
            layer.image = np.ascontiguousarray(np.fliplr(layer.image))
            if layer.mask is not None:
                layer.mask = np.ascontiguousarray(np.fliplr(layer.mask))
        self._remap_all_selections(
            lambda arr: np.ascontiguousarray(np.fliplr(arr)))
        self._notify()
        return True

    def flip_vertical(self) -> bool:
        """Mirror every layer + mask + selection along the horizontal axis."""
        if not self._layers:
            return False
        for layer in self._layers:
            layer.image = np.ascontiguousarray(np.flipud(layer.image))
            if layer.mask is not None:
                layer.mask = np.ascontiguousarray(np.flipud(layer.mask))
        self._remap_all_selections(
            lambda arr: np.ascontiguousarray(np.flipud(arr)))
        self._notify()
        return True

    def rotate_90_cw(self) -> bool:
        """Rotate the whole document 90° clockwise.

        ``np.rot90(arr, k=-1)`` is the canonical 90°-CW; the result
        swaps width and height across every layer + mask + selection.
        """
        if not self._layers:
            return False
        for layer in self._layers:
            layer.image = np.ascontiguousarray(np.rot90(layer.image, k=-1))
            if layer.mask is not None:
                layer.mask = np.ascontiguousarray(np.rot90(layer.mask, k=-1))
        self._remap_all_selections(
            lambda arr: np.ascontiguousarray(np.rot90(arr, k=-1)))
        self._notify()
        return True

    def rotate_90_ccw(self) -> bool:
        """Rotate the whole document 90° counter-clockwise."""
        if not self._layers:
            return False
        for layer in self._layers:
            layer.image = np.ascontiguousarray(np.rot90(layer.image, k=1))
            if layer.mask is not None:
                layer.mask = np.ascontiguousarray(np.rot90(layer.mask, k=1))
        self._remap_all_selections(
            lambda arr: np.ascontiguousarray(np.rot90(arr, k=1)))
        self._notify()
        return True

    def resize(
        self, new_w: int, new_h: int, *, resample: str = "bilinear",
    ) -> bool:
        """Resample every layer + mask + selection to ``(new_h, new_w)``.

        Pure-numpy via Pillow under the hood (see
        :mod:`Imervue.paint.image_resize`). Returns ``True`` once the
        document was actually resized; identity-resize on a same-size
        document still returns ``True`` so the caller can refresh
        unconditionally without inspecting the verb's return value.
        """
        if not self._layers:
            return False
        from Imervue.paint.image_resize import (
            resize_mask, resize_rgba, resize_selection,
        )
        for layer in self._layers:
            layer.image = resize_rgba(
                layer.image, new_w, new_h, resample=resample,
            )
            if layer.mask is not None:
                layer.mask = resize_mask(
                    layer.mask, new_w, new_h, resample=resample,
                )
        self._remap_all_selections(
            lambda arr: resize_selection(arr, new_w, new_h))
        self._notify()
        return True

    def rotate_180(self) -> bool:
        """Rotate the whole document 180° — equivalent to flip H + flip V."""
        if not self._layers:
            return False
        for layer in self._layers:
            layer.image = np.ascontiguousarray(np.rot90(layer.image, k=2))
            if layer.mask is not None:
                layer.mask = np.ascontiguousarray(np.rot90(layer.mask, k=2))
        self._remap_all_selections(
            lambda arr: np.ascontiguousarray(np.rot90(arr, k=2)))
        self._notify()
        return True

    def transform_selection(
        self, *,
        scale: float = 1.0,
        angle_deg: float = 0.0,
        dx: float = 0.0,
        dy: float = 0.0,
        anchor: tuple[float, float] | None = None,
    ) -> bool:
        """Scale / rotate / translate the active layer's selected pixels.

        Cuts the selection out of the active layer, applies the affine
        transform, and pastes the warped pixels back. Updates the
        document selection to reflect the new pixel positions.
        Returns ``True`` if anything was warped (i.e. the selection
        is non-empty and the transform isn't an identity).
        """
        from Imervue.paint.selection_transform import transform_selection
        layer = self.active_layer()
        if layer is None or self._selection is None:
            return False
        if not self._selection.any():
            return False
        new_image, new_selection = transform_selection(
            layer.image, self._selection,
            scale=scale, angle_deg=angle_deg, dx=dx, dy=dy, anchor=anchor,
        )
        layer.image = new_image
        self._selection = new_selection
        self._notify()
        return True

    def transform_canvas(self, *, action: str) -> bool:
        """Apply a canvas-wide transform to every layer + the selection.

        ``action`` must be one of
        :data:`Imervue.paint.canvas_transforms.CANVAS_TRANSFORM_ACTIONS`
        (rotate_90_ccw / rotate_90_cw / rotate_180 / flip_horizontal /
        flip_vertical). The 90° rotations swap width and height; the
        document.shape after the call reflects the new orientation.
        Returns ``True`` if anything changed.
        """
        from Imervue.paint.canvas_transforms import apply_canvas_transform
        if not self._layers:
            return False
        for layer in self._layers:
            layer.image = apply_canvas_transform(layer.image, action)
            if layer.mask is not None:
                layer.mask = apply_canvas_transform(layer.mask, action)
        if self._selection is not None:
            self._selection = apply_canvas_transform(self._selection, action)
        self._notify()
        return True
