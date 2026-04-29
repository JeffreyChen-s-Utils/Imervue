"""Procedural lens flare overlay.

Composites a synthetic light burst at a configurable image-space
position. The flare is built from three additive layers:

* a **sun disc** — a tight Gaussian highlight at the source point;
* a **glow halo** — a wide soft Gaussian that fades into the surroundings;
* a **streak chain** — three small ghost dots along the line from the
  source through the image centre, mimicking the inter-element
  reflections of a real lens.

All operations work on uint8 RGBA arrays in place of the recipe pipeline.
The position is normalised to ``[0, 1]`` per axis so a flare placed at
``(0.7, 0.3)`` lands at the same relative spot regardless of crop or
export resolution.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.lens_flare")

INTENSITY_MIN = 0.0
INTENSITY_MAX = 1.0
SIZE_MIN = 0.05
SIZE_MAX = 1.0


@dataclass
class LensFlareOptions:
    """Position / intensity / size / colour for the flare."""

    enabled: bool = False
    position: list[float] = None     # [x, y] in 0..1
    intensity: float = 0.6
    size: float = 0.4                # fraction of the long edge for the halo
    colour: list[int] = None         # [r, g, b] tint of the flare; default warm yellow

    def __post_init__(self):
        if self.position is None:
            self.position = [0.7, 0.3]
        if self.colour is None:
            self.colour = [255, 235, 180]

    def to_dict(self) -> dict:
        return {
            "enabled": bool(self.enabled),
            "position": [float(self.position[0]), float(self.position[1])],
            "intensity": float(self.intensity),
            "size": float(self.size),
            "colour": [int(c) for c in self.colour],
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> LensFlareOptions:
        if not isinstance(data, dict):
            return cls()
        try:
            return cls(
                enabled=bool(data.get("enabled", False)),
                position=_clamp_position(data.get("position")),
                intensity=_clamp_float(
                    data.get("intensity", 0.6), INTENSITY_MIN, INTENSITY_MAX,
                ),
                size=_clamp_float(data.get("size", 0.4), SIZE_MIN, SIZE_MAX),
                colour=_clamp_colour(data.get("colour")),
            )
        except (TypeError, ValueError):
            return cls()


def _clamp_position(value) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return [0.7, 0.3]
    try:
        return [max(0.0, min(1.0, float(v))) for v in value]
    except (TypeError, ValueError):
        return [0.7, 0.3]


def _clamp_float(value, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _clamp_colour(value) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return [255, 235, 180]
    try:
        return [max(0, min(255, int(c))) for c in value]
    except (TypeError, ValueError):
        return [255, 235, 180]


def apply_lens_flare(arr: np.ndarray, options: LensFlareOptions) -> np.ndarray:
    """Composite the configured flare onto ``arr``."""
    if not options.enabled or options.intensity <= 0.0:
        return arr
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"apply_lens_flare expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )

    h, w = arr.shape[:2]
    centre_x = options.position[0] * (w - 1)
    centre_y = options.position[1] * (h - 1)
    long_edge = max(h, w)
    halo_radius = max(1.0, options.size * long_edge)
    sun_radius = halo_radius * 0.15
    intensity = max(INTENSITY_MIN, min(INTENSITY_MAX, options.intensity))
    colour = np.array(options.colour, dtype=np.float32)

    weight = _build_flare_weight(
        h, w, centre_x, centre_y, sun_radius, halo_radius,
    )
    weight += _build_ghost_streaks(h, w, centre_x, centre_y, halo_radius)
    weight = np.clip(weight, 0.0, 1.0) * intensity

    rgb = arr[..., :3].astype(np.float32)
    overlay = colour[None, None, :] * weight[..., None]
    blended = rgb + overlay
    out = arr.copy()
    out[..., :3] = np.clip(blended, 0.0, 255.0).astype(np.uint8)
    return out


def _build_flare_weight(
    h: int, w: int,
    cx: float, cy: float,
    sun_radius: float, halo_radius: float,
) -> np.ndarray:
    """Return the sun-disc + halo weight field, in ``[0, 1]``."""
    yy, xx = np.indices((h, w), dtype=np.float32)
    dist_sq = (xx - cx) ** 2 + (yy - cy) ** 2

    sun = np.exp(-dist_sq / (2.0 * (sun_radius ** 2)))
    halo = np.exp(-dist_sq / (2.0 * (halo_radius ** 2))) * 0.55

    return sun + halo


def _build_ghost_streaks(
    h: int, w: int,
    cx: float, cy: float,
    halo_radius: float,
) -> np.ndarray:
    """Three small Gaussian ghosts along the source→centre axis."""
    yy, xx = np.indices((h, w), dtype=np.float32)
    centre_x = (w - 1) * 0.5
    centre_y = (h - 1) * 0.5
    dx = centre_x - cx
    dy = centre_y - cy
    ghosts = np.zeros((h, w), dtype=np.float32)
    ghost_radius = max(2.0, halo_radius * 0.12)
    for offset_factor, weight in ((0.6, 0.30), (1.4, 0.20), (1.9, 0.12)):
        gx = cx + dx * offset_factor
        gy = cy + dy * offset_factor
        dist_sq = (xx - gx) ** 2 + (yy - gy) ** 2
        ghosts += weight * np.exp(-dist_sq / (2.0 * (ghost_radius ** 2)))
    return ghosts
