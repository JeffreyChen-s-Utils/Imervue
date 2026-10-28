"""Active selection and geometry remapping."""
from __future__ import annotations

from collections.abc import Callable

import numpy as np


class DocumentSelectionMixin:
    """Active selection and geometry remapping."""

    def selection(self) -> np.ndarray | None:
        return self._selection

    def set_selection(self, mask: np.ndarray | None) -> None:
        if mask is None:
            self._selection = None
        else:
            shape = self.shape
            if shape is not None and mask.shape != shape:
                raise ValueError(
                    f"selection shape {mask.shape} does not match document {shape}",
                )
            if mask.dtype != np.bool_:
                raise ValueError(f"selection mask must be bool, got {mask.dtype}")
            self._selection = mask
        # Selection changes don't dirty the composite cache, but the
        # canvas does need to redraw the marquee.
        self._emit_changed()

    def selection_from_layer_alpha(
        self, index: int = -1, *, threshold: int = 0,
    ) -> bool:
        """Replace the active selection with one derived from a layer's alpha.

        Pixels with alpha strictly greater than ``threshold`` become
        selected. ``threshold=0`` matches raster paint apps' "Select Layer"
        command. Returns ``True`` if the selection actually changed.
        """
        from Imervue.paint.selection_ops import from_layer_alpha
        layer = self._resolve_layer(index)
        if layer is None:
            return False
        new_selection = from_layer_alpha(layer.image, threshold=threshold)
        # Reuse set_selection so listener notification + shape check fire.
        previous = self._selection
        if (
            previous is not None
            and previous.shape == new_selection.shape
            and np.array_equal(previous, new_selection)
        ):
            return False
        self.set_selection(new_selection)
        return True

    def _remap_all_selections(
        self, transform: Callable[[np.ndarray], np.ndarray],
    ) -> None:
        """Apply a geometric ``transform`` to the active selection and
        every saved named selection so a crop / flip / rotate / resize
        keeps them aligned with the new canvas geometry. Without this a
        later :meth:`load_selection` would restore (or reject) a mask
        sized for the pre-transform canvas."""
        if self._selection is not None:
            self._selection = transform(self._selection)
        if self._named_selections:
            self._named_selections = {
                name: transform(mask)
                for name, mask in self._named_selections.items()
            }
