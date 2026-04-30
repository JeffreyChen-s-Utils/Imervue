"""Pure-numpy selection refinement helpers.

The :class:`Imervue.paint.document.PaintDocument` stores a single
HxW bool mask as the active selection. The marquee tools in
:mod:`Imervue.paint.selection` *create* selection masks; the helpers
here *refine* an existing one — invert it, expand or contract its
boundary, feather the edge into a soft alpha, build a fresh
all-canvas / empty mask, or derive a mask from a layer's alpha
channel.

Pure numpy / Qt-free; testable without a display server.

Edge philosophy
---------------

* :func:`expand` and :func:`contract` use 4-connectivity dilation /
  erosion in Chebyshev (square-window) form. The radius argument
  is the number of iterations, which equals the maximum number of
  pixels added (expand) or removed (contract) from the mask edge.
* :func:`feather` returns a **float32** alpha mask in ``[0, 1]`` —
  not bool — because softening the edge inherently produces
  fractional coverage. PaintDocument's selection storage keeps
  bool semantics; the float result is for compositing-time alpha
  blending and the dispatcher knows how to consume both.
"""
from __future__ import annotations

import numpy as np

# Rejecting larger radii defends the iterative dilation / erosion
# from accidental DoS via a runaway slider value. 256 covers every
# realistic painting workflow without inviting a 10s pause for one
# misclick.
MAX_RADIUS = 256


def select_all(shape: tuple[int, int]) -> np.ndarray:
    """Return a fresh all-True selection mask of the given ``(h, w)``."""
    h, w = _validate_shape(shape)
    return np.ones((h, w), dtype=np.bool_)


def empty_selection(shape: tuple[int, int]) -> np.ndarray:
    """Return a fresh all-False selection mask of the given ``(h, w)``.

    Mostly used by tests; production code typically passes ``None`` to
    :meth:`PaintDocument.set_selection` to clear a selection.
    """
    h, w = _validate_shape(shape)
    return np.zeros((h, w), dtype=np.bool_)


def invert(mask: np.ndarray) -> np.ndarray:
    """Return ``~mask`` with shape and dtype preserved."""
    _check_bool_mask(mask)
    return np.logical_not(mask)


def expand(mask: np.ndarray, radius: int) -> np.ndarray:
    """Morphological dilation by ``radius`` iterations (4-connectivity).

    Each iteration adds the immediate neighbour pixels. ``radius=0``
    is a no-op that returns a fresh copy. Radii beyond
    :data:`MAX_RADIUS` are rejected.
    """
    _check_bool_mask(mask)
    radius = _validate_radius(radius)
    if radius == 0:
        return mask.copy()
    out = mask.copy()
    for _ in range(radius):
        out = _dilate_once(out)
    return out


def contract(mask: np.ndarray, radius: int) -> np.ndarray:
    """Morphological erosion by ``radius`` iterations (4-connectivity)."""
    _check_bool_mask(mask)
    radius = _validate_radius(radius)
    if radius == 0:
        return mask.copy()
    out = mask.copy()
    for _ in range(radius):
        out = _erode_once(out)
    return out


def feather(mask: np.ndarray, radius: int) -> np.ndarray:
    """Soften the mask edge into a float32 alpha mask in ``[0, 1]``.

    Uses a separable square-window box blur of the bool mask; the
    output is a fresh array — the input is not mutated. ``radius=0``
    short-circuits to a plain bool→float cast.
    """
    _check_bool_mask(mask)
    radius = _validate_radius(radius)
    arr = mask.astype(np.float32)
    if radius == 0:
        return arr
    return _box_blur(arr, radius)


def lock_alpha_mask(
    layer_image: np.ndarray,
    base_selection: np.ndarray | None,
) -> np.ndarray | None:
    """Combine a layer's existing-alpha mask with an optional selection.

    When the active layer has lock-alpha on, paint must only land on
    pixels that already have alpha > 0. This helper produces the
    composite mask:

    * if ``base_selection`` is None — return a bool mask matching the
      layer's alpha > 0 region
    * otherwise — return ``base_selection AND (alpha > 0)``

    Returns ``None`` if the result would be a fresh full-True mask
    (i.e. neither the lock nor a selection narrows the paint region),
    so callers can keep the cheap "no selection" fast path.
    """
    if (
        layer_image.ndim != 3
        or layer_image.shape[2] != 4
        or layer_image.dtype != np.uint8
    ):
        raise ValueError(
            f"layer_image must be HxWx4 uint8 RGBA, "
            f"got {layer_image.shape} {layer_image.dtype}",
        )
    alpha_mask = layer_image[..., 3] > 0
    if base_selection is None:
        return alpha_mask
    if base_selection.shape != alpha_mask.shape:
        raise ValueError(
            f"selection shape {base_selection.shape} does not match "
            f"layer {alpha_mask.shape}",
        )
    return base_selection & alpha_mask


