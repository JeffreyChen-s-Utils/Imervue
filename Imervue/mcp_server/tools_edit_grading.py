"""Write-side MCP effect handlers: tone grading, colour grading, curves and lens.

Each handler builds the options of one pure ``Imervue.image`` effect, then saves
``destination`` through :func:`tools_edit_support._apply_effect_and_save`.
Re-exported by ``tools_edit``, which is where tool definitions import them.
"""
from __future__ import annotations

from typing import Any

from Imervue.mcp_server.tools_edit_support import _apply_effect_and_save


# ---------------------------------------------------------------------------
# tone-grading / lens effects
# ---------------------------------------------------------------------------


def posterize_image(
    source: str, destination: str, *, levels: int = 4,
) -> dict[str, Any]:
    """Quantize each channel to ``levels`` discrete steps and save the result."""
    from Imervue.image.posterize import PosterizeOptions, apply_posterize
    options = PosterizeOptions(enabled=True, levels=int(levels))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_posterize(arr, options),
    )


def gradient_map_image(
    source: str, destination: str, *,
    intensity: float = 1.0, perceptual: bool = False,
) -> dict[str, Any]:
    """Map luminance through a black-to-white gradient and save the blended result."""
    from Imervue.image.gradient_map import GradientMapOptions, apply_gradient_map
    options = GradientMapOptions(
        enabled=True, intensity=float(intensity), perceptual=bool(perceptual),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_gradient_map(arr, options),
    )


def film_grain_image(
    source: str, destination: str, *,
    intensity: float = 0.25, size: int = 1,
    monochrome: bool = True, seed: int = 0,
) -> dict[str, Any]:
    """Add tunable Gaussian film grain to the image and save the result."""
    from Imervue.image.film_grain import FilmGrainOptions, apply_film_grain
    options = FilmGrainOptions(
        enabled=True, intensity=float(intensity), size=int(size),
        monochrome=bool(monochrome), seed=int(seed),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_film_grain(arr, options),
    )


def dehaze_image(
    source: str, destination: str, *, strength: float = 0.5,
) -> dict[str, Any]:
    """Remove atmospheric haze (dark-channel prior) by ``strength`` and save."""
    from Imervue.image.dehaze import dehaze
    return _apply_effect_and_save(
        source, destination,
        lambda arr: dehaze(arr, float(strength)),
    )


def distort_image(
    source: str, destination: str, *,
    mode: str = "swirl", strength: float = 0.5,
) -> dict[str, Any]:
    """Warp the image with a swirl, pinch or ripple distortion and save the result."""
    from Imervue.image.distort import distort
    return _apply_effect_and_save(
        source, destination,
        lambda arr: distort(arr, str(mode), float(strength)),
    )


# ---------------------------------------------------------------------------
# colour-grading / curve effects
# ---------------------------------------------------------------------------


def levels_image(
    source: str, destination: str, *,
    black: int = 0, white: int = 255, gamma: float = 1.0,
) -> dict[str, Any]:
    """Remap tones with input black/white points and a gamma, then save."""
    from Imervue.image.levels import LevelsOptions, apply_levels
    options = LevelsOptions(
        enabled=True, black=int(black), white=int(white), gamma=float(gamma),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_levels(arr, options),
    )


def auto_color_balance_image(
    source: str, destination: str, *,
    method: str = "percentile_stretch", intensity: float = 1.0,
    percentile: float = 1.0, retinex_radius: int = 24,
) -> dict[str, Any]:
    """Auto white-balance / colour-cast correction by the chosen method, then save."""
    from Imervue.image.auto_color_balance import AutoBalanceOptions, auto_balance
    options = AutoBalanceOptions(
        method=str(method), intensity=float(intensity),
        percentile=float(percentile), retinex_radius=int(retinex_radius),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: auto_balance(arr, options),
    )


def channel_mixer_image(
    source: str, destination: str, *,
    red: list[float] | None = None, green: list[float] | None = None,
    blue: list[float] | None = None, offsets: list[float] | None = None,
    monochrome: bool = False,
) -> dict[str, Any]:
    """Remix output channels from a 3x3 weight matrix plus offsets, then save."""
    from Imervue.image.channel_mixer import ChannelMixerOptions, apply_channel_mixer
    options = ChannelMixerOptions(
        enabled=True,
        red=[float(v) for v in (red if red is not None else [1.0, 0.0, 0.0])],
        green=[float(v) for v in (green if green is not None else [0.0, 1.0, 0.0])],
        blue=[float(v) for v in (blue if blue is not None else [0.0, 0.0, 1.0])],
        offsets=[float(v) for v in (offsets if offsets is not None else [0.0, 0.0, 0.0])],
        monochrome=bool(monochrome),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_channel_mixer(arr, options),
    )


_CURVE_PRESETS = ("s_curve", "lift_shadows", "compress_highlights")


def _curve_points(preset: str, strength: float):
    """Return the master-curve points for a named preset."""
    from Imervue.image import curves
    builders = {
        "s_curve": curves.s_curve_preset,
        "lift_shadows": curves.lift_shadows_preset,
        "compress_highlights": curves.compress_highlights_preset,
    }
    builder = builders.get(preset)
    if builder is None:
        raise ValueError(
            f"unknown curve preset {preset!r}; expected one of {_CURVE_PRESETS}",
        )
    return builder(strength)


def curve_image(
    source: str, destination: str, *,
    preset: str = "s_curve", strength: float = 0.15,
) -> dict[str, Any]:
    """Apply a tone-curve preset (S-curve, lift shadows, compress highlights), then save."""
    from Imervue.image.curves import CurveOptions, apply_curves
    options = CurveOptions(
        enabled=True, per_channel={"rgb": _curve_points(str(preset), float(strength))},
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_curves(arr, options),
    )


def lens_correction_image(
    source: str, destination: str, *,
    k1: float = 0.0, vignette: float = 0.0,
    ca_red: float = 0.0, ca_blue: float = 0.0,
) -> dict[str, Any]:
    """Correct barrel/pincushion distortion, vignette and chromatic aberration, then save."""
    from Imervue.image.lens_correction import (
        LensCorrectionOptions,
        apply_lens_correction,
    )
    options = LensCorrectionOptions(
        k1=float(k1), vignette=float(vignette),
        ca_red=float(ca_red), ca_blue=float(ca_blue),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_lens_correction(arr, options),
    )
