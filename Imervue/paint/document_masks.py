"""Create, apply and edit layer masks."""
from __future__ import annotations

import numpy as np


class DocumentMasksMixin:
    """Create, apply and edit layer masks."""

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
        return self._set_layer_property(index, "mask_enabled", enabled, normalize=bool)
