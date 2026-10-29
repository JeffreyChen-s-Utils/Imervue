"""Write-side MCP effect handlers: tonal, colour, stylize and detail effects.

Each handler loads ``source``, applies one pure ``Imervue.image`` effect and
saves ``destination`` through :func:`tools_edit_support._apply_effect_and_save`.
Re-exported by ``tools_edit``, which is where tool definitions import them.
"""
from __future__ import annotations

from typing import Any

from Imervue.mcp_server.tools_edit_support import _apply_effect_and_save


# ---------------------------------------------------------------------------
# solarize_image
# ---------------------------------------------------------------------------


def solarize_image(
    source: str,
    destination: str,
    *,
    threshold: float = 0.5,
    mix: float = 1.0,
) -> dict[str, Any]:
    """Apply a solarize tone reversal to ``source`` and save it to ``destination``.

    Tones at or above ``threshold`` (0-1) are inverted; ``mix`` (0-1) blends the
    result toward the original.
    """
    from Imervue.image.solarize import apply_solarize
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_solarize(arr, float(threshold), float(mix)),
    )


# ---------------------------------------------------------------------------
# glow_image
# ---------------------------------------------------------------------------


def glow_image(
    source: str,
    destination: str,
    *,
    amount: float = 0.5,
    radius: int = 15,
    threshold: float = 0.0,
) -> dict[str, Any]:
    """Apply a diffuse-glow / Orton bloom to ``source`` and save to ``destination``.

    ``amount`` (0-1) is the glow opacity, ``radius`` the blur radius and
    ``threshold`` (0-1) the brightness above which regions bloom (0 = whole frame).
    """
    from Imervue.image.glow import apply_glow
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_glow(arr, float(amount), int(radius), float(threshold)),
    )


# ---------------------------------------------------------------------------
# tonal / colour effects
# ---------------------------------------------------------------------------


def velvia_image(
    source: str, destination: str, *,
    strength: float = 1.0, luminance_protection: float = 0.5,
) -> dict[str, Any]:
    """Apply a Velvia luminance-weighted saturation boost and save the result."""
    from Imervue.image.velvia import apply_velvia
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_velvia(arr, float(strength), float(luminance_protection)),
    )


def emboss_image(
    source: str, destination: str, *,
    azimuth_deg: float = 135.0, elevation_deg: float = 45.0,
    depth: float = 1.0, grayscale: bool = True,
) -> dict[str, Any]:
    """Apply a directional-light emboss relief and save the result."""
    from Imervue.image.emboss import apply_emboss
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_emboss(
            arr, float(azimuth_deg), float(elevation_deg), float(depth), bool(grayscale),
        ),
    )


def film_negative_image(
    source: str, destination: str, *, gamma: float = 1.0,
) -> dict[str, Any]:
    """Invert a scanned colour negative (auto film base) and save the positive."""
    from Imervue.image.film_negative import apply_film_negative
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_film_negative(arr, None, float(gamma)),
    )


def defringe_image(
    source: str, destination: str, *,
    amount: float = 1.0, edge_threshold: float = 0.1, hue: str = "purple",
) -> dict[str, Any]:
    """Desaturate purple/green chromatic-aberration edge fringes and save the result."""
    from Imervue.image.defringe import apply_defringe
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_defringe(arr, float(amount), float(edge_threshold), str(hue)),
    )


def graduated_density_image(
    source: str, destination: str, *,
    angle_deg: float = 0.0, density_stops: float = 1.0,
    hardness: float = 0.5, offset: float = 0.0,
) -> dict[str, Any]:
    """Apply a linear graduated neutral-density gradient and save the result."""
    from Imervue.image.graduated_density import apply_graduated_density
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_graduated_density(
            arr, float(angle_deg), float(density_stops), float(hardness), float(offset),
        ),
    )


def filmic_tonemap_image(
    source: str, destination: str, *,
    exposure: float = 0.0, white_point: float = 4.0,
    contrast: float = 1.0, saturation: float = 1.0, mode: str = "reinhard",
) -> dict[str, Any]:
    """Apply a filmic (Reinhard/Hable) tone-map highlight rolloff and save the result."""
    from Imervue.image.filmic_tonemap import apply_filmic_tonemap
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_filmic_tonemap(
            arr, float(exposure), float(white_point),
            float(contrast), float(saturation), str(mode),
        ),
    )


_TONE_EQ_DEFAULT = (0.0, 0.0, 0.0, 0.0, 0.0)
_DETAIL_EQ_DEFAULT = (1.0, 1.0, 1.0, 1.0)


