"""1-bit binary "ink" layer rendering.

MediBang exposes a layer type whose pixels are either fully-opaque ink
or fully-transparent — no grey in between. It saves space, avoids
edge halos around inks, and matches the print convention for line art
that goes to a black-and-white plate.

Imervue stores the type as a per-layer hint on
:attr:`Imervue.paint.document.Layer.binary`. The compositor reads
``layer.binary`` and, when set, hands the layer through
:func:`render_binary_layer` to produce the thresholded version that
gets blended on top — non-destructive, so toggling the flag off
restores the original soft strokes.

The default threshold (128) puts the cut-off at 50% alpha which is
where soft brush dabs are visually "filled in" already, keeping the
inked silhouette close to what the artist sees.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Threshold acts on the alpha channel by default. Use the luma source
# instead when the artist paints with grey on white-opaque inputs.
BINARY_SOURCE_ALPHA = "alpha"
BINARY_SOURCE_LUMA = "luma"
BINARY_SOURCES = (BINARY_SOURCE_ALPHA, BINARY_SOURCE_LUMA)
DEFAULT_BINARY_SOURCE = BINARY_SOURCE_ALPHA

DEFAULT_BINARY_THRESHOLD = 128
BINARY_THRESHOLD_MIN = 0
BINARY_THRESHOLD_MAX = 255


@dataclass(frozen=True)
class BinarySettings:
    """Per-layer 1-bit render settings.

    ``threshold`` is the cut-off (0..255). With the default
    ``alpha`` source: pixels with alpha strictly greater than
    ``threshold`` become fully-opaque ink; everything else becomes
    transparent. With the ``luma`` source: dark luma → ink,
    matching the "black ink on white paper" workflow.
    """

    threshold: int = DEFAULT_BINARY_THRESHOLD
    color: tuple[int, int, int] = (0, 0, 0)
    source: str = DEFAULT_BINARY_SOURCE

    def __post_init__(self) -> None:
        if not BINARY_THRESHOLD_MIN <= int(self.threshold) <= BINARY_THRESHOLD_MAX:
            raise ValueError(
                f"threshold must be in [{BINARY_THRESHOLD_MIN}, "
                f"{BINARY_THRESHOLD_MAX}], got {self.threshold}",
            )
        if len(self.color) != 3:
            raise ValueError(f"color must be a 3-tuple, got {self.color!r}")
        for component in self.color:
            if not 0 <= int(component) <= 255:
                raise ValueError(
                    f"color components must be in 0..255, got {self.color}",
                )
        if self.source not in BINARY_SOURCES:
            raise ValueError(
                f"unknown source {self.source!r}; "
                f"expected one of {BINARY_SOURCES}",
            )

    def to_dict(self) -> dict:
        return {
            "threshold": int(self.threshold),
            "color": list(self.color),
            "source": str(self.source),
        }

    @classmethod
    def from_dict(cls, raw: dict | None) -> BinarySettings | None:
        """Re-hydrate from a saved dict; ``None`` / malformed → ``None``.

        The compositor treats a missing binary as "render normally",
        so a corrupt entry should fall back to plain rendering rather
        than crash the whole open-document path.
        """
        if not isinstance(raw, dict):
            return None
        try:
            color_raw = raw.get("color", [0, 0, 0])
            if not isinstance(color_raw, (list, tuple)) or len(color_raw) != 3:
                return None
            color = (
                int(color_raw[0]), int(color_raw[1]), int(color_raw[2]),
            )
            return cls(
                threshold=int(raw.get("threshold", DEFAULT_BINARY_THRESHOLD)),
                color=color,
                source=str(raw.get("source", DEFAULT_BINARY_SOURCE)),
            )
        except (TypeError, ValueError):
            return None


def render_binary_layer(
    layer: np.ndarray, settings: BinarySettings,
) -> np.ndarray:
    """Convert ``layer`` into a 1-bit ink-or-transparent buffer.

    Returns a fresh HxWx4 uint8 RGBA buffer the same size as ``layer``;
    the input is not mutated. Pixels above the threshold become fully
    opaque ``settings.color``; everything else is fully transparent.
    """
    if layer.ndim != 3 or layer.shape[2] != 4 or layer.dtype != np.uint8:
        raise ValueError(
            f"layer must be HxWx4 uint8 RGBA, got shape={layer.shape}"
            f" dtype={layer.dtype}",
        )
    if settings.source == BINARY_SOURCE_ALPHA:
        source = layer[..., 3]
        ink_mask = source > int(settings.threshold)
    else:
        rgb = layer[..., :3].astype(np.float32) / 255.0
        luma = (
            0.2126 * rgb[..., 0]
            + 0.7152 * rgb[..., 1]
            + 0.0722 * rgb[..., 2]
        )
        # Luma source: dark (low luma) is ink; gate by alpha so empty
        # transparent pixels never count as ink even when their RGB
        # happens to read as black.
        luma_8 = (luma * 255.0).astype(np.uint8)
        ink_mask = (luma_8 < int(settings.threshold)) & (layer[..., 3] > 0)

    out = np.zeros_like(layer)
    out[ink_mask, 0] = int(settings.color[0])
    out[ink_mask, 1] = int(settings.color[1])
    out[ink_mask, 2] = int(settings.color[2])
    out[ink_mask, 3] = 255
    return out
