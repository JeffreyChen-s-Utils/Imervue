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
    clip: bool = False     # clip to layer below

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
            clip=layer.clip,
        )
        self._layers.insert(self._active_index + 1, copy)
        self._active_index += 1
        self._notify()

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
