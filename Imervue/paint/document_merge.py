"""Layer merging operations of the paint document.

Divide the active layer, merge down, merge visible and flatten. They rebuild
the layer stack, keep the active and reference layer indices pointing at the
right layers, and invalidate the composite. Pure NumPy, no Qt;
``PaintDocument`` mixes these methods in.
"""
from __future__ import annotations

from typing import Any

from Imervue.paint.layer_model import Layer


class DocumentMergeMixin:
    """Divide, merge and flatten operations of :class:`~Imervue.paint.document.PaintDocument`."""

    def divide_active_layer(
        self, *,
        quantize: int | None = None,
        max_buckets: int | None = None,
    ) -> int:
        """Replace the active layer with one per discovered flat colour.

        Walks the active layer's pixels, groups by quantised colour,
        and inserts a fresh raster layer for each group with that
        bucket's representative colour painted only where the original
        had it. The original layer is removed. Returns the number of
        new layers inserted; ``0`` means the active layer was empty
        / fully transparent and nothing changed.

        ``quantize`` and ``max_buckets`` forward to
        :func:`Imervue.paint.divide_layer.divide_layer_into_color_layers`;
        ``None`` keeps the helper's defaults.
        """
        from Imervue.paint.divide_layer import (
            divide_layer_into_color_layers,
            render_color_layer,
        )
        layer = self.active_layer()
        if layer is None or self.shape is None:
            return 0
        kwargs: dict[str, Any] = {}
        if quantize is not None:
            kwargs["quantize"] = int(quantize)
        if max_buckets is not None:
            kwargs["max_buckets"] = int(max_buckets)
        color_layers = divide_layer_into_color_layers(layer.image, **kwargs)
        if not color_layers:
            return 0
        h, w = self.shape
        old_index = self._active_index
        old_name = layer.name
        new_layers: list[Layer] = []
        for color_layer in color_layers:
            new_layers.append(Layer(
                name=f"{old_name} {color_layer.color}",
                image=render_color_layer((h, w), color_layer),
                opacity=layer.opacity,
                blend_mode=layer.blend_mode,
                visible=layer.visible,
                group=layer.group,
                color_label=layer.color_label,
            ))
        # Drop the source and splice in the per-colour layers in its
        # slot, biggest-bucket first (the largest flat fill ends up at
        # the bottom of the run, matching the input's visual order).
        del self._layers[old_index]
        for offset, fresh in enumerate(new_layers):
            self._layers.insert(old_index + offset, fresh)
        self._active_index = old_index
        # Reference layer follows the layer-list mutation: it pointed
        # at the source if anywhere, so clear it — none of the new
        # layers carries the original's authority as a reference.
        if self._reference_layer_index is not None:
            ref = self._reference_layer_index
            if ref == old_index:
                self._reference_layer_index = None
            elif ref > old_index:
                self._reference_layer_index = ref + len(new_layers) - 1
        self._notify()
        return len(new_layers)

    def merge_down(self) -> bool:
        """Merge the active layer with the one immediately below it.

        Returns ``True`` if anything changed. A no-op (returns
        ``False``) when the active layer is the bottom of the stack —
        there is nothing to merge into.
        """
        from Imervue.paint.layer_ops import merge_layer_pair
        idx = self._active_index
        if idx <= 0:
            return False
        below = self._layers[idx - 1]
        above = self._layers[idx]
        merged = merge_layer_pair(below, above)
        self._layers[idx - 1] = merged
        del self._layers[idx]
        self._active_index = idx - 1
        # The pair below+above was collapsed into below's slot; either
        # of those being the reference resolves to the merged layer.
        ref = self._reference_layer_index
        if ref == idx:
            self._reference_layer_index = idx - 1
        elif ref is not None and ref > idx:
            self._reference_layer_index = ref - 1
        self._notify()
        return True

    def merge_visible(self) -> bool:
        """Replace every visible layer with their merged composite.

        Hidden layers are kept untouched in their original positions.
        The merged layer is inserted where the lowest visible layer
        sat. Returns ``True`` if any merge actually happened.
        """
        from Imervue.paint.layer_ops import composite_visible_layers
        if not self._layers:
            return False
        shape = self.shape
        if shape is None:
            return False
        merged = composite_visible_layers(self._layers, shape, groups=self._groups)
        if merged is None:
            return False
        # Find indices of effectively-visible layers; the merged result
        # replaces the lowest one and the rest are dropped. Group
        # visibility is honoured here so a layer inside a hidden group
        # survives merge_visible — it's not in the on-screen composite.
        visible_idx = [
            i for i, layer in enumerate(self._layers)
            if self._is_layer_effectively_visible(layer)
        ]
        if len(visible_idx) <= 1:
            # Nothing to merge — single visible layer is already the
            # composite of the visible set.
            return False
        kept_layers, new_active, new_ref = self._rebuild_after_merge(
            visible_idx, merged,
        )
        self._layers = kept_layers
        self._active_index = max(0, new_active)
        self._reference_layer_index = new_ref if new_ref >= 0 else None
        self._notify()
        return True

    def _rebuild_after_merge(
        self, visible_idx: list[int], merged,
    ) -> tuple[list, int, int]:
        """Walk the layer list once, replacing the lowest visible slot
        with ``merged`` and dropping the other visible layers. Returns
        the new layer list and the (re-mapped) active / reference indices.
        """
        active_was_visible = self._active_index in visible_idx
        ref_was_visible = self._reference_layer_index in visible_idx
        kept_layers: list = []
        new_active = -1
        new_ref = -1
        merged_slot = -1
        merged_inserted = False
        for i, layer in enumerate(self._layers):
            if i in visible_idx:
                if not merged_inserted:
                    kept_layers.append(merged)
                    merged_slot = len(kept_layers) - 1
                    if active_was_visible:
                        new_active = merged_slot
                    merged_inserted = True
                continue
            kept_layers.append(layer)
            if i == self._active_index:
                new_active = len(kept_layers) - 1
            if i == self._reference_layer_index:
                new_ref = len(kept_layers) - 1
        if ref_was_visible:
            # Fold the reference onto the merged stand-in so the bucket
            # keeps a coherent target after the merge.
            new_ref = merged_slot
        return kept_layers, new_active, new_ref

    def flatten(self) -> bool:
        """Replace the entire stack with one ``Background`` layer.

        Visible layers are merged into a single Layer; hidden layers
        are dropped. Returns ``True`` if the stack actually shrank.
        """
        from Imervue.paint.layer_ops import flatten_layers
        if not self._layers:
            return False
        shape = self.shape
        if shape is None:
            return False
        flat = flatten_layers(self._layers, shape, groups=self._groups)
        if len(self._layers) == 1 and self._layers[0].image is flat.image:
            return False
        self._layers = [flat]
        self._active_index = 0
        self._reference_layer_index = None
        self._notify()
        return True
