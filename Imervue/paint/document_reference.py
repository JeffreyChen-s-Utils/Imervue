"""Reference-layer selection and index tracking."""
from __future__ import annotations

import numpy as np

from Imervue.paint.document_layer_visibility import layer_effectively_visible
from Imervue.paint.layer_model import Layer


class DocumentReferenceMixin:
    """Reference-layer selection and index tracking."""

    def reference_layer_index(self) -> int | None:
        """Index of the layer the bucket samples, or ``None`` if unset."""
        return self._reference_layer_index

    def reference_layer_image(self) -> np.ndarray | None:
        """The HxWx4 RGBA buffer of the reference layer, or ``None``.

        Convenience wrapper used by the fill dispatcher so callers do
        not need to know about index bookkeeping. Returns ``None`` if
        no reference layer is set, the index has gone stale, or the
        target layer is hidden — a hidden reference would be confusing
        because the user can't see what bounds the fill.
        """
        idx = self._reference_layer_index
        if idx is None or not 0 <= idx < len(self._layers):
            return None
        layer = self._layers[idx]
        if not self._is_layer_effectively_visible(layer):
            return None
        return layer.image

    def set_reference_layer_index(self, index: int | None) -> bool:
        """Select the bucket reference layer, notifying once only when it changes."""
        idx = None if index is None else int(index)
        if idx is not None and not 0 <= idx < len(self._layers):
            raise IndexError(f"reference layer index {idx} out of range")
        if idx == self._reference_layer_index:
            return False
        self._reference_layer_index = idx
        self._notify()
        return True

    def _shift_reference_for_insert(self, insert_at: int) -> None:
        """Bump the reference index up one when a new layer slid in below."""
        ref = self._reference_layer_index
        if ref is not None and insert_at <= ref:
            self._reference_layer_index = ref + 1

    def _shift_reference_for_remove(self, removed_index: int) -> None:
        """Drop / shift the reference index when a layer was deleted."""
        ref = self._reference_layer_index
        if ref is None:
            return
        if ref == removed_index:
            self._reference_layer_index = None
        elif ref > removed_index:
            self._reference_layer_index = ref - 1

    def _swap_reference(self, a: int, b: int) -> None:
        """Track the reference layer across an a<->b position swap."""
        self._reference_layer_index = {a: b, b: a}.get(
            self._reference_layer_index, self._reference_layer_index,
        )

    def _is_layer_effectively_visible(self, layer: Layer) -> bool:
        return layer_effectively_visible(layer, self._groups)
