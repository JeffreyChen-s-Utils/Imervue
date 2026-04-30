"""PaintDocument — layer stack + selection + active layer.

The Paint workspace draws against a single document. Tools mutate
``document.active_layer().image`` in place, the document broadcasts a
"changed" signal-via-callback, and the canvas re-composites the stack
on the next paint.

Pure-Python; no Qt dependency. The layer dock subscribes to the
``listen`` callback to refresh its visible state. The document also
caches the last composite so painting one stroke doesn't pay
N-times-the-work to recomposite — only the cache is invalidated; the
canvas's next paint pays the recomposite cost once.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from Imervue.paint.compositing import LAYER_BLEND_MODES, composite_stack

DEFAULT_LAYER_NAME = "Layer"
BACKGROUND_LAYER_NAME = "Background"


@dataclass
class Layer:
    """A single layer in the stack.

    ``image`` is HxWx4 uint8 RGBA; the document keeps every layer at
    the same shape. ``mask`` (optional) is HxW uint8 alpha used by the
    layer-mask path; ``None`` means no mask.
    """

    name: str
    image: np.ndarray
    opacity: float = 1.0
    blend_mode: str = "normal"
    visible: bool = True
    locked: bool = False
    mask: np.ndarray | None = None
    mask_enabled: bool = True
    clip: bool = False           # clip to layer below
    lock_alpha: bool = False     # paint only where alpha > 0 already exists

    @property
    def effective_mask(self) -> np.ndarray | None:
        """Mask used by compositing — ``None`` if disabled or not set."""
        if self.mask is None or not self.mask_enabled:
            return None
        return self.mask

    def __post_init__(self) -> None:
        if self.image.ndim != 3 or self.image.shape[2] != 4 or self.image.dtype != np.uint8:
            raise ValueError(
                f"layer image must be HxWx4 uint8 RGBA, "
                f"got {self.image.shape} {self.image.dtype}",
            )
        if self.blend_mode not in LAYER_BLEND_MODES:
            raise ValueError(
                f"unknown blend_mode {self.blend_mode!r}; "
                f"expected one of {LAYER_BLEND_MODES}",
            )
        self.opacity = max(0.0, min(1.0, float(self.opacity)))


class PaintDocument:
    """Layer stack + active-layer pointer + selection mask.

    ``shape`` is ``(height, width)`` — every layer added must match it.
    The document is empty until :meth:`load_image` or :meth:`add_layer`
    runs.
    """

    def __init__(self):
        self._layers: list[Layer] = []
        self._active_index: int = -1
        self._selection: np.ndarray | None = None
        self._composite_cache: np.ndarray | None = None
        self._listeners: list[Callable[[], None]] = []

    # ---- listeners -------------------------------------------------------

    def listen(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def _unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)
        return _unsubscribe

    def _notify(self) -> None:
        self._composite_cache = None
        for cb in list(self._listeners):
            cb()

    # ---- shape / layer access -------------------------------------------

    @property
    def shape(self) -> tuple[int, int] | None:
        if not self._layers:
            return None
        return self._layers[0].image.shape[:2]

    @property
    def layer_count(self) -> int:
        return len(self._layers)

    def layers(self) -> list[Layer]:
        return list(self._layers)

    def layer_at(self, index: int) -> Layer:
        return self._layers[index]

    def active_layer(self) -> Layer | None:
        if 0 <= self._active_index < len(self._layers):
            return self._layers[self._active_index]
        return None

    def active_layer_index(self) -> int:
        return self._active_index

    def set_active_layer(self, index: int) -> None:
        if not (0 <= index < len(self._layers)):
            raise IndexError(f"active layer index {index} out of range")
        if index == self._active_index:
            return
        self._active_index = index
        self._notify()

    # ---- layer ops ------------------------------------------------------

    def load_image(self, arr: np.ndarray) -> None:
        """Replace the document with a single Background layer of ``arr``."""
        if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
            raise ValueError(
                f"image must be HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}",
            )
        self._layers = [Layer(name=BACKGROUND_LAYER_NAME, image=np.ascontiguousarray(arr))]
        self._active_index = 0
        self._selection = None
        self._notify()

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
        insert_at = self._active_index + 1 if on_top_of_active else len(self._layers)
        insert_at = min(insert_at, len(self._layers))
        self._layers.insert(insert_at, layer)
        self._active_index = insert_at
        self._notify()
        return layer

    def remove_active_layer(self) -> None:
        if self._active_index < 0 or len(self._layers) <= 1:
            return  # never remove the last layer
        del self._layers[self._active_index]
        self._active_index = max(0, self._active_index - 1)
        self._notify()

    def duplicate_active_layer(self) -> None:
        layer = self.active_layer()
        if layer is None:
            return
        copy = Layer(
            name=f"{layer.name} copy",
            image=layer.image.copy(),
            opacity=layer.opacity,
            blend_mode=layer.blend_mode,
            visible=layer.visible,
            locked=layer.locked,
            mask=None if layer.mask is None else layer.mask.copy(),
            mask_enabled=layer.mask_enabled,
            clip=layer.clip,
        )
        self._layers.insert(self._active_index + 1, copy)
        self._active_index += 1
        self._notify()

    # ---- layer mask -----------------------------------------------------

    def set_layer_locked(self, index: int = -1, *, locked: bool) -> bool:
        """Toggle the full-layer lock (no edits allowed)."""
        layer = self._resolve_layer(index)
        if layer is None or layer.locked == bool(locked):
            return False
        layer.locked = bool(locked)
        self._notify()
        return True

    def set_layer_lock_alpha(self, index: int = -1, *, lock_alpha: bool) -> bool:
        """Toggle the lock-alpha (transparent-pixel) lock.

        When ``lock_alpha`` is on, paint operations should only affect
        pixels that already have alpha > 0. The dispatcher consults
        :func:`Imervue.paint.selection_ops.lock_alpha_mask` to combine
        this flag with the active selection.
        """
        layer = self._resolve_layer(index)
        if layer is None or layer.lock_alpha == bool(lock_alpha):
            return False
        layer.lock_alpha = bool(lock_alpha)
        self._notify()
        return True

    def set_layer_clip(self, index: int = -1, *, clip: bool) -> bool:
        """Toggle the layer's clip-to-layer-below flag."""
        layer = self._resolve_layer(index)
        if layer is None or layer.clip == bool(clip):
            return False
        layer.clip = bool(clip)
        self._notify()
        return True

    def selection_from_layer_alpha(
        self, index: int = -1, *, threshold: int = 0,
    ) -> bool:
        """Replace the active selection with one derived from a layer's alpha.

        Pixels with alpha strictly greater than ``threshold`` become
        selected. ``threshold=0`` matches MediBang's "Select Layer"
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

    def add_layer_mask(self, index: int = -1, *, fill: int = 255) -> bool:
        """Attach a fresh ``HxW`` uint8 mask to a layer.

        ``fill`` controls the initial value (0 = fully hidden,
        255 = fully visible). Returns ``True`` if a mask was added /
        replaced.
        """
        layer = self._resolve_layer(index)
        if layer is None:
            return False
        if not 0 <= int(fill) <= 255:
            raise ValueError(f"fill must be in [0, 255], got {fill!r}")
        h, w = layer.image.shape[:2]
        layer.mask = np.full((h, w), int(fill), dtype=np.uint8)
        layer.mask_enabled = True
        self._notify()
        return True

    def add_layer_mask_from_selection(self, index: int = -1) -> bool:
        """Build a layer mask from the active selection.

        Selected pixels become 255, the rest 0. With no active
        selection the mask is initialised to fully-visible (the
        selection-less default).
        """
        layer = self._resolve_layer(index)
        if layer is None:
            return False
        h, w = layer.image.shape[:2]
        if self._selection is None:
            layer.mask = np.full((h, w), 255, dtype=np.uint8)
        else:
            if self._selection.shape != (h, w):
                raise ValueError(
                    f"selection shape {self._selection.shape} does not "
                    f"match layer {(h, w)}",
                )
            layer.mask = np.where(self._selection, 255, 0).astype(np.uint8)
        layer.mask_enabled = True
        self._notify()
        return True

    def clear_layer_mask(self, index: int = -1) -> bool:
        """Discard a layer's mask. Returns ``True`` if there was one."""
        layer = self._resolve_layer(index)
        if layer is None or layer.mask is None:
            return False
        layer.mask = None
        layer.mask_enabled = True
        self._notify()
        return True

    def invert_layer_mask(self, index: int = -1) -> bool:
        """Bitwise-invert a layer mask in place. No-op if mask is None."""
        layer = self._resolve_layer(index)
        if layer is None or layer.mask is None:
            return False
        layer.mask = (255 - layer.mask).astype(np.uint8)
        self._notify()
        return True

    def apply_layer_mask(self, index: int = -1) -> bool:
        """Bake a mask into the layer's alpha channel and discard the mask.

        ``layer.image[..., 3] *= mask / 255``. After applying, the
        layer behaves as if it never had a mask — the visibility
        information is now in the alpha channel itself. Returns
        ``True`` if anything was baked.
        """
        layer = self._resolve_layer(index)
        if layer is None or layer.mask is None:
            return False
        alpha = layer.image[..., 3].astype(np.float32)
        mask_f = layer.mask.astype(np.float32) / 255.0
        new_alpha = np.clip(alpha * mask_f, 0.0, 255.0).astype(np.uint8)
        layer.image[..., 3] = new_alpha
        layer.mask = None
        layer.mask_enabled = True
        self._notify()
        return True

    def set_layer_mask_enabled(self, index: int = -1, *, enabled: bool) -> bool:
        """Toggle whether the mask is applied during compositing.

        The mask data is preserved — disabling just makes
        :attr:`Layer.effective_mask` return ``None`` so compositing
        skips it. Returns ``True`` if the flag changed.
        """
        layer = self._resolve_layer(index)
        if layer is None:
            return False
        if layer.mask_enabled == bool(enabled):
            return False
        layer.mask_enabled = bool(enabled)
        self._notify()
        return True

    def _resolve_layer(self, index: int) -> Layer | None:
        if not self._layers:
            return None
        if index == -1:
            if self._active_index < 0:
                return None
            return self._layers[self._active_index]
        if not 0 <= index < len(self._layers):
            raise IndexError(f"layer index {index} out of range")
        return self._layers[index]

    # ---- crop ----------------------------------------------------------

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
        if self._selection is not None:
            self._selection = crop_to_rect(self._selection, rect)
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

    # ---- canvas transforms ---------------------------------------------

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
        merged = composite_visible_layers(self._layers, shape)
        if merged is None:
            return False
        # Find indices of visible layers; the merged result replaces
        # the lowest one and the rest are dropped.
        visible_idx = [
            i for i, layer in enumerate(self._layers)
            if layer.visible and layer.opacity > 0
        ]
        if len(visible_idx) <= 1:
            # Nothing to merge — single visible layer is already the
            # composite of the visible set.
            return False
        # Was the active layer one of the visibles? Track its identity
        # so the active pointer survives the rebuild.
        active_was_visible = self._active_index in visible_idx
        kept_layers: list = []
        new_active = -1
        merged_inserted = False
        for i, layer in enumerate(self._layers):
            if i in visible_idx:
                if not merged_inserted:
                    kept_layers.append(merged)
                    if active_was_visible:
                        new_active = len(kept_layers) - 1
                    merged_inserted = True
                # All other visible layers are absorbed.
            else:
                kept_layers.append(layer)
                if i == self._active_index:
                    new_active = len(kept_layers) - 1
        self._layers = kept_layers
        self._active_index = max(0, new_active)
        self._notify()
        return True

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
        flat = flatten_layers(self._layers, shape)
        if len(self._layers) == 1 and self._layers[0].image is flat.image:
            return False
        self._layers = [flat]
        self._active_index = 0
        self._notify()
        return True

    def move_active_layer(self, *, up: bool) -> None:
        idx = self._active_index
        target = idx + 1 if up else idx - 1
        if not (0 <= target < len(self._layers)):
            return
        self._layers[idx], self._layers[target] = self._layers[target], self._layers[idx]
        self._active_index = target
        self._notify()

    def set_layer_attribute(self, index: int, **kwargs) -> None:
        """Tweak a single layer's opacity / blend_mode / visible / name."""
        if not (0 <= index < len(self._layers)):
            raise IndexError(f"layer index {index} out of range")
        layer = self._layers[index]
        changed = False
        for key, value in kwargs.items():
            if not hasattr(layer, key):
                raise ValueError(f"unknown layer attribute {key!r}")
            current = getattr(layer, key)
            new_value = value
            if key == "opacity":
                new_value = max(0.0, min(1.0, float(value)))
            elif key == "blend_mode" and value not in LAYER_BLEND_MODES:
                raise ValueError(
                    f"unknown blend_mode {value!r}; expected one of {LAYER_BLEND_MODES}",
                )
            if new_value != current:
                setattr(layer, key, new_value)
                changed = True
        if changed:
            self._notify()

    # ---- selection ------------------------------------------------------

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
        for cb in list(self._listeners):
            cb()

    # ---- composite ------------------------------------------------------

    def composite(self) -> np.ndarray | None:
        """Return the flattened RGBA frame, computing once and caching."""
        if not self._layers:
            return None
        if self._composite_cache is None:
            shape = self.shape
            if shape is None:
                return None
            self._composite_cache = composite_stack(self._layers, shape)
        return self._composite_cache

    def invalidate_composite(self) -> None:
        """Force the next :meth:`composite` to recompute."""
        self._composite_cache = None
        for cb in list(self._listeners):
            cb()

    # ---- internals ------------------------------------------------------

    def _unique_layer_name(self) -> str:
        existing = {layer.name for layer in self._layers}
        i = len(self._layers)
        while True:
            candidate = f"{DEFAULT_LAYER_NAME} {i}"
            if candidate not in existing:
                return candidate
            i += 1
