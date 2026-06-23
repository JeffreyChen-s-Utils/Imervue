"""WCAG colour-contrast maths for theme authoring and accessibility audits.

``themes.py`` ships hand-tuned stylesheets but has no way to check whether a
theme's text/background pairing is legible or to derive a safe foreground for a
given background. These pure helpers implement the WCAG 2.x relative-luminance
and contrast-ratio formulae, an AA/AAA pass check, a best-foreground picker and
a brightness scaler for deriving hover / pressed shades. Works on ``(r, g, b)``
int tuples (0-255); hex parsing already lives in ``paint.color_math``. Pure
stdlib maths — no Qt, no numpy.
"""
from __future__ import annotations

Rgb = tuple[int, int, int]

# sRGB → linear-light transfer (WCAG 2.x).
_SRGB_KNEE = 0.03928
_LINEAR_DIVISOR = 12.92
_GAMMA_OFFSET = 0.055
_GAMMA_SCALE = 1.055
_GAMMA = 2.4
_LUMA_WEIGHTS = (0.2126, 0.7152, 0.0722)
_CONTRAST_OFFSET = 0.05
_MAX_CHANNEL = 255

# WCAG 2.x minimum contrast ratios.
_THRESHOLDS = {
    ("AA", False): 4.5,
    ("AA", True): 3.0,
    ("AAA", False): 7.0,
    ("AAA", True): 4.5,
}


def _linearize(channel: int) -> float:
    value = channel / _MAX_CHANNEL
    if value <= _SRGB_KNEE:
        return value / _LINEAR_DIVISOR
    return ((value + _GAMMA_OFFSET) / _GAMMA_SCALE) ** _GAMMA


def relative_luminance(rgb: Rgb) -> float:
    """Return the WCAG relative luminance of *rgb* in ``[0, 1]``."""
    r, g, b = rgb
    weights = _LUMA_WEIGHTS
    return (
        weights[0] * _linearize(r)
        + weights[1] * _linearize(g)
        + weights[2] * _linearize(b)
    )


def contrast_ratio(rgb1: Rgb, rgb2: Rgb) -> float:
    """Return the WCAG contrast ratio of two colours in ``[1, 21]``."""
    lum1 = relative_luminance(rgb1)
    lum2 = relative_luminance(rgb2)
    lighter, darker = max(lum1, lum2), min(lum1, lum2)
    return (lighter + _CONTRAST_OFFSET) / (darker + _CONTRAST_OFFSET)


def meets_wcag(
    foreground: Rgb, background: Rgb, *, level: str = "AA", large_text: bool = False,
) -> bool:
    """True if the pairing meets the WCAG *level* (``"AA"`` / ``"AAA"``).

    ``large_text`` relaxes the threshold (>=18pt or >=14pt bold). Raises
    ``ValueError`` for an unknown level.
    """
    try:
        threshold = _THRESHOLDS[(level, bool(large_text))]
    except KeyError:
        raise ValueError(f"level must be 'AA' or 'AAA', got {level!r}") from None
    return contrast_ratio(foreground, background) >= threshold


def best_foreground(
    background: Rgb, *, light: Rgb = (255, 255, 255), dark: Rgb = (0, 0, 0),
) -> Rgb:
    """Return whichever of *light* / *dark* contrasts more with *background*."""
    if contrast_ratio(light, background) >= contrast_ratio(dark, background):
        return light
    return dark


def scale_brightness(rgb: Rgb, factor: float) -> Rgb:
    """Scale each channel by *factor* (clamped to 0-255) for hover/pressed shades.

    ``factor > 1`` lightens, ``factor < 1`` darkens; negative factors clamp to 0.
    """
    return tuple(  # type: ignore[return-value]
        max(0, min(_MAX_CHANNEL, round(channel * factor))) for channel in rgb
    )
