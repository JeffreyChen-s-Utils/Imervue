"""Quick mask — render the active selection as a translucent overlay.

In MediBang's "Quick Mask" mode, the user toggles a button and the
selection visualisation flips into a paintable overlay: red over
everything that's NOT in the selection. The user can then paint
additions / subtractions on the overlay with the brush, and toggling
back converts the painted overlay into a fresh selection.

This module ships the two pure-numpy halves of that loop:

* :func:`quick_mask_overlay` — render a selection as an HxWx4 RGBA
  buffer the canvas widget can blit on top of the layer composite.
* :func:`selection_from_quick_mask` — invert: read a painted overlay
  buffer and produce the bool selection that matches it.

Plus the workspace-side toggle hand-off helpers used by Phase 24e:

* :func:`enter_mode` — build a :class:`QuickMaskState` snapshotting
  the active layer's pixels and producing a paintable RGBA proxy.
* :func:`exit_mode` — recover the original pixels + a selection mask
  from a painted proxy.

Pure numpy / Qt-free.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_OVERLAY_COLOR = (255, 0, 0)
DEFAULT_OVERLAY_ALPHA = 128

# Saturation values for the toggle-mode proxy buffer. The proxy's
# RGB channels are always the overlay colour, baked at half opacity
# so the layer image showing through still reads as itself rather
# than turning solid red. Alpha tracks the selection coverage.
QUICK_MASK_PROXY_RGB = (
    int(round(DEFAULT_OVERLAY_COLOR[0] * 0.5)),
    int(round(DEFAULT_OVERLAY_COLOR[1] * 0.5)),
    int(round(DEFAULT_OVERLAY_COLOR[2] * 0.5)),
)


def quick_mask_overlay(
    selection: np.ndarray,
    *,
    color: tuple[int, int, int] = DEFAULT_OVERLAY_COLOR,
    alpha: int = DEFAULT_OVERLAY_ALPHA,
    invert: bool = True,
) -> np.ndarray:
    """Build an HxWx4 RGBA overlay marking the (un)selected region.

    By default ``invert=True`` paints over the *unselected* region —
    matching Photoshop / MediBang's "anywhere outside the selection"
    quick-mask convention. ``invert=False`` paints over the selected
    region instead, useful for "show what's selected" previews.

    The overlay's alpha channel is the requested ``alpha`` inside the
    masked region and 0 outside, so compositing it onto the canvas
    yields a translucent veil over the masked pixels and a clean
    pass-through everywhere else.
    """
    if selection.ndim != 2:
        raise ValueError(f"selection must be 2-D, got {selection.shape}")
    if selection.dtype != np.bool_:
        raise ValueError(f"selection must be bool, got {selection.dtype}")
    if not 0 <= int(alpha) <= 255:
        raise ValueError(f"alpha must be in [0, 255], got {alpha}")
    h, w = selection.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    region = ~selection if invert else selection
    if not region.any():
        return out
    out[region, 0] = color[0]
    out[region, 1] = color[1]
    out[region, 2] = color[2]
    out[region, 3] = int(alpha)
    return out


def selection_from_quick_mask(
    overlay: np.ndarray,
    *,
    invert: bool = True,
    threshold: int = 0,
) -> np.ndarray:
    """Invert :func:`quick_mask_overlay` — derive a bool selection from
    the painted overlay buffer.

    ``threshold`` is the alpha value the user-painted overlay must
    exceed for a pixel to count as "in the mask"; default 0 picks up
    every pixel with any opacity. ``invert=True`` (default) treats
    the painted region as the *un*selected area, mirroring
    quick_mask_overlay's convention.
    """
    if (
        overlay.ndim != 3
        or overlay.shape[2] != 4
        or overlay.dtype != np.uint8
    ):
        raise ValueError(
            f"overlay must be HxWx4 uint8 RGBA, got {overlay.shape} {overlay.dtype}",
        )
    if not 0 <= int(threshold) <= 255:
        raise ValueError(f"threshold must be in [0, 255], got {threshold}")
    masked_region = overlay[..., 3] > int(threshold)
    return ~masked_region if invert else masked_region


# ---------------------------------------------------------------------------
# Toggle-mode hand-off (Phase 24e)
# ---------------------------------------------------------------------------


@dataclass
class QuickMaskState:
    """Snapshot of everything the workspace needs to round-trip.

    ``original_image`` is a copy of the layer's pixels at toggle-in
    time; restored verbatim on toggle-out so a botched mask never
    damages the underlying art. ``buffer`` is the live HxWx4 RGBA
    proxy whose alpha encodes the in-progress mask coverage.
    """

    layer_index: int
    original_image: np.ndarray
    buffer: np.ndarray

    @property
    def shape(self) -> tuple[int, int]:
        return self.buffer.shape[:2]


def make_proxy_buffer(
    shape: tuple[int, int], selection: np.ndarray | None,
) -> np.ndarray:
    """Build the toggle-mode proxy buffer from an existing selection.

    Returned buffer is HxWx4 uint8 RGBA. R/G/B are the overlay tint
    pre-baked; alpha == 255 inside the selection, 0 outside. ``None``
    selection produces a fully-transparent buffer (the user starts
    painting from a blank slate).
    """
    h, w = shape
    if h <= 0 or w <= 0:
        raise ValueError(f"shape must be positive, got {shape!r}")
    buffer = np.zeros((h, w, 4), dtype=np.uint8)
    buffer[..., 0] = QUICK_MASK_PROXY_RGB[0]
    buffer[..., 1] = QUICK_MASK_PROXY_RGB[1]
    buffer[..., 2] = QUICK_MASK_PROXY_RGB[2]
    if selection is None:
        return buffer
    if selection.shape != (h, w):
        raise ValueError(
            f"selection shape {selection.shape} does not match buffer {shape}",
        )
    buffer[..., 3] = np.where(selection, 255, 0).astype(np.uint8)
    return buffer


def selection_from_proxy(
    buffer: np.ndarray, *, threshold: int = 128,
) -> np.ndarray:
    """Extract a HxW bool selection from the proxy buffer's alpha.

    Pixels with alpha >= ``threshold`` count as selected. Default
    threshold treats half-or-more-opaque overlay as selection so a
    partial stroke barely moves a pixel into the selection — matches
    Photoshop's behaviour.
    """
    if (
        buffer.ndim != 3
        or buffer.shape[2] != 4
        or buffer.dtype != np.uint8
    ):
        raise ValueError(
            f"buffer must be HxWx4 uint8 RGBA, got {buffer.shape}"
            f" {buffer.dtype}",
        )
    if not 0 <= int(threshold) <= 255:
        raise ValueError(f"threshold must be in [0, 255], got {threshold}")
    return buffer[..., 3] >= int(threshold)


def enter_mode(
    layer_image: np.ndarray,
    selection: np.ndarray | None,
    layer_index: int = 0,
) -> QuickMaskState:
    """Build a :class:`QuickMaskState` and freeze the layer's pixels."""
    if (
        layer_image.ndim != 3
        or layer_image.shape[2] != 4
        or layer_image.dtype != np.uint8
    ):
        raise ValueError(
            f"layer_image must be HxWx4 uint8 RGBA, got {layer_image.shape}"
            f" {layer_image.dtype}",
        )
    h, w = layer_image.shape[:2]
    return QuickMaskState(
        layer_index=int(layer_index),
        original_image=layer_image.copy(),
        buffer=make_proxy_buffer((h, w), selection),
    )


def exit_mode(
    state: QuickMaskState, *, threshold: int = 128,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(restored_layer_image, selection_mask)`` for toggle-out.

    Caller is responsible for assigning the restored image back to
    the layer and pushing the selection into the document's
    selection slot.
    """
    selection = selection_from_proxy(state.buffer, threshold=threshold)
    return state.original_image, selection