def refine_edge(
    mask: np.ndarray,
    *,
    smooth: int = 0,
    feather: int = 0,
    contrast: float = 0.0,
    shift: int = 0,
) -> np.ndarray:
    """Smooth + feather + contrast + shift the boundary of ``mask``.

    Returns a float32 alpha mask in ``[0, 1]`` — the user-facing
    "Refine Edge" / "Select And Mask" output the dispatcher can apply
    as a layer mask. Pipeline order is fixed (shift → smooth → feather
    → contrast) to give the user predictable layering of effects.

    * ``shift`` (px) — positive grows the boundary outward, negative
      shrinks it inward. Capped to :data:`MAX_RADIUS`.
    * ``smooth`` — open / close pass count that erodes-then-dilates-
      twice-then-erodes; pulls jagged single-pixel artefacts off the
      boundary without changing the overall area much. Each pass is a
      full open + close, so ``smooth = 2`` is much heavier than 1.
    * ``feather`` (px) — separable box-blur radius that fades the
      bool edge into fractional alpha.
    * ``contrast`` in ``[-1, 1]`` — steepens (positive) or softens
      (negative) the alpha curve around 0.5 via a logistic S-curve.
    """
    _check_bool_mask(mask)
    smooth = max(0, min(MAX_RADIUS, int(smooth)))
    feather = _validate_radius(feather)
    contrast = max(-1.0, min(1.0, float(contrast)))
    shift_amount = max(-MAX_RADIUS, min(MAX_RADIUS, int(shift)))

    refined = mask.copy()
    if shift_amount > 0:
        for _ in range(shift_amount):
            refined = _dilate_once(refined)
    elif shift_amount < 0:
        for _ in range(-shift_amount):
            refined = _erode_once(refined)

    if smooth > 0:
        for _ in range(smooth):
            refined = _erode_once(refined)
        for _ in range(2 * smooth):
            refined = _dilate_once(refined)
        for _ in range(smooth):
            refined = _erode_once(refined)

    alpha = refined.astype(np.float32)
    if feather > 0:
        alpha = _box_blur(alpha, feather)

    if contrast > 0.0:
        # Positive contrast steepens the transition via a logistic
        # S-curve around 0.5 — slope tuned so contrast = 1 produces a
        # near-binary mask without quite collapsing the feather.
        k = float(contrast) * 12.0
        alpha = 1.0 / (1.0 + np.exp(-k * (alpha - 0.5)))
        alpha = np.clip(alpha, 0.0, 1.0).astype(np.float32)
    elif contrast < 0.0:
        # Negative contrast softens by lerping every alpha toward
        # mid-grey 0.5; magnitude in [0, 1] controls how far.
        blend = -float(contrast)
        alpha = alpha * (1.0 - blend) + 0.5 * blend
        alpha = np.clip(alpha, 0.0, 1.0).astype(np.float32)
    return alpha


def from_layer_alpha(layer_image: np.ndarray, threshold: int = 0) -> np.ndarray:
    """Build a bool selection from a layer's alpha channel.

    Pixels with alpha strictly greater than ``threshold`` are
    selected. ``threshold=0`` (the default) selects everything that
    has any opacity at all, matching MediBang's "Select Layer" command.
    ``threshold=127`` selects the predominantly-opaque half of a
    semi-transparent layer.
    """
    if (
        layer_image.ndim != 3
        or layer_image.shape[2] != 4
        or layer_image.dtype != np.uint8
    ):
        raise ValueError(
            f"layer_image must be HxWx4 uint8 RGBA, "
            f"got {layer_image.shape} {layer_image.dtype}",
        )
    if not 0 <= int(threshold) <= 255:
        raise ValueError(f"threshold must be in [0, 255], got {threshold!r}")
    return layer_image[..., 3] > int(threshold)


# ---------------------------------------------------------------------------
# Pure-numpy morphological ops
# ---------------------------------------------------------------------------


def _dilate_once(mask: np.ndarray) -> np.ndarray:
    """One-step 4-connectivity dilation; pads with False at the border."""
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def _erode_once(mask: np.ndarray) -> np.ndarray:
    """One-step 4-connectivity erosion; pads with False at the border so
    edges of the canvas erode away just like the mask interior."""
    out = mask.copy()
    out[1:, :] &= mask[:-1, :]
    out[:-1, :] &= mask[1:, :]
    out[:, 1:] &= mask[:, :-1]
    out[:, :-1] &= mask[:, 1:]
    # Border rows/cols can't be eroded against off-canvas neighbours;
    # treat the off-canvas world as False.
    out[0, :] = False
    out[-1, :] = False
    out[:, 0] = False
    out[:, -1] = False
    return out


def _box_blur(arr: np.ndarray, radius: int) -> np.ndarray:
    """Separable square-window box blur via cumsum (pure numpy)."""
    win = 2 * radius + 1
    h, w = arr.shape
    padded = np.pad(arr, radius, mode="edge")

    h_csum = np.empty((padded.shape[0], padded.shape[1] + 1), dtype=np.float32)
    h_csum[:, 0] = 0.0
    h_csum[:, 1:] = np.cumsum(padded, axis=1)
    horiz = (h_csum[:, win:win + w] - h_csum[:, 0:w]) / win

    v_csum = np.empty((horiz.shape[0] + 1, w), dtype=np.float32)
    v_csum[0, :] = 0.0
    v_csum[1:, :] = np.cumsum(horiz, axis=0)
    return (v_csum[win:win + h, :] - v_csum[0:h, :]) / win


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _check_bool_mask(mask: np.ndarray) -> None:
    if mask.ndim != 2:
        raise ValueError(f"selection mask must be 2-D, got shape {mask.shape}")
    if mask.dtype != np.bool_:
        raise ValueError(f"selection mask must be bool, got dtype {mask.dtype}")


def _validate_shape(shape: tuple[int, int]) -> tuple[int, int]:
    if (
        not isinstance(shape, tuple)
        or len(shape) != 2
        or not all(isinstance(s, int) for s in shape)
        or any(s <= 0 for s in shape)
    ):
        raise ValueError(f"shape must be a (h, w) tuple of positive ints, got {shape!r}")
    return shape


def _validate_radius(radius: int) -> int:
    try:
        r = int(radius)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"radius must be an integer, got {radius!r}") from exc
    if r < 0:
        raise ValueError(f"radius must be >= 0, got {r}")
    if r > MAX_RADIUS:
        raise ValueError(f"radius must be <= {MAX_RADIUS}, got {r}")
    return r
