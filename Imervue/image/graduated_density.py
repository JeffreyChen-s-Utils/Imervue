"""Graduated neutral-density filter — a linear darkening gradient.

The single most-used field filter in landscape work (darktable *graduated
density*, RawTherapee *graduated filter*): darken and optionally tint one side
of the frame along a straight line, so a blown sky or a hot foreground can be
balanced without painting a mask. Imervue's only spatial adjustment was the
radial ``vignette``; this adds the linear case.

The gradient is defined by an *angle*, a transition *hardness*, and a signed
*offset* of the centre line. Every pixel's signed perpendicular distance to that
line is shaped by a smoothstep into a ``[0, 1]`` mask; the masked side is
darkened by ``density_stops`` (an exposure stop multiply ``2**(-stops*mask)``)
and, if a ``tint`` is given, pulled toward that per-channel multiplier.

Pure NumPy on ``HxWx3/4`` uint8 — ships in the main program. Alpha is preserved.
"""
from __future__ import annotations

import math

import numpy as np

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_NEAR_ZERO = 1e-6
_MIN_WIDTH = 1e-3
_DENSITY_LIMIT = 8.0


def apply_graduated_density(
    arr: np.ndarray,
    angle_deg: float = 0.0,
    density_stops: float = 1.0,
    hardness: float = 0.5,
    offset: float = 0.0,
    tint: tuple[float, float, float] | None = None,
) -> np.ndarray:
    """Return *arr* with a linear density gradient applied.

    *angle_deg* rotates the gradient direction (0 darkens the top, 90 the left).
    *density_stops* is how many exposure stops the masked side loses (clamped to
    ``[-8, 8]``; negative brightens). *hardness* in ``[0, 1]`` sets the
    transition sharpness (0 spans the whole frame, 1 is a near-hard edge).
    *offset* in ``[-1, 1]`` shifts the centre line along the gradient direction.
    *tint*, if given, is a per-channel ``(r, g, b)`` multiplier in ``[0, 1]``
    blended in by the mask (e.g. ``(0.8, 0.9, 1.0)`` cools the darkened side).
    """
    _validate(arr)
    density_stops = float(np.clip(density_stops, -_DENSITY_LIMIT, _DENSITY_LIMIT))
    if abs(density_stops) < _NEAR_ZERO and tint is None:
        return arr.copy()
    mask = graduated_mask(arr.shape[0], arr.shape[1], angle_deg, hardness, offset)
    rgb = arr[..., :3].astype(np.float32)
    out = rgb * (2.0 ** (-density_stops * mask))[..., None]
    if tint is not None:
        out = _apply_tint(out, mask, tint)
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    return result


def graduated_mask(
    height: int, width: int, angle_deg: float, hardness: float, offset: float,
) -> np.ndarray:
    """Return an ``HxW`` float mask in ``[0, 1]`` for the linear gradient.

    The mask is 1 on the fully affected side and 0 on the untouched side, with a
    smoothstep transition whose width is set by *hardness*.
    """
    offset = float(np.clip(offset, -1.0, 1.0))
    theta = math.radians(angle_deg)
    ny, nx = np.meshgrid(
        np.linspace(-1.0, 1.0, height, dtype=np.float32),
        np.linspace(-1.0, 1.0, width, dtype=np.float32),
        indexing="ij",
    )
    # Signed distance along the gradient direction; +offset slides the line.
    dist = nx * math.sin(theta) - ny * math.cos(theta) - offset
    half_width = max(_MIN_WIDTH, 1.0 - float(np.clip(hardness, 0.0, 1.0)))
    return _smoothstep(-half_width, half_width, dist)


def _apply_tint(
    rgb: np.ndarray, mask: np.ndarray, tint: tuple[float, float, float],
) -> np.ndarray:
    tint_arr = np.clip(np.asarray(tint, dtype=np.float32), 0.0, 1.0)
    multiplier = 1.0 + mask[..., None] * (tint_arr - 1.0)
    return rgb * multiplier


def _smoothstep(edge0: float, edge1: float, values: np.ndarray) -> np.ndarray:
    span = edge1 - edge0
    t = np.clip((values - edge0) / span, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _validate(arr: np.ndarray) -> None:
    if (
        arr.ndim != _RGB_CHANNELS
        or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS)
        or arr.dtype != np.uint8
    ):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape} {arr.dtype}")
