"""Named gradient-map presets for the Layer-menu one-click adders.

The gradient_map adjustment kind already lives in
:mod:`Imervue.paint.adjustments`; this module ships the small palette
of presets the Layer menu offers as one-click "Add Gradient Map"
entries — black→white grayscale (identity), warm sunset, cool blue
toner, sepia, and a magma-style heat ramp. Each preset is just a
``stops`` list compatible with
:data:`Imervue.paint.adjustments.DEFAULT_PARAMS["gradient_map"]`.

Pure data — no Qt, no numpy. Tests can assert the dict shape without
a workspace.
"""
from __future__ import annotations

# Each preset is an (id, label_key, fallback, stops) row. The label_key
# routes through the i18n dict; the fallback shows up when the key is
# missing. Stops are raster paint apps-friendly defaults — start dark, end
# light — so a default-grey image converted by the preset reads as
# the named tone.
GRADIENT_MAP_PRESETS: tuple[tuple[str, str, str, list[dict]], ...] = (
    (
        "grayscale",
        "paint_gradient_map_grayscale",
        "Grayscale",
        [
            {"position": 0.0, "color": [0, 0, 0, 255]},
            {"position": 1.0, "color": [255, 255, 255, 255]},
        ],
    ),
    (
        "sunset",
        "paint_gradient_map_sunset",
        "Sunset",
        [
            {"position": 0.0, "color": [40, 0, 60, 255]},
            {"position": 0.5, "color": [220, 70, 50, 255]},
            {"position": 1.0, "color": [255, 220, 130, 255]},
        ],
    ),
    (
        "sepia",
        "paint_gradient_map_sepia",
        "Sepia",
        [
            {"position": 0.0, "color": [40, 25, 10, 255]},
            {"position": 0.5, "color": [150, 100, 60, 255]},
            {"position": 1.0, "color": [240, 220, 180, 255]},
        ],
    ),
    (
        "cyanotype",
        "paint_gradient_map_cyanotype",
        "Cyanotype",
        [
            {"position": 0.0, "color": [10, 25, 60, 255]},
            {"position": 0.5, "color": [50, 110, 170, 255]},
            {"position": 1.0, "color": [220, 240, 255, 255]},
        ],
    ),
    (
        "magma",
        "paint_gradient_map_magma",
        "Magma",
        [
            {"position": 0.0, "color": [10, 0, 30, 255]},
            {"position": 0.4, "color": [180, 30, 80, 255]},
            {"position": 0.7, "color": [240, 130, 60, 255]},
            {"position": 1.0, "color": [255, 250, 190, 255]},
        ],
    ),
)


def preset_stops(preset_id: str) -> list[dict] | None:
    """Return a fresh copy of the stops list for ``preset_id``, or None."""
    for entry in GRADIENT_MAP_PRESETS:
        if entry[0] == preset_id:
            return [
                {"position": stop["position"], "color": list(stop["color"])}
                for stop in entry[3]
            ]
    return None


def preset_ids() -> tuple[str, ...]:
    """Return the canonical id order of the preset palette."""
    return tuple(entry[0] for entry in GRADIENT_MAP_PRESETS)
