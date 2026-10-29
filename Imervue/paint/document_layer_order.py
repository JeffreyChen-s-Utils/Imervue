"""Remove, duplicate and reorder owned layers."""
from __future__ import annotations

import copy

from Imervue.paint.layer_model import Layer


class DocumentLayerOrderMixin:
    """Remove, duplicate and reorder owned layers."""

    def remove_active_layer(self) -> None:
        if self._active_index < 0 or len(self._layers) <= 1:
            return  # never remove the last layer
        removed = self._active_index
        del self._layers[removed]
        self._active_index = max(0, self._active_index - 1)
        self._shift_reference_for_remove(removed)
        self._notify()

    def duplicate_active_layer(self) -> None:
        layer = self.active_layer()
        if layer is None:
            return
        duplicate = Layer(
            name=f"{layer.name} copy",
            image=layer.image.copy(),
            opacity=layer.opacity,
            blend_mode=layer.blend_mode,
            visible=layer.visible,
            locked=layer.locked,
            mask=None if layer.mask is None else layer.mask.copy(),
            mask_enabled=layer.mask_enabled,
            clip=layer.clip,
            lock_alpha=layer.lock_alpha,
            group=layer.group,
            adjustment=layer.adjustment,
            effects=layer.effects,
            tone=layer.tone,
            binary=layer.binary,
            # blend_if / vector_data carry mutable state (channel ranges,
            # the stroke list); deep-copy them so edits on the duplicate
            # don't bleed back into the original. Dropping vector_data
            # entirely would silently rasterise a duplicated vector layer.
            blend_if=copy.deepcopy(layer.blend_if),
            vector_data=copy.deepcopy(layer.vector_data),
            color_label=layer.color_label,
        )
        insert_at = self._active_index + 1
        self._layers.insert(insert_at, duplicate)
        self._active_index = insert_at
        self._shift_reference_for_insert(insert_at)
        self._notify()

    def move_active_layer(self, *, up: bool) -> None:
        idx = self._active_index
        target = idx + 1 if up else idx - 1
        if not (0 <= target < len(self._layers)):
            return
        self._layers[idx], self._layers[target] = self._layers[target], self._layers[idx]
        self._active_index = target
        self._swap_reference(idx, target)
        self._notify()
