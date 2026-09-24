"""Name, description, input schema and handler of each write-side MCP tool.

Listed after the read-side tools in ``tools/list``; output schemas live in ``tool_schemas``.
"""
from __future__ import annotations

from typing import Any

from Imervue.mcp_server.tools_edit import (
    apply_frame,
    apply_watermark,
    auto_color_balance_image,
    build_collage,
    channel_mixer_image,
    clahe_image,
    colormap_image,
    crop_image,
    curve_image,
    defringe_image,
    dehaze_image,
    detail_equalizer_image,
    distort_image,
    dither_image,
    emboss_image,
    false_color_image,
    film_grain_image,
    film_negative_image,
    filmic_tonemap_image,
    frosted_glass_image,
    glow_image,
    gradient_map_image,
    graduated_density_image,
    kaleidoscope_image,
    lens_correction_image,
    levels_image,
    local_contrast_image,
    pixel_sort_image,
    polar_image,
    posterize_image,
    resize_image,
    rotate_image,
    solarize_image,
    split_toning_image,
    tone_equalizer_image,
    velvia_image,
)

EDIT_TOOL_DEFINITIONS: list[dict[str, Any]] = [    {
        "name": "apply_watermark",
        "description": (
            "Render a text watermark onto an image and save it to a destination "
            "path. corner is one of top-left / top-right / bottom-left / "
            "bottom-right / center; opacity and font_fraction are 0..1 fractions; "
            "color is an [r, g, b] triplet. The destination format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "text": {"type": "string", "description": "Watermark text (non-empty)."},
                "corner": {
                    "type": "string",
                    "enum": ["top-left", "top-right", "bottom-left",
                             "bottom-right", "center"],
                    "default": "bottom-right",
                },
                "opacity": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.6},
                "font_fraction": {
                    "type": "number", "minimum": 0.005, "maximum": 0.2, "default": 0.035,
                },
                "color": {
                    "type": "array", "items": {"type": "integer"},
                    "minItems": 3, "maxItems": 3, "default": [255, 255, 255],
                },
                "shadow": {"type": "boolean", "default": True},
            },
            "required": ["source", "destination", "text"],
        },
        "handler": apply_watermark,
    },
    {
        "name": "apply_frame",
        "description": (
            "Wrap an image in a coloured matte border and save it to a "
            "destination path. border is the matte width in pixels; bottom_extra "
            "adds a thicker Polaroid-style bottom band; caption is burned into "
            "that band. color and text_color are [r, g, b] triplets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "border": {"type": "integer", "minimum": 0, "default": 40},
                "color": {
                    "type": "array", "items": {"type": "integer"},
                    "minItems": 3, "maxItems": 3, "default": [255, 255, 255],
                },
                "bottom_extra": {"type": "integer", "minimum": 0, "default": 0},
                "caption": {"type": "string", "default": ""},
                "text_color": {
                    "type": "array", "items": {"type": "integer"},
                    "minItems": 3, "maxItems": 3, "default": [40, 40, 40],
                },
            },
            "required": ["source", "destination"],
        },
        "handler": apply_frame,
    },
    {
        "name": "build_collage",
        "description": (
            "Composite several images into a grid montage and save it. Each "
            "source is letterboxed into an equal cell_width x cell_height cell; "
            "columns sets the grid width, gap separates cells and margin frames "
            "the grid. background is an [r, g, b] triplet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array", "items": {"type": "string"}, "minItems": 1,
                },
                "destination": {"type": "string"},
                "columns": {"type": "integer", "minimum": 1, "default": 3},
                "cell_width": {"type": "integer", "minimum": 1, "default": 400},
                "cell_height": {"type": "integer", "minimum": 1, "default": 400},
                "gap": {"type": "integer", "minimum": 0, "default": 12},
                "margin": {"type": "integer", "minimum": 0, "default": 20},
                "background": {
                    "type": "array", "items": {"type": "integer"},
                    "minItems": 3, "maxItems": 3, "default": [255, 255, 255],
                },
            },
            "required": ["sources", "destination"],
        },
        "handler": build_collage,
    },
    {
        "name": "crop_image",
        "description": (
            "Crop a rectangular region out of an image and save it. x / y are "
            "the top-left corner and width / height the box size, all in source "
            "pixels; the box must lie fully inside the image. The destination "
            "format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "x": {"type": "integer", "minimum": 0},
                "y": {"type": "integer", "minimum": 0},
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
            },
            "required": ["source", "destination", "x", "y", "width", "height"],
        },
        "handler": crop_image,
    },
    {
        "name": "resize_image",
        "description": (
            "Resize an image and save it. Pass both width and height for an "
            "exact resize, or just one to scale the other proportionally. The "
            "destination format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
            },
            "required": ["source", "destination"],
        },
        "handler": resize_image,
    },
    {
        "name": "rotate_image",
        "description": (
            "Rotate (clockwise) or flip an image by a fixed, lossless operation "
            "and save it. operation is one of rotate_90 / rotate_180 / "
            "rotate_270 / flip_horizontal / flip_vertical. The destination "
            "format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "operation": {
                    "type": "string",
                    "enum": ["rotate_90", "rotate_180", "rotate_270",
                             "flip_horizontal", "flip_vertical"],
                },
            },
            "required": ["source", "destination", "operation"],
        },
        "handler": rotate_image,
    },
    {
        "name": "solarize_image",
        "description": (
            "Apply a solarize tone reversal and save the result. Tones at or "
            "above threshold (0-1) are inverted; mix (0-1) blends back toward "
            "the original. The destination format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "threshold": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
                },
                "mix": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 1.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": solarize_image,
    },
    {
        "name": "glow_image",
        "description": (
            "Apply a diffuse-glow / Orton soft-focus bloom and save the result. "
            "amount (0-1) is the glow opacity, radius the blur size, threshold "
            "(0-1) the brightness above which regions bloom (0 = whole frame). "
            "The destination format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "amount": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
                },
                "radius": {
                    "type": "integer", "minimum": 1, "maximum": 200, "default": 15,
                },
                "threshold": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": glow_image,
    },
    {
        "name": "velvia_image",
        "description": (
            "Apply a Velvia luminance-weighted saturation boost: intensifies "
            "muted colours while sparing already-saturated ones and the shadows."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "strength": {
                    "type": "number", "minimum": -1, "maximum": 4, "default": 1.0,
                },
                "luminance_protection": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": velvia_image,
    },
    {
        "name": "emboss_image",
        "description": (
            "Apply a directional-light emboss relief, shading the luminance as a "
            "height field lit from a chosen azimuth and elevation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "azimuth_deg": {
                    "type": "number", "minimum": 0, "maximum": 360, "default": 135.0,
                },
                "elevation_deg": {
                    "type": "number", "minimum": 0, "maximum": 90, "default": 45.0,
                },
                "depth": {
                    "type": "number", "minimum": 0, "maximum": 10, "default": 1.0,
                },
                "grayscale": {"type": "boolean", "default": True},
            },
            "required": ["source", "destination"],
        },
        "handler": emboss_image,
    },
    {
        "name": "film_negative_image",
        "description": (
            "Invert a scanned colour negative to a positive, dividing out the "
            "auto-estimated orange film base, with an optional output gamma."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "gamma": {
                    "type": "number", "minimum": 0.1, "maximum": 6, "default": 1.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": film_negative_image,
    },
    {
        "name": "defringe_image",
        "description": (
            "Desaturate purple/green chromatic-aberration fringes on high-contrast "
            "edges, leaving flat colour untouched."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "amount": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 1.0,
                },
                "edge_threshold": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.1,
                },
                "hue": {
                    "type": "string", "enum": ["purple", "green", "all"],
                    "default": "purple",
                },
            },
            "required": ["source", "destination"],
        },
        "handler": defringe_image,
    },
    {
        "name": "graduated_density_image",
        "description": (
            "Apply a linear graduated neutral-density gradient: darken one side of "
            "the frame along an angled line, by a number of exposure stops."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "angle_deg": {
                    "type": "number", "minimum": 0, "maximum": 360, "default": 0.0,
                },
                "density_stops": {
                    "type": "number", "minimum": -8, "maximum": 8, "default": 1.0,
                },
                "hardness": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
                },
                "offset": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": graduated_density_image,
    },
    {
        "name": "filmic_tonemap_image",
        "description": (
            "Apply a filmic Reinhard or Hable tone-map: compress highlights into a "
            "soft rolloff with pivoted contrast and a saturation restore."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "exposure": {
                    "type": "number", "minimum": -6, "maximum": 6, "default": 0.0,
                },
                "white_point": {
                    "type": "number", "minimum": 0.1, "maximum": 64, "default": 4.0,
                },
                "contrast": {
                    "type": "number", "minimum": 0.1, "maximum": 4, "default": 1.0,
                },
                "saturation": {
                    "type": "number", "minimum": 0, "maximum": 4, "default": 1.0,
                },
                "mode": {
                    "type": "string", "enum": ["reinhard", "hable"],
                    "default": "reinhard",
                },
            },
            "required": ["source", "destination"],
        },
        "handler": filmic_tonemap_image,
    },
    {
        "name": "tone_equalizer_image",
        "description": (
            "Apply a tone equalizer: independent exposure per luminance zone "
            "(shadows to highlights, in stops) over a smoothed mask."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "zone_gains": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -4, "maximum": 4},
                    "minItems": 2,
                    "description": "Stop adjustments, shadows to highlights.",
                },
                "smoothing": {
                    "type": "integer", "minimum": 0, "maximum": 50, "default": 12,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": tone_equalizer_image,
    },
    {
        "name": "detail_equalizer_image",
        "description": (
            "Apply a detail equalizer: re-weight contrast per frequency band "
            "(finest to coarsest); a gain of 1.0 is neutral."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "band_gains": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -8, "maximum": 8},
                    "minItems": 1,
                    "description": "Per-band gain, finest to coarsest (1.0 neutral).",
                },
            },
            "required": ["source", "destination"],
        },
        "handler": detail_equalizer_image,
    },
    {
        "name": "colormap_image",
        "description": (
            "Re-colour the image by mapping its luminance through a perceptual "
            "colour map (viridis, magma or jet)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "name": {
                    "type": "string",
                    "enum": ["viridis", "magma", "jet"],
                    "default": "viridis",
                },
            },
            "required": ["source", "destination"],
        },
        "handler": colormap_image,
    },
    {
        "name": "false_color_image",
        "description": (
            "Map luminance to a false-colour exposure scale (blacks through "
            "whites), the way a video monitor flags clipping."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
            },
            "required": ["source", "destination"],
        },
        "handler": false_color_image,
    },
    {
        "name": "dither_image",
        "description": (
            "Ordered (Bayer) dither the image to a small number of tones per "
            "channel, trading colour depth for a retro halftone look."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "levels": {
                    "type": "integer", "minimum": 2, "maximum": 8, "default": 2,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": dither_image,
    },
    {
        "name": "split_toning_image",
        "description": (
            "Tint shadows and highlights with separate hues, weighted by "
            "luminance, with a balance control for the split point."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "shadow_hue": {
                    "type": "number", "minimum": 0, "maximum": 360, "default": 210.0,
                },
                "shadow_saturation": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.0,
                },
                "highlight_hue": {
                    "type": "number", "minimum": 0, "maximum": 360, "default": 45.0,
                },
                "highlight_saturation": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.0,
                },
                "balance": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": split_toning_image,
    },
    {
        "name": "pixel_sort_image",
        "description": (
            "Pixel-sort the image: reorder pixels by brightness within contiguous "
            "bands bounded by lower/upper thresholds, for a glitch-art smear."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "lower": {
                    "type": "integer", "minimum": 0, "maximum": 255, "default": 60,
                },
                "upper": {
                    "type": "integer", "minimum": 0, "maximum": 255, "default": 200,
                },
                "vertical": {"type": "boolean", "default": False},
            },
            "required": ["source", "destination"],
        },
        "handler": pixel_sort_image,
    },
    {
        "name": "polar_image",
        "description": (
            "Warp the image between rectangular and polar coordinates: wrap it "
            "into a disc (tiny-planet) or unroll a disc back into a strip."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "to_polar": {"type": "boolean", "default": True},
                "invert": {"type": "boolean", "default": False},
            },
            "required": ["source", "destination"],
        },
        "handler": polar_image,
    },
    {
        "name": "kaleidoscope_image",
        "description": (
            "Mirror the image into a number of kaleidoscope wedges around the "
            "centre, with an optional rotation of the wedge."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "segments": {
                    "type": "integer", "minimum": 2, "maximum": 64, "default": 6,
                },
                "angle_deg": {
                    "type": "number", "minimum": 0, "maximum": 360, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": kaleidoscope_image,
    },
    {
        "name": "frosted_glass_image",
        "description": (
            "Frosted-glass scatter: replace each pixel with a random neighbour "
            "within a radius, for a textured diffusion. The seed is reproducible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "radius": {
                    "type": "integer", "minimum": 0, "maximum": 64, "default": 4,
                },
                "seed": {"type": "integer", "minimum": 0, "default": 0},
            },
            "required": ["source", "destination"],
        },
        "handler": frosted_glass_image,
    },
    {
        "name": "clahe_image",
        "description": (
            "Contrast-limited adaptive histogram equalization: boost local "
            "contrast per tile on the luminance, with a clip limit to cap noise."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "clip_limit": {
                    "type": "number", "minimum": 1, "maximum": 8, "default": 2.0,
                },
                "tiles": {
                    "type": "integer", "minimum": 1, "maximum": 16, "default": 8,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": clahe_image,
    },
    {
        "name": "local_contrast_image",
        "description": (
            "Local contrast: midtone-weighted clarity at a large radius plus "
            "fine-detail texture at a small radius (each -1 to 1, 0 neutral)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "clarity": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.0,
                },
                "texture": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": local_contrast_image,
    },
    {
        "name": "posterize_image",
        "description": (
            "Posterize: quantize each channel to a small number of discrete "
            "levels for a flat, banded poster look."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "levels": {
                    "type": "integer", "minimum": 2, "maximum": 64, "default": 4,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": posterize_image,
    },
    {
        "name": "gradient_map_image",
        "description": (
            "Gradient map: remap luminance through a black-to-white gradient "
            "and blend it over the original by an intensity factor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "intensity": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 1.0,
                },
                "perceptual": {"type": "boolean", "default": False},
            },
            "required": ["source", "destination"],
        },
        "handler": gradient_map_image,
    },
    {
        "name": "film_grain_image",
        "description": (
            "Add Gaussian film grain: tunable intensity and clump size, "
            "monochrome or per-channel, with a reproducible seed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "intensity": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.25,
                },
                "size": {
                    "type": "integer", "minimum": 1, "maximum": 8, "default": 1,
                },
                "monochrome": {"type": "boolean", "default": True},
                "seed": {"type": "integer", "minimum": 0, "default": 0},
            },
            "required": ["source", "destination"],
        },
        "handler": film_grain_image,
    },
    {
        "name": "dehaze_image",
        "description": (
            "Dehaze: estimate atmospheric light with a dark-channel prior and "
            "recover contrast and colour through the haze, by a strength factor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "strength": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": dehaze_image,
    },
    {
        "name": "distort_image",
        "description": (
            "Geometric distortion: swirl around the centre, pinch/bulge, or a "
            "sinusoidal ripple. Strength runs -1 to 1 (sign flips the direction)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["swirl", "pinch", "ripple"],
                    "default": "swirl",
                },
                "strength": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.5,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": distort_image,
    },
    {
        "name": "levels_image",
        "description": (
            "Levels: set input black and white points and a midtone gamma to "
            "remap the tonal range. gamma 1.0 is neutral."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "black": {
                    "type": "integer", "minimum": 0, "maximum": 254, "default": 0,
                },
                "white": {
                    "type": "integer", "minimum": 1, "maximum": 255, "default": 255,
                },
                "gamma": {
                    "type": "number", "minimum": 0.1, "maximum": 9.99, "default": 1.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": levels_image,
    },
    {
        "name": "auto_color_balance_image",
        "description": (
            "Automatic white-balance / colour-cast correction by gray-world, "
            "white-patch, percentile-stretch or simplified-retinex, blended by "
            "intensity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "method": {
                    "type": "string",
                    "enum": [
                        "gray_world", "white_patch",
                        "percentile_stretch", "simplified_retinex",
                    ],
                    "default": "percentile_stretch",
                },
                "intensity": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 1.0,
                },
                "percentile": {
                    "type": "number", "minimum": 0, "maximum": 10, "default": 1.0,
                },
                "retinex_radius": {
                    "type": "integer", "minimum": 4, "maximum": 64, "default": 24,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": auto_color_balance_image,
    },
    {
        "name": "channel_mixer_image",
        "description": (
            "Channel mixer: build each output channel as a weighted sum of the "
            "input R/G/B plus an offset. Set monochrome to fold all rows into a "
            "tunable black-and-white conversion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "red": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -2, "maximum": 2},
                    "minItems": 3, "maxItems": 3,
                    "description": "Output-red weights [from_r, from_g, from_b].",
                },
                "green": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -2, "maximum": 2},
                    "minItems": 3, "maxItems": 3,
                    "description": "Output-green weights [from_r, from_g, from_b].",
                },
                "blue": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -2, "maximum": 2},
                    "minItems": 3, "maxItems": 3,
                    "description": "Output-blue weights [from_r, from_g, from_b].",
                },
                "offsets": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -1, "maximum": 1},
                    "minItems": 3, "maxItems": 3,
                    "description": "Per-channel constant offset [r, g, b].",
                },
                "monochrome": {"type": "boolean", "default": False},
            },
            "required": ["source", "destination"],
        },
        "handler": channel_mixer_image,
    },
    {
        "name": "curve_image",
        "description": (
            "Apply a master tone-curve preset: an S-curve for contrast, lift "
            "shadows for a flat look, or compress highlights to recover detail. "
            "strength scales the preset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "preset": {
                    "type": "string",
                    "enum": ["s_curve", "lift_shadows", "compress_highlights"],
                    "default": "s_curve",
                },
                "strength": {
                    "type": "number", "minimum": 0, "maximum": 0.5, "default": 0.15,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": curve_image,
    },
    {
        "name": "lens_correction_image",
        "description": (
            "Lens correction: remove barrel/pincushion distortion (k1), lift or "
            "deepen corner vignette, and offset the red/blue radial scale to "
            "cancel chromatic aberration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "k1": {
                    "type": "number", "minimum": -0.4, "maximum": 0.4, "default": 0.0,
                },
                "vignette": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.0,
                },
                "ca_red": {
                    "type": "number", "minimum": -0.02, "maximum": 0.02, "default": 0.0,
                },
                "ca_blue": {
                    "type": "number", "minimum": -0.02, "maximum": 0.02, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": lens_correction_image,
    },
]
