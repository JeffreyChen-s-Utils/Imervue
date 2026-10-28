"""Validate and install loaded document state."""
from __future__ import annotations

import numpy as np

from Imervue.paint.layer_model import BACKGROUND_LAYER_NAME, Layer


class DocumentStateMixin:
    """Validate and install loaded document state."""

    def load_image(self, arr: np.ndarray) -> None:
        """Replace the document with a single Background layer of ``arr``."""
        if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
            raise ValueError(
                f"image must be HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}",
            )
        self._layers = [Layer(name=BACKGROUND_LAYER_NAME, image=np.ascontiguousarray(arr))]
        self._active_index = 0
        self._selection = None
        self._reference_layer_index = None
        self._notify()

    def replace_state(
        self,
        *,
        layers: list[Layer],
        active_index: int = 0,
        selection: np.ndarray | None = None,
        groups: dict | None = None,
        named_selections: dict | None = None,
        reference_layer_index: int | None = None,
    ) -> None:
        """Replace the document state wholesale.

        Used by the :mod:`document_io` loader to drop a freshly-read
        layer stack into the document. Validates layer-shape
        consistency and selection compatibility before swapping in.
        """
        if not layers:
            raise ValueError("layers must be non-empty")
        shape = layers[0].image.shape[:2]
        for i, layer in enumerate(layers):
            if layer.image.shape[:2] != shape:
                raise ValueError(
                    f"layer {i} ({layer.name!r}) shape "
                    f"{layer.image.shape[:2]} does not match "
                    f"layer 0 {shape}",
                )
        if selection is not None:
            if selection.shape != shape:
                raise ValueError(
                    f"selection shape {selection.shape} does not "
                    f"match document {shape}",
                )
            if selection.dtype != np.bool_:
                raise ValueError(
                    f"selection dtype must be bool, got {selection.dtype}",
                )
        self._layers = list(layers)
        self._active_index = max(0, min(int(active_index), len(layers) - 1))
        self._selection = selection
        self._groups = dict(groups) if groups else {}
        self._named_selections = (
            dict(named_selections) if named_selections else {}
        )
        if reference_layer_index is None:
            self._reference_layer_index = None
        else:
            ref = int(reference_layer_index)
            self._reference_layer_index = (
                ref if 0 <= ref < len(self._layers) else None
            )
        self._notify()
