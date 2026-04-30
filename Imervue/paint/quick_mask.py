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

Pure numpy / Qt-free.
"""
from __future__ import annotations

import numpy as np

DEFAULT_OVERLAY_COLOR = (255, 0, 0)
DEFAULT_OVERLAY_ALPHA = 128


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
