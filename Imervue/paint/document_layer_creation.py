"""Create raster, adjustment and vector layers."""
from __future__ import annotations

from typing import Any

import numpy as np

from Imervue.paint.layer_model import DEFAULT_LAYER_NAME, Layer


class DocumentLayerCreationMixin:
    """Create raster, adjustment and vector layers."""

    def add_adjustment_layer(
        self, adjustment: Any, *, name: str | None = None,
        on_top_of_active: bool = True,
    ) -> Layer:
        """Add a non-destructive adjustment layer above the active one.

        ``adjustment`` is an :class:`Imervue.paint.adjustments.Adjustment`.
        The layer's image is a fully-transparent placeholder of the
        document shape; the compositor consults ``layer.adjustment``
        and skips the regular blend path when it's set.
        """
        if not self._layers:
            raise RuntimeError("cannot add an adjustment layer to an empty document")
        h, w = self.shape  # type: ignore[misc]
        layer = Layer(
            name=name or f"{adjustment.kind.title()} adjustment",
            image=np.zeros((h, w, 4), dtype=np.uint8),
            adjustment=adjustment,
        )
        return self._insert_new_layer(layer, on_top_of_active=on_top_of_active)

    def add_layer(
        self, *, name: str | None = None, on_top_of_active: bool = True,
    ) -> Layer:
        """Add a fully-transparent layer matching the document shape."""
        if not self._layers:
            raise RuntimeError("cannot add a layer to an empty document")
        h, w = self.shape  # type: ignore[misc]
        layer = Layer(
            name=name or self._unique_layer_name(),
            image=np.zeros((h, w, 4), dtype=np.uint8),
        )
        return self._insert_new_layer(layer, on_top_of_active=on_top_of_active)

    def add_vector_layer(
        self, *, name: str | None = None, on_top_of_active: bool = True,
    ) -> Layer:
        """Add a non-destructive vector-stroke layer.

        The layer's ``image`` field is the rasterised cache — the
        canonical state lives in ``layer.vector_data.strokes``. Edits
        mutate the stroke list and call
        :func:`Imervue.paint.vector_layer.realise_vector_layer` to
        repaint the cache.
        """
        from Imervue.paint.vector_layer import VectorLayerData
        if not self._layers:
            raise RuntimeError("cannot add a layer to an empty document")
        h, w = self.shape  # type: ignore[misc]
        layer = Layer(
            name=name or self._unique_layer_name(),
            image=np.zeros((h, w, 4), dtype=np.uint8),
            vector_data=VectorLayerData(),
        )
        return self._insert_new_layer(layer, on_top_of_active=on_top_of_active)

    def _unique_layer_name(self) -> str:
        existing = {layer.name for layer in self._layers}
        i = len(self._layers)
        while True:
            candidate = f"{DEFAULT_LAYER_NAME} {i}"
            if candidate not in existing:
                return candidate
            i += 1

    def _insert_new_layer(self, layer: Layer, *, on_top_of_active: bool) -> Layer:
        """Insert a created layer and keep active/reference indices aligned."""
        insert_at = self._active_index + 1 if on_top_of_active else len(self._layers)
        insert_at = min(insert_at, len(self._layers))
        self._layers.insert(insert_at, layer)
        self._active_index = insert_at
        self._shift_reference_for_insert(insert_at)
        self._notify()
        return layer