def tone_equalizer_image(
    source: str, destination: str, *,
    zone_gains: list[float] | None = None, smoothing: int = 12,
) -> dict[str, Any]:
    """Apply per-luminance-zone exposure (shadows to highlights) and save the result."""
    from Imervue.image.tone_equalizer import apply_tone_equalizer
    gains = tuple(float(g) for g in (zone_gains if zone_gains is not None else _TONE_EQ_DEFAULT))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_tone_equalizer(arr, gains, int(smoothing)),
    )


def detail_equalizer_image(
    source: str, destination: str, *, band_gains: list[float] | None = None,
) -> dict[str, Any]:
    """Re-weight contrast per detail band (finest to coarsest, 1.0 neutral) and save."""
    from Imervue.image.detail_equalizer import apply_detail_equalizer
    gains = tuple(float(g) for g in (band_gains if band_gains is not None else _DETAIL_EQ_DEFAULT))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_detail_equalizer(arr, gains),
    )


# ---------------------------------------------------------------------------
# stylize / artistic effects
# ---------------------------------------------------------------------------


def colormap_image(
    source: str, destination: str, *, name: str = "viridis",
) -> dict[str, Any]:
    """Re-colour ``source`` luminance through a named colour map and save the result."""
    from Imervue.image.colormap import apply_colormap
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_colormap(arr, str(name)),
    )


def false_color_image(source: str, destination: str) -> dict[str, Any]:
    """Map ``source`` luminance to a false-colour exposure scale and save the result."""
    from Imervue.image.false_color import false_color
    return _apply_effect_and_save(source, destination, false_color)


def dither_image(
    source: str, destination: str, *, levels: int = 2,
) -> dict[str, Any]:
    """Ordered-dither ``source`` to ``levels`` tones per channel and save the result."""
    from Imervue.image.dither import ordered_dither
    return _apply_effect_and_save(
        source, destination,
        lambda arr: ordered_dither(arr, int(levels)),
    )


def split_toning_image(
    source: str, destination: str, *,
    shadow_hue: float = 210.0, shadow_saturation: float = 0.0,
    highlight_hue: float = 45.0, highlight_saturation: float = 0.0,
    balance: float = 0.0,
) -> dict[str, Any]:
    """Tint shadows and highlights with separate hues weighted by luminance, then save."""
    from Imervue.image.split_toning import apply_split_toning
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_split_toning(
            arr, float(shadow_hue), float(shadow_saturation),
            float(highlight_hue), float(highlight_saturation), float(balance),
        ),
    )


def pixel_sort_image(
    source: str, destination: str, *,
    lower: int = 60, upper: int = 200, vertical: bool = False,
) -> dict[str, Any]:
    """Sort pixels within brightness bands (``lower``-``upper``) and save the result."""
    from Imervue.image.pixel_sort import pixel_sort
    return _apply_effect_and_save(
        source, destination,
        lambda arr: pixel_sort(arr, int(lower), int(upper), vertical=bool(vertical)),
    )


# ---------------------------------------------------------------------------
# geometric / detail effects
# ---------------------------------------------------------------------------


def polar_image(
    source: str, destination: str, *,
    to_polar: bool = True, invert: bool = False,
) -> dict[str, Any]:
    """Warp ``source`` between rectangular and polar coordinates and save the result."""
    from Imervue.image.polar import polar_distort
    return _apply_effect_and_save(
        source, destination,
        lambda arr: polar_distort(arr, bool(to_polar), bool(invert)),
    )


def kaleidoscope_image(
    source: str, destination: str, *,
    segments: int = 6, angle_deg: float = 0.0,
) -> dict[str, Any]:
    """Mirror ``source`` into ``segments`` kaleidoscope wedges and save the result."""
    import math

    from Imervue.image.kaleidoscope import kaleidoscope
    angle_offset = math.radians(float(angle_deg))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: kaleidoscope(arr, int(segments), None, angle_offset),
    )


def frosted_glass_image(
    source: str, destination: str, *, radius: int = 4, seed: int = 0,
) -> dict[str, Any]:
    """Scatter each pixel to a random neighbour within ``radius`` and save the result."""
    from Imervue.image.frosted_glass import frosted_glass
    return _apply_effect_and_save(
        source, destination,
        lambda arr: frosted_glass(arr, int(radius), int(seed)),
    )


def clahe_image(
    source: str, destination: str, *,
    clip_limit: float = 2.0, tiles: int = 8,
) -> dict[str, Any]:
    """Apply contrast-limited adaptive histogram equalization and save the result."""
    from Imervue.image.clahe import apply_clahe
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_clahe(arr, float(clip_limit), int(tiles)),
    )


def local_contrast_image(
    source: str, destination: str, *,
    clarity: float = 0.0, texture: float = 0.0,
) -> dict[str, Any]:
    """Add midtone clarity and fine-detail texture local contrast, then save."""
    from Imervue.image.local_contrast import apply_clarity, apply_texture
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_texture(apply_clarity(arr, float(clarity)), float(texture)),
    )
