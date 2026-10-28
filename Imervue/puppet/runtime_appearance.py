"""Evaluate drawable opacity and multiply-color curves."""
from __future__ import annotations

from Imervue.puppet.document import Drawable
from Imervue.puppet.runtime_curves import curve_samples, _sample_color_stops, _sample_opacity_stops


def resolve_drawable_opacity(
    drawable: Drawable, values: dict[str, float],
) -> float:
    """Compute the effective alpha multiplier for ``drawable`` given the
    current parameter ``values``.

    Multiplies the static ``drawable.opacity`` with each
    ``opacity_keys`` curve sampled at its parameter value. Stops are
    interpolated linearly; values outside the stop range clamp to the
    nearest stop. A drawable without ``opacity_keys`` returns
    ``drawable.opacity`` unchanged.

    Used for cross-fading between pose variants (e.g. an arm at neutral
    swing fades out while an arm at full drop fades in)."""
    out = float(drawable.opacity)
    if not drawable.opacity_keys:
        return max(0.0, min(1.0, out))
    for stops, sample in curve_samples(drawable.opacity_keys, values):
        out *= _sample_opacity_stops(stops, sample)
        if out <= 0.0:
            return 0.0
    return max(0.0, min(1.0, out))


def resolve_drawable_color(
    drawable: Drawable, values: dict[str, float],
) -> tuple[float, float, float]:
    """Return the per-frame ``(r, g, b)`` multiply tint for ``drawable``.

    Combines the static :attr:`Drawable.multiply_color` with every
    :attr:`Drawable.multiply_color_keys` curve sampled at its parameter
    value. Multiple curves multiply channel-wise so two curves each
    tinting by ``(1, 0.5, 0.5)`` compose to ``(1, 0.25, 0.25)``.

    Mirrors :func:`resolve_drawable_opacity` so the canvas applies one
    consistent pattern for parameter-driven channel multipliers."""
    r, g, b = drawable.multiply_color
    if not drawable.multiply_color_keys:
        return (r, g, b)
    for stops, sample in curve_samples(drawable.multiply_color_keys, values):
        sr, sg, sb = _sample_color_stops(stops, sample)
        r *= sr
        g *= sg
        b *= sb
    return (max(0.0, r), max(0.0, g), max(0.0, b))
