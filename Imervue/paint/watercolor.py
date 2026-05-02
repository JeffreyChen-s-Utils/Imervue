"""Wet-on-wet watercolor simulation primitives.

A simple two-field model that approximates watercolor's
characteristic "pigment diffuses through wet paper" behaviour:

* ``water`` — per-pixel water amount (float32, ``[0, ~3]``). Bigger
  values mean wetter, longer-spreading pigment.
* ``pigment`` — per-pixel RGB pigment (float32 in ``[0, 1]``). Where
  there's no water, pigment is "stuck" and shows at full intensity.

Each frame the dispatcher does:

  1. ``add_dab`` for every brush stamp the user lays down (pigment +
     water deposit with a soft Gaussian falloff).
  2. ``diffuse`` once or twice — water carries pigment to the 4
     immediate neighbours via simple averaging.
  3. ``evaporate`` between strokes — water amount drops, leaving the
     diffused pigment in place to show through the dry paper.

The pigment field composites back to the canvas via
:func:`composite_to_canvas`, which mixes pigment colour over the
existing canvas pixels weighted by pigment intensity.

Pure numpy. The model is intentionally minimal — production
watercolor sims use multi-layer pigment / fluid dynamics with
capillary action; this module is "good enough for a paint app's
preview".
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class WetField:
    """Per-pixel water + pigment state for watercolor simulation."""

    water: np.ndarray    # HxW float32
    pigment: np.ndarray  # HxWx3 float32

    @classmethod
    def empty(cls, shape: tuple[int, int]) -> WetField:
        h, w = shape
        return cls(
            water=np.zeros((h, w), dtype=np.float32),
            pigment=np.zeros((h, w, 3), dtype=np.float32),
        )

    @property
    def shape(self) -> tuple[int, int]:
        return self.water.shape


def add_dab(
    field: WetField,
    cx: float,
    cy: float,
    radius: float,
    *,
    water: float = 1.0,
    color: tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Deposit water + pigment at ``(cx, cy)`` with a Gaussian
    falloff over ``radius`` pixels.

    Mutates ``field`` in place."""
    if radius <= 0:
        return
    h, w = field.water.shape
    if water <= 0:
        return
    sigma = max(0.5, float(radius) / 2.0)
    ys, xs = np.indices((h, w), dtype=np.float32)
    dx = xs - float(cx)
    dy = ys - float(cy)
    falloff = np.exp(-(dx * dx + dy * dy) / (2.0 * sigma * sigma))
    deposit = falloff * float(water)
    field.water[...] = field.water + deposit
    color_arr = np.array(color, dtype=np.float32) / 255.0
    pigment_deposit = deposit[..., None] * color_arr[None, None, :]
    # Pigment accumulates additively up to a cap of 1.0 per channel
    # (pigment is "concentration"; saturation at 1 is effectively
    # opaque ink).
    field.pigment[...] = np.clip(
        field.pigment + pigment_deposit, 0.0, 1.0,
    )


def diffuse(field: WetField, *, rate: float = 0.2) -> None:
    """Spread water + pigment to the 4-connectivity neighbours.

    ``rate`` in ``[0, 0.25]`` controls how much each neighbour
    contribution mixes into the pixel per step. A value of 0 means
    no diffusion; 0.25 is the maximum stable rate (each neighbour
    contributes a quarter of its mass)."""
    rate = max(0.0, min(0.25, float(rate)))
    if rate <= 0.0:
        return

    def _diffuse_field(arr: np.ndarray) -> np.ndarray:
        # 4-neighbour average via padded shifts — boundary pixels see
        # zero outside the canvas (effectively bleeding off the edge).
        padded = np.pad(arr, 1 if arr.ndim == 2 else ((1, 1), (1, 1), (0, 0)))
        if arr.ndim == 2:
            up = padded[:-2, 1:-1]
            down = padded[2:, 1:-1]
            left = padded[1:-1, :-2]
            right = padded[1:-1, 2:]
        else:
            up = padded[:-2, 1:-1, :]
            down = padded[2:, 1:-1, :]
            left = padded[1:-1, :-2, :]
            right = padded[1:-1, 2:, :]
        # Weight pigment diffusion by where there's water — pigment
        # only travels where water carries it.
        return arr + rate * (up + down + left + right - 4.0 * arr)

    # Diffuse water first, then pigment with the same rate but masked
    # by water presence (no water → no pigment movement).
    new_water = _diffuse_field(field.water)
    water_mask = (field.water > 1e-6).astype(np.float32)
    new_pigment = field.pigment + (
        _diffuse_field(field.pigment) - field.pigment
    ) * water_mask[..., None]
    field.water[...] = np.clip(new_water, 0.0, 100.0)
    field.pigment[...] = np.clip(new_pigment, 0.0, 1.0)


def evaporate(field: WetField, *, rate: float = 0.05) -> None:
    """Reduce water amount uniformly. Pigment stays put — that's what
    "drying" looks like.

    ``rate`` in ``[0, 1]`` is the fraction of water removed per call."""
    rate = max(0.0, min(1.0, float(rate)))
    if rate <= 0.0:
        return
    field.water[...] = field.water * (1.0 - rate)


def composite_to_canvas(
    canvas: np.ndarray, field: WetField,
) -> bool:
    """Mix the wet field's pigment onto ``canvas`` in place.

    Pigment intensity acts as the deposit alpha — each pixel's
    pigment magnitude (max-of-RGB) becomes the alpha at which the
    pigment colour mixes onto the canvas. Returns ``True`` if any
    pixel actually changed.
    """
    if (
        canvas.ndim != 3
        or canvas.shape[2] != 4
        or canvas.dtype != np.uint8
    ):
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got "
            f"{canvas.shape} {canvas.dtype}",
        )
    if canvas.shape[:2] != field.shape:
        raise ValueError(
            f"canvas shape {canvas.shape[:2]} does not match "
            f"field {field.shape}",
        )
    pigment_alpha = np.max(field.pigment, axis=-1)
    if not (pigment_alpha > 0).any():
        return False

    canvas_rgb = canvas[..., :3].astype(np.float32) / 255.0
    pigment_rgb = field.pigment   # already in [0, 1]
    alpha = pigment_alpha[..., None]
    blended = canvas_rgb * (1.0 - alpha) + pigment_rgb * alpha
    canvas[..., :3] = np.clip(blended * 255.0, 0.0, 255.0).astype(np.uint8)
    return True


def _gaussian_kernel_size(radius: float) -> int:
    """Convenience for callers that want to know the effective
    footprint of an ``add_dab`` call."""
    return max(3, int(math.ceil(radius * 4.0)) | 1)
