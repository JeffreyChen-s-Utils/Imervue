"""Owned composite cache and bounded pixel damage."""
from __future__ import annotations

import numpy as np

from Imervue.paint.compositing import composite_stack


class DocumentCompositeMixin:
    """Owned composite cache and bounded pixel damage."""

    def composite(self) -> np.ndarray | None:
        """Return the flattened RGBA frame, computing once and caching.

        The cache survives a brush dab when only a bounded region is
        marked dirty — :func:`composite_region` recomputes that slice
        and patches it into the cached buffer, which is dramatically
        cheaper than re-running the full N-layer composite each dab.
        """
        if not self._layers:
            return None
        shape = self.shape
        if shape is None:
            return None
        if self._composite_cache is None:
            self._composite_cache = self._compute_full_composite(shape)
            self._composite_dirty_rect = None
            return self._composite_cache
        if self._composite_dirty_rect is not None:
            from Imervue.paint.compositing import composite_region
            x, y, rw, rh = self._composite_dirty_rect
            partial = composite_region(
                self._layers, shape, (x, y, rw, rh), groups=self._groups,
            )
            if partial is None:
                # A layer in the stack needs full-frame context (effects
                # / adjustment) — fall back to a full recompose so the
                # output still respects every layer's contract.
                self._composite_cache = self._compute_full_composite(shape)
            else:
                self._composite_cache[y:y + rh, x:x + rw] = partial
            self._composite_dirty_rect = None
        return self._composite_cache

    def _compute_full_composite(self, shape: tuple[int, int]) -> np.ndarray:
        """Full stack composite that never aliases a layer's buffer.

        The single-layer fast path in :func:`composite_stack` returns
        the layer's own image object; adopting that as the patchable
        cache would let the dirty-rect patch in :meth:`composite` write
        composite output straight into the layer's pixels.
        """
        result = composite_stack(self._layers, shape, groups=self._groups)
        if any(result is layer.image for layer in self._layers):
            return result.copy()
        return result

    def invalidate_composite(self) -> None:
        """Force the next :meth:`composite` to recompute everything."""
        self._composite_cache = None
        self._composite_dirty_rect = None
        self._emit_changed()

    def mark_composite_dirty(
        self, rect: tuple[int, int, int, int],
    ) -> None:
        """Mark a bounded region of the cached composite as stale.

        The caller (typically the canvas after a brush dab) supplies
        the damage rect from the brush engine; the next
        :meth:`composite` call patches just that rect via
        :func:`composite_region` instead of recomputing the whole
        frame. ``rect`` is ``(x, y, w, h)`` in image-space pixels;
        empty rects are silently dropped, off-canvas rects are
        clipped, and out-of-shape rects fall back to a full
        invalidation so the cache never carries stale pixels.
        """
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return
        shape = self.shape
        if shape is None:
            self.invalidate_composite()
            return
        ih, iw = shape
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(int(iw), int(x) + int(w))
        y1 = min(int(ih), int(y) + int(h))
        if x1 <= x0 or y1 <= y0:
            return
        clipped = (x0, y0, x1 - x0, y1 - y0)
        if self._composite_cache is None:
            # Cache already nuked — full recompose is pending; nothing
            # to merge into. Listeners still fire so the canvas
            # repaints.
            self._emit_changed()
            return
        if self._composite_dirty_rect is None:
            self._composite_dirty_rect = clipped
        else:
            ex, ey, ew, eh = self._composite_dirty_rect
            ux0 = min(ex, x0)
            uy0 = min(ey, y0)
            ux1 = max(ex + ew, x1)
            uy1 = max(ey + eh, y1)
            self._composite_dirty_rect = (ux0, uy0, ux1 - ux0, uy1 - uy0)
        self._emit_changed()
