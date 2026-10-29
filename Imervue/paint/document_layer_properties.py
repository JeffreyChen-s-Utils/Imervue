"""Layer rendering properties and mutation notification."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from Imervue.paint.compositing import LAYER_BLEND_MODES
from Imervue.paint.layer_model import LAYER_LABELS


class DocumentLayerPropertiesMixin:
    """Layer rendering properties and mutation notification."""

    def set_layer_effects(
        self, index: int = -1, *, effects: tuple,
    ) -> bool:
        """Replace a layer's effect tuple in one shot."""
        return self._set_layer_property(index, "effects", effects, normalize=tuple)

    def set_layer_locked(self, index: int = -1, *, locked: bool) -> bool:
        """Toggle the full-layer lock (no edits allowed)."""
        return self._set_layer_property(index, "locked", locked, normalize=bool)

    def set_layer_lock_alpha(self, index: int = -1, *, lock_alpha: bool) -> bool:
        """Toggle the lock-alpha (transparent-pixel) lock.

        When ``lock_alpha`` is on, paint operations should only affect
        pixels that already have alpha > 0. The dispatcher consults
        :func:`Imervue.paint.selection_ops.lock_alpha_mask` to combine
        this flag with the active selection.
        """
        return self._set_layer_property(index, "lock_alpha", lock_alpha, normalize=bool)

    def set_layer_tone(self, index: int = -1, *, tone: Any) -> bool:
        """Toggle / replace the per-layer halftone-render setting.

        ``tone`` should be a :class:`Imervue.paint.halftone.ToneSettings`
        or ``None`` to revert to plain raster rendering. Returns ``True``
        if the assignment changed the layer.
        """
        return self._set_layer_property(index, "tone", tone)

    def set_layer_binary(self, index: int = -1, *, binary: Any) -> bool:
        """Toggle / replace the per-layer 1-bit-render setting.

        ``binary`` should be a
        :class:`Imervue.paint.binary_layer.BinarySettings` or ``None``
        to revert to plain raster rendering. Returns ``True`` if the
        assignment changed the layer.
        """
        return self._set_layer_property(index, "binary", binary)

    def set_layer_color_label(
        self, index: int = -1, *, label: str | None,
    ) -> bool:
        """Tag a layer with a colour label (or clear it with ``None``).

        Returns ``True`` if the label changed. Unknown label values
        raise ``ValueError`` so a typo can't silently mis-tag a layer.
        """
        if label not in (None, *LAYER_LABELS):
            raise ValueError(
                f"unknown color_label {label!r}; "
                f"expected None or one of {LAYER_LABELS}",
            )
        return self._set_layer_property(index, "color_label", label)

    def set_layer_clip(self, index: int = -1, *, clip: bool) -> bool:
        """Toggle the layer's clip-to-layer-below flag."""
        return self._set_layer_property(index, "clip", clip, normalize=bool)

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

    def _set_layer_property(
        self, index: int, name: str, value: Any,
        *, normalize: Callable[[Any], Any] = lambda value: value,
    ) -> bool:
        """Normalize and change one resolved layer property, notifying only on change."""
        layer = self._resolve_layer(index)
        if layer is None:
            return False
        value = normalize(value)
        if getattr(layer, name) == value:
            return False
        setattr(layer, name, value)
        self._notify()
        return True
