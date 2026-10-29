"""Colour adjustment kinds and the vectorised HSV / HSL conversions.

Covers ``hsv``, ``color_balance``, ``selective_color``, ``photo_filter``,
``hsl`` and ``channel_mixer``. Dispatched and re-exported by
:mod:`Imervue.paint.adjustments`.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.adjustments_params import (
    DEFAULT_PARAMS,
    SELECTIVE_RANGE_CENTERS,
)


# ---------------------------------------------------------------------------
# HSV
# ---------------------------------------------------------------------------


def _apply_hsv(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["hsv"], **params}
    hue_shift = float(p.get("hue_shift_deg", 0.0))
    saturation = max(0.0, min(8.0, float(p.get("saturation", 1.0))))
    lightness = max(0.0, min(8.0, float(p.get("lightness", 1.0))))
    rgb = image[..., :3].astype(np.float32) / 255.0
    hsv = _rgb_to_hsv(rgb)
    hsv[..., 0] = (hsv[..., 0] + hue_shift) % 360.0
    hsv[..., 1] = np.clip(hsv[..., 1] * saturation, 0.0, 1.0)
    hsv[..., 2] = np.clip(hsv[..., 2] * lightness, 0.0, 1.0)
    rgb_out = _hsv_to_rgb(hsv)
    out = image.copy()
    out[..., :3] = np.clip(rgb_out * 255.0, 0.0, 255.0).astype(np.uint8)
    return out

# ---------------------------------------------------------------------------
# Color Balance
# ---------------------------------------------------------------------------


def _apply_color_balance(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["color_balance"], **params}
    shadows = _coerce_balance_triplet(p.get("shadows"))
    midtones = _coerce_balance_triplet(p.get("midtones"))
    highlights = _coerce_balance_triplet(p.get("highlights"))

    rgb = image[..., :3].astype(np.float32) / 255.0
    luminance = (
        0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    )
    shadows_w = np.clip(1.0 - 2.0 * luminance, 0.0, 1.0)
    midtones_w = 1.0 - 2.0 * np.abs(luminance - 0.5)
    highlights_w = np.clip(2.0 * luminance - 1.0, 0.0, 1.0)

    for channel in range(3):
        delta = (
            shadows[channel] * shadows_w
            + midtones[channel] * midtones_w
            + highlights[channel] * highlights_w
        )
        rgb[..., channel] = rgb[..., channel] + delta
    out = image.copy()
    out[..., :3] = np.clip(rgb * 255.0, 0.0, 255.0).astype(np.uint8)
    return out


def _coerce_balance_triplet(value) -> tuple[float, float, float]:
    """Clamp a color-balance triplet to [-1, 1] per channel."""
    if not isinstance(value, list | tuple) or len(value) != 3:
        return (0.0, 0.0, 0.0)
    out = []
    for c in value:
        try:
            out.append(max(-1.0, min(1.0, float(c))))
        except (TypeError, ValueError):
            out.append(0.0)
    return (out[0], out[1], out[2])


# ---------------------------------------------------------------------------
# Selective Color
# ---------------------------------------------------------------------------


def _apply_selective_color(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["selective_color"], **params}
    range_name = str(p.get("range", "reds"))
    if range_name not in SELECTIVE_RANGE_CENTERS:
        range_name = "reds"
    centre = SELECTIVE_RANGE_CENTERS[range_name]
    width = max(1.0, min(180.0, float(p.get("width_deg", 60.0))))
    hue_shift = float(p.get("hue_shift_deg", 0.0))
    sat_delta = max(-1.0, min(1.0, float(p.get("saturation_delta", 0.0))))
    light_delta = max(-1.0, min(1.0, float(p.get("lightness_delta", 0.0))))

    rgb = image[..., :3].astype(np.float32) / 255.0
    hsv = _rgb_to_hsv(rgb)
    h = hsv[..., 0]
    # Wrap-aware hue distance to the range centre.
    raw = np.abs(h - centre)
    delta_h = np.minimum(raw, 360.0 - raw)
    weight = np.clip(1.0 - delta_h / width, 0.0, 1.0)

    hsv[..., 0] = (hsv[..., 0] + hue_shift * weight) % 360.0
    hsv[..., 1] = np.clip(hsv[..., 1] + sat_delta * weight, 0.0, 1.0)
    hsv[..., 2] = np.clip(hsv[..., 2] + light_delta * weight, 0.0, 1.0)
    rgb_out = _hsv_to_rgb(hsv)
    out = image.copy()
    out[..., :3] = np.clip(rgb_out * 255.0, 0.0, 255.0).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Photo Filter
# ---------------------------------------------------------------------------


def _apply_photo_filter(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["photo_filter"], **params}
    raw_color = p.get("color") or DEFAULT_PARAMS["photo_filter"]["color"]
    if not isinstance(raw_color, list | tuple) or len(raw_color) < 3:
        raw_color = DEFAULT_PARAMS["photo_filter"]["color"]
    color = tuple(max(0, min(255, int(c))) for c in raw_color[:3])
    density = max(0.0, min(1.0, float(p.get("density", 0.25))))
    if density <= 0.0:
        return image.copy()

    rgb = image[..., :3].astype(np.float32) / 255.0
    filter_rgb = np.array(color, dtype=np.float32) / 255.0
    tinted = rgb * filter_rgb[None, None, :]
    blended = rgb * (1.0 - density) + tinted * density
    out = image.copy()
    out[..., :3] = np.clip(blended * 255.0, 0.0, 255.0).astype(np.uint8)
    return out

# ---------------------------------------------------------------------------
# HSL
# ---------------------------------------------------------------------------


def _apply_hsl(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["hsl"], **params}
    hue_shift = float(p.get("hue_shift_deg", 0.0))
    sat = max(0.0, min(8.0, float(p.get("saturation", 1.0))))
    light = max(0.0, min(8.0, float(p.get("lightness", 1.0))))
    rgb = image[..., :3].astype(np.float32) / 255.0
    hsl = _rgb_to_hsl(rgb)
    hsl[..., 0] = (hsl[..., 0] + hue_shift) % 360.0
    hsl[..., 1] = np.clip(hsl[..., 1] * sat, 0.0, 1.0)
    hsl[..., 2] = np.clip(hsl[..., 2] * light, 0.0, 1.0)
    rgb_out = _hsl_to_rgb(hsl)
    out = image.copy()
    out[..., :3] = np.clip(rgb_out * 255.0, 0.0, 255.0).astype(np.uint8)
    return out


def _rgb_to_hsl(rgb: np.ndarray) -> np.ndarray:
    """Vectorised RGB → HSL. Inputs ``[0, 1]`` RGB; outputs H in
    ``[0, 360)`` and S, L in ``[0, 1]``."""
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    cmax = np.max(rgb, axis=-1)
    cmin = np.min(rgb, axis=-1)
    delta = cmax - cmin
    lightness = (cmax + cmin) / 2.0

    safe_delta = np.where(delta == 0, 1.0, delta)
    h = np.zeros_like(cmax)
    mask_r = (cmax == r) & (delta != 0)
    mask_g = (cmax == g) & (delta != 0)
    mask_b = (cmax == b) & (delta != 0)
    h = np.where(mask_r, ((g - b) / safe_delta) % 6.0, h)
    h = np.where(mask_g, ((b - r) / safe_delta) + 2.0, h)
    h = np.where(mask_b, ((r - g) / safe_delta) + 4.0, h)
    h = h * 60.0

    # Saturation differs from HSV — HSL's S is normalised against
    # how close L is to mid-grey: S = delta / (1 - |2L - 1|).
    denom = 1.0 - np.abs(2.0 * lightness - 1.0)
    safe_denom = np.where(denom <= 1e-9, 1.0, denom)
    s = np.where(delta == 0, 0.0, delta / safe_denom)
    return np.stack([h, s, lightness], axis=-1)


def _hsl_to_rgb(hsl: np.ndarray) -> np.ndarray:
    """Inverse of :func:`_rgb_to_hsl`. Returns HxWx3 RGB in ``[0, 1]``."""
    h = hsl[..., 0] % 360.0
    s = hsl[..., 1]
    l_ = hsl[..., 2]
    c = (1.0 - np.abs(2.0 * l_ - 1.0)) * s
    h_prime = h / 60.0
    x = c * (1.0 - np.abs(h_prime % 2.0 - 1.0))
    m = l_ - c / 2.0

    r = np.zeros_like(c)
    g = np.zeros_like(c)
    b = np.zeros_like(c)
    seg0 = (h_prime >= 0) & (h_prime < 1)
    seg1 = (h_prime >= 1) & (h_prime < 2)
    seg2 = (h_prime >= 2) & (h_prime < 3)
    seg3 = (h_prime >= 3) & (h_prime < 4)
    seg4 = (h_prime >= 4) & (h_prime < 5)
    seg5 = (h_prime >= 5) & (h_prime < 6)
    r = np.where(seg0, c, r)
    g = np.where(seg0, x, g)
    r = np.where(seg1, x, r)
    g = np.where(seg1, c, g)
    g = np.where(seg2, c, g)
    b = np.where(seg2, x, b)
    g = np.where(seg3, x, g)
    b = np.where(seg3, c, b)
    r = np.where(seg4, x, r)
    b = np.where(seg4, c, b)
    r = np.where(seg5, c, r)
    b = np.where(seg5, x, b)
    return np.stack([r + m, g + m, b + m], axis=-1)

# ---------------------------------------------------------------------------
# Channel Mixer
# ---------------------------------------------------------------------------


def _apply_channel_mixer(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["channel_mixer"], **params}
    out_r = _coerce_mixer_row(p.get("output_red"), default=(1.0, 0.0, 0.0, 0.0))
    out_g = _coerce_mixer_row(p.get("output_green"), default=(0.0, 1.0, 0.0, 0.0))
    out_b = _coerce_mixer_row(p.get("output_blue"), default=(0.0, 0.0, 1.0, 0.0))
    rgb = image[..., :3].astype(np.float32) / 255.0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    new_r = r * out_r[0] + g * out_r[1] + b * out_r[2] + out_r[3]
    new_g = r * out_g[0] + g * out_g[1] + b * out_g[2] + out_g[3]
    new_b = r * out_b[0] + g * out_b[1] + b * out_b[2] + out_b[3]
    out = image.copy()
    out[..., 0] = np.clip(new_r * 255.0, 0.0, 255.0).astype(np.uint8)
    out[..., 1] = np.clip(new_g * 255.0, 0.0, 255.0).astype(np.uint8)
    out[..., 2] = np.clip(new_b * 255.0, 0.0, 255.0).astype(np.uint8)
    return out


def _coerce_mixer_row(
    value, *, default: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Validate / clamp one (r_factor, g_factor, b_factor, constant)
    row from a channel-mixer parameter dict."""
    if not isinstance(value, list | tuple) or len(value) != 4:
        return default
    out = []
    for c in value:
        try:
            out.append(max(-2.0, min(2.0, float(c))))
        except (TypeError, ValueError):
            out.append(0.0)
    return (out[0], out[1], out[2], out[3])

