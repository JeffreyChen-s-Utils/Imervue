"""Film negative — invert a scanned colour negative to a positive.

darktable's *negadoctor* in its essential form: a scanned colour negative is
inverted by dividing the film-base colour (the orange mask) out of the scan, so
the cast is removed at the same time as the tones are flipped. The brightest
recovered value is mapped to white and an optional gamma sets the contrast.

The film base can be supplied (sampled from the unexposed rebate) or estimated
from the scan's per-channel bright point. Pure NumPy on ``HxWx3/4`` uint8 —
ships in the main program. Alpha is preserved.
"""
from __future__ import annotations

import numpy as np

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_MAX_8BIT = 255.0
_NEAR_ZERO = 1e-6
_BASE_PERCENTILE = 99.0
_GAMMA_MIN = 0.1
_GAMMA_MAX = 6.0


def estimate_film_base(arr: np.ndarray) -> tuple[float, float, float]:
    """Estimate the film-base colour as the per-channel bright point of *arr*.

    The unexposed orange mask is the brightest, most saturated region of a
    negative, so a high per-channel percentile approximates it without needing
    the user to sample the rebate by hand.
    """
    rgb = arr[..., :3].astype(np.float32) / _MAX_8BIT
    base = np.percentile(rgb.reshape(-1, _RGB_CHANNELS), _BASE_PERCENTILE, axis=0)
    return tuple(float(max(c, _NEAR_ZERO)) for c in base)


def apply_film_negative(
    arr: np.ndarray,
    film_base: tuple[float, float, float] | None = None,
    gamma: float = 1.0,
) -> np.ndarray:
    """Return the positive image recovered from negative scan *arr*.

    *film_base* is the orange-mask colour as a ``(r, g, b)`` triple in ``[0, 1]``
    (estimated from the scan when omitted). *gamma* (clamped to ``[0.1, 6]``)
    sets the output contrast; ``1.0`` leaves the linear inversion untouched.
    """
    _validate(arr)
    base = np.asarray(film_base if film_base is not None else estimate_film_base(arr),
                      dtype=np.float32)
    gamma = float(np.clip(gamma, _GAMMA_MIN, _GAMMA_MAX))
    scan = arr[..., :3].astype(np.float32) / _MAX_8BIT
    inverted = base / np.maximum(scan, _NEAR_ZERO)
    inverted /= max(float(inverted.max()), _NEAR_ZERO)   # white-balance to brightest
    positive = np.clip(inverted, 0.0, 1.0) ** (1.0 / gamma)
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(positive * _MAX_8BIT), 0, 255).astype(np.uint8)
    return result


def _validate(arr: np.ndarray) -> None:
    if (
        arr.ndim != _RGB_CHANNELS
        or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS)
        or arr.dtype != np.uint8
    ):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape} {arr.dtype}")
