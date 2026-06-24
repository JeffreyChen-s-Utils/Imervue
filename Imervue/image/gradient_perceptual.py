"""Perceptual colour mixing in OkLab / OkLCH.

``gradient.py`` and ``color_math.py`` interpolate in sRGB, which dulls and
greys the midpoint of saturated gradients (blue→yellow runs through grey). OkLab
is a perceptual colour space where a straight line is a perceptually even ramp,
and OkLCH is its polar form (lightness / chroma / hue) so hue can be
interpolated along the shorter arc. These pure functions convert ``(r, g, b)``
int tuples (0-255, matching ``color_math``) to/from OkLab/OkLCH and mix two
colours in the chosen space. Pure stdlib maths — no Qt, no numpy.

Transform constants are Björn Ottosson's: https://bottosson.github.io/posts/oklab/
"""
from __future__ import annotations

import math

Rgb = tuple[int, int, int]
Triple = tuple[float, float, float]

_MAX_CHANNEL = 255
_SRGB_KNEE = 0.04045
_LINEAR_DIVISOR = 12.92
_GAMMA_OFFSET = 0.055
_GAMMA_SCALE = 1.055
_GAMMA = 2.4
_DELINEAR_KNEE = 0.0031308
_DEGREES = 360.0
_HALF_TURN = 180.0

_LINEAR_TO_LMS = (
    (0.4122214708, 0.5363325363, 0.0514459929),
    (0.2119034982, 0.6806995451, 0.1073969566),
    (0.0883024619, 0.2817188376, 0.6299787005),
)
_LMS_TO_LAB = (
    (0.2104542553, 0.7936177850, -0.0040720468),
    (1.9779984951, -2.4285922050, 0.4505937099),
    (0.0259040371, 0.7827717662, -0.8086757660),
)
_LAB_TO_LMS = (
    (1.0, 0.3963377774, 0.2158037573),
    (1.0, -0.1055613458, -0.0638541728),
    (1.0, -0.0894841775, -1.2914855480),
)
_LMS_TO_LINEAR = (
    (4.0767416621, -3.3077115913, 0.2309699292),
    (-1.2684380046, 2.6097574011, -0.3413193965),
    (-0.0041960863, -0.7034186147, 1.7076147010),
)


def _mat_apply(matrix: tuple[Triple, ...], vec: Triple) -> Triple:
    return tuple(  # type: ignore[return-value]
        row[0] * vec[0] + row[1] * vec[1] + row[2] * vec[2] for row in matrix
    )


def _linearize(value: float) -> float:
    if value <= _SRGB_KNEE:
        return value / _LINEAR_DIVISOR
    return ((value + _GAMMA_OFFSET) / _GAMMA_SCALE) ** _GAMMA


def _delinearize(value: float) -> float:
    if value <= _DELINEAR_KNEE:
        return value * _LINEAR_DIVISOR
    return _GAMMA_SCALE * value ** (1.0 / _GAMMA) - _GAMMA_OFFSET


def _cbrt(value: float) -> float:
    return math.copysign(abs(value) ** (1.0 / 3.0), value)


def rgb_to_oklab(rgb: Rgb) -> Triple:
    """Convert an ``(r, g, b)`` int tuple (0-255) to OkLab ``(L, a, b)``."""
    linear = tuple(_linearize(channel / _MAX_CHANNEL) for channel in rgb)
    lms = _mat_apply(_LINEAR_TO_LMS, linear)  # type: ignore[arg-type]
    lms_root = tuple(_cbrt(component) for component in lms)
    return _mat_apply(_LMS_TO_LAB, lms_root)  # type: ignore[arg-type]


def oklab_to_rgb(lab: Triple) -> Rgb:
    """Convert OkLab ``(L, a, b)`` back to a clamped ``(r, g, b)`` int tuple."""
    lms_root = _mat_apply(_LAB_TO_LMS, lab)
    lms = tuple(component ** 3 for component in lms_root)
    linear = _mat_apply(_LMS_TO_LINEAR, lms)  # type: ignore[arg-type]
    return tuple(  # type: ignore[return-value]
        max(0, min(_MAX_CHANNEL, round(_delinearize(channel) * _MAX_CHANNEL)))
        for channel in linear
    )


def oklab_to_oklch(lab: Triple) -> Triple:
    """Convert OkLab to OkLCH ``(L, C, H)`` with hue in degrees ``[0, 360)``."""
    lightness, a, b = lab
    chroma = math.hypot(a, b)
    hue = math.degrees(math.atan2(b, a)) % _DEGREES
    return (lightness, chroma, hue)


def oklch_to_oklab(lch: Triple) -> Triple:
    """Convert OkLCH ``(L, C, H)`` (hue in degrees) back to OkLab."""
    lightness, chroma, hue = lch
    radians = math.radians(hue)
    return (lightness, chroma * math.cos(radians), chroma * math.sin(radians))


def _lerp(start: float, end: float, t: float) -> float:
    return start + (end - start) * t


def _lerp_hue(start: float, end: float, t: float) -> float:
    delta = ((end - start + _HALF_TURN) % _DEGREES) - _HALF_TURN
    return (start + delta * t) % _DEGREES


def mix_colors_perceptual(c0: Rgb, c1: Rgb, t: float, *, mode: str = "oklch") -> Rgb:
    """Blend two colours at fraction *t* in the given colour space.

    ``mode`` is ``"oklch"`` (lightness/chroma linear, hue along the shorter arc),
    ``"oklab"`` (linear in OkLab) or ``"rgb"`` (plain sRGB lerp). *t* is clamped
    to ``[0, 1]``. Raises ``ValueError`` for an unknown mode.
    """
    t = min(1.0, max(0.0, t))
    if mode == "rgb":
        return tuple(  # type: ignore[return-value]
            max(0, min(_MAX_CHANNEL, round(_lerp(a, b, t))))
            for a, b in zip(c0, c1, strict=True)
        )
    if mode == "oklab":
        lab0, lab1 = rgb_to_oklab(c0), rgb_to_oklab(c1)
        return oklab_to_rgb(
            tuple(_lerp(a, b, t) for a, b in zip(lab0, lab1, strict=True)),
        )
    if mode == "oklch":
        lch0 = oklab_to_oklch(rgb_to_oklab(c0))
        lch1 = oklab_to_oklch(rgb_to_oklab(c1))
        mixed = (
            _lerp(lch0[0], lch1[0], t),
            _lerp(lch0[1], lch1[1], t),
            _lerp_hue(lch0[2], lch1[2], t),
        )
        return oklab_to_rgb(oklch_to_oklab(mixed))
    raise ValueError(f"mode must be 'oklch', 'oklab' or 'rgb', got {mode!r}")