# ---------------------------------------------------------------------------
# HSV conversions
# ---------------------------------------------------------------------------


def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """Vectorised RGB → HSV. Inputs / outputs are HxWx3 float32 in
    [0, 1] (S, V) and [0, 360) (H)."""
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    cmax = np.max(rgb, axis=-1)
    cmin = np.min(rgb, axis=-1)
    delta = cmax - cmin
    safe_delta = np.where(delta == 0, 1.0, delta)

    h = np.zeros_like(cmax)
    mask_r = (cmax == r) & (delta != 0)
    mask_g = (cmax == g) & (delta != 0)
    mask_b = (cmax == b) & (delta != 0)
    h = np.where(mask_r, ((g - b) / safe_delta) % 6.0, h)
    h = np.where(mask_g, ((b - r) / safe_delta) + 2.0, h)
    h = np.where(mask_b, ((r - g) / safe_delta) + 4.0, h)
    h = h * 60.0

    s = np.where(cmax == 0, 0.0, delta / np.where(cmax == 0, 1.0, cmax))
    v = cmax
    return np.stack([h, s, v], axis=-1)


def _hsv_to_rgb(hsv: np.ndarray) -> np.ndarray:
    """Inverse of :func:`_rgb_to_hsv`. Accepts H in any range; result
    is HxWx3 float32 in [0, 1]."""
    h = hsv[..., 0] % 360.0
    s = hsv[..., 1]
    v = hsv[..., 2]
    c = v * s
    h_prime = h / 60.0
    x = c * (1.0 - np.abs(h_prime % 2.0 - 1.0))
    m = v - c

    r = np.zeros_like(c)
    g = np.zeros_like(c)
    b = np.zeros_like(c)

    seg0 = (h_prime >= 0) & (h_prime < 1)
    seg1 = (h_prime >= 1) & (h_prime < 2)
    seg2 = (h_prime >= 2) & (h_prime < 3)
    seg3 = (h_prime >= 3) & (h_prime < 4)
    seg4 = (h_prime >= 4) & (h_prime < 5)
    seg5 = (h_prime >= 5) & (h_prime < 6)

    r = np.where(seg0, c, r)
    g = np.where(seg0, x, g)
    r = np.where(seg1, x, r)
    g = np.where(seg1, c, g)
    g = np.where(seg2, c, g)
    b = np.where(seg2, x, b)
    g = np.where(seg3, x, g)
    b = np.where(seg3, c, b)
    r = np.where(seg4, x, r)
    b = np.where(seg4, c, b)
    r = np.where(seg5, c, r)
    b = np.where(seg5, x, b)

    return np.stack([r + m, g + m, b + m], axis=-1)
