"""Layer and layer-group data model for the paint document.

The Layer / LayerGroup dataclasses and the layer-domain constants, extracted
from ``document`` so that module stays focused on stack logic. Re-exported
from ``document`` for backwards compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from Imervue.paint.compositing import LAYER_BLEND_MODES


DEFAULT_LAYER_NAME = "Layer"
BACKGROUND_LAYER_NAME = "Background"

# Eight raster-editor colour labels artists use to triage layers.
# ``None`` is the "no label" default; the seven named values match the
# colours raster paint apps / Photoshop tint the row chip with.
LAYER_LABELS = ("red", "orange", "yellow", "green", "blue", "violet", "grey")

# Layer-group blend modes — ``pass_through`` keeps each member layer's
# own blend mode (the group only multiplies opacity / visibility). The
# other modes match the Layer-level set; non-pass-through groups
# composite their members internally first, then blend the result as a
# unit. For 9a only ``pass_through`` is honoured; the rest are stored
# verbatim so the persisted state survives round-trips, and a future
# pass can wire up internal compositing.
GROUP_BLEND_MODES = ("pass_through", *LAYER_BLEND_MODES)
DEFAULT_GROUP_BLEND_MODE = "pass_through"


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
    group: str | None = None     # name of the LayerGroup this layer belongs to
    adjustment: Any = None       # Adjustment | None — when set the layer is non-destructive
    effects: tuple = ()          # tuple[LayerEffect, ...] — drop shadow / glow / stroke
    blend_if: Any = None         # BlendIf | None — luminance-range visibility gate
    vector_data: Any = None      # VectorLayerData | None — vector strokes; image is the cache
    color_label: str | None = None   # one of LAYER_LABELS or None for "no label"
    tone: Any = None             # ToneSettings | None — render layer as halftone at composite
    binary: Any = None           # BinarySettings | None — 1-bit ink-or-transparent render

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
        if self.color_label is not None and self.color_label not in LAYER_LABELS:
            raise ValueError(
                f"unknown color_label {self.color_label!r}; "
                f"expected None or one of {LAYER_LABELS}",
            )
        self.opacity = max(0.0, min(1.0, float(self.opacity)))


@dataclass
class LayerGroup:
    """Named group of layers with shared visibility / opacity / blend mode.

    Groups are stored in :class:`PaintDocument._groups`; layers point at
    a group via :attr:`Layer.group`. ``expanded`` is a UI-only hint that
    persists across saves so a collapsed group stays collapsed.
    """

    name: str
    visible: bool = True
    opacity: float = 1.0
    blend_mode: str = DEFAULT_GROUP_BLEND_MODE
    locked: bool = False
    expanded: bool = True

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("group name must be non-empty")
        if self.blend_mode not in GROUP_BLEND_MODES:
            raise ValueError(
                f"unknown group blend_mode {self.blend_mode!r}; "
                f"expected one of {GROUP_BLEND_MODES}",
            )
        self.opacity = max(0.0, min(1.0, float(self.opacity)))


