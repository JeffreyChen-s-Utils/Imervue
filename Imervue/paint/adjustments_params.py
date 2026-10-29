"""Registry of paint adjustment kinds and their default parameters.

:mod:`Imervue.paint.adjustments` re-exports every name here; the kind
modules import them from this module so none of them has to import the
dispatch module that imports them.
"""
from __future__ import annotations

ADJUSTMENT_KINDS = (
    "levels",
    "curves",
    "hsv",
    "brightness_contrast",
    "color_balance",
    "selective_color",
    "photo_filter",
    "hsl",
    "gradient_map",
    "channel_mixer",
    "posterize",
    "threshold",
)

# Six named ranges in selective-color, mapped to their HSV hue centres.
SELECTIVE_RANGES = ("reds", "yellows", "greens", "cyans", "blues", "magentas")
SELECTIVE_RANGE_CENTERS = {
    "reds": 0.0,
    "yellows": 60.0,
    "greens": 120.0,
    "cyans": 180.0,
    "blues": 240.0,
    "magentas": 300.0,
}

DEFAULT_PARAMS: dict[str, dict] = {
    "levels": {
        "input_black": 0,
        "input_white": 255,
        "gamma": 1.0,
        "output_black": 0,
        "output_white": 255,
    },
    "curves": {
        "points": [[0, 0], [255, 255]],
    },
    "hsv": {
        "hue_shift_deg": 0.0,
        "saturation": 1.0,
        "lightness": 1.0,
    },
    "brightness_contrast": {
        # Both in [-1, 1]. brightness = 0 / contrast = 0 → identity.
        "brightness": 0.0,
        "contrast": 0.0,
    },
    "color_balance": {
        # Per-luminance-band channel shifts in [-1, 1]. Each band's
        # weight peaks where the pixel's luminance matches the band
        # (shadows = 0.0, midtones = 0.5, highlights = 1.0).
        "shadows": [0.0, 0.0, 0.0],
        "midtones": [0.0, 0.0, 0.0],
        "highlights": [0.0, 0.0, 0.0],
    },
    "selective_color": {
        # Range-targeted HSV shifts. The Gaussian-style weight peaks
        # at the named range's hue centre and falls off across
        # ``width_deg``.
        "range": "reds",
        "width_deg": 60.0,
        "hue_shift_deg": 0.0,
        "saturation_delta": 0.0,
        "lightness_delta": 0.0,
    },
    "photo_filter": {
        # Tint the image by mixing with a flat colour at density.
        # Defaults reproduce Photoshop's "Warming Filter (85)".
        "color": [235, 165, 95],
        "density": 0.25,
    },
    "hsl": {
        # Hue-Saturation-Lightness — proper HSL where pure black has
        # L = 0 and pure white has L = 1, unlike HSV's V which sits at
        # 1 for any fully-saturated colour. Saturation / lightness
        # are multipliers (1.0 = identity).
        "hue_shift_deg": 0.0,
        "saturation": 1.0,
        "lightness": 1.0,
    },
    "gradient_map": {
        # Map per-pixel luminance to a multi-stop gradient. Default
        # is a black → white gradient = grayscale (identity for
        # already-grey images, desaturate-to-grey for colour ones).
        "stops": [
            {"position": 0.0, "color": [0, 0, 0, 255]},
            {"position": 1.0, "color": [255, 255, 255, 255]},
        ],
    },
    "channel_mixer": {
        # Per-output-channel linear combination of input RGB.
        # Default = identity matrix (no change).
        "output_red": [1.0, 0.0, 0.0, 0.0],
        "output_green": [0.0, 1.0, 0.0, 0.0],
        "output_blue": [0.0, 0.0, 1.0, 0.0],
    },
    "posterize": {
        "levels": 4,
    },
    "threshold": {
        "threshold": 128,
    },
}
