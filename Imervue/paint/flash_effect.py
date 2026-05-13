"""Comic action-flash / explosion effect.

The classic "BOOM!" frame: a starburst silhouette filled solid with
a radial-gradient halo around it. raster paint apps / CSP ship this as a
preset; here it's a pure-numpy rasteriser that returns an HxWx4
RGBA layer ready to drop above the lineart.

The shape is parameterised by a number of *spikes* alternating
between an inner and outer radius. Even spike counts give the
familiar 8 / 12 / 16-point starburst; the spike sharpness comes from
the inner / outer radius ratio.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FLASH_SPIKES_MIN = 4
FLASH_SPIKES_MAX = 64
DEFAULT_FLASH_SPIKES = 12

# Outer radius is a fraction of the canvas's longest axis. A small
# value keeps the burst central; a large one clips against the
# corners (the renderer just stops drawing when it leaves the canvas).
DEFAULT_OUTER_RADIUS_RATIO = 0.45
DEFAULT_INNER_RADIUS_RATIO = 0.20

# Halo extends past the outer spike radius with a radial fade so
# the silhouette reads as "lit from within" against the background.
DEFAULT_HALO_RADIUS_RATIO = 0.55
DEFAULT_HALO_OPACITY = 0.6


@dataclass(frozen=True)
class FlashOptions:
    """Frozen recipe for one flash render — JSON-friendly."""

    spikes: int = DEFAULT_FLASH_SPIKES
    outer_radius_ratio: float = DEFAULT_OUTER_RADIUS_RATIO
    inner_radius_ratio: float = DEFAULT_INNER_RADIUS_RATIO
    halo_radius_ratio: float = DEFAULT_HALO_RADIUS_RATIO
    halo_opacity: float = DEFAULT_HALO_OPACITY
    color: tuple[int, int, int] = (255, 230, 80)
    center: tuple[int, int] | None = None
    rotation_deg: float = 0.0

    def __post_init__(self) -> None:
        if not FLASH_SPIKES_MIN <= int(self.spikes) <= FLASH_SPIKES_MAX:
            raise ValueError(
                f"spikes must be in [{FLASH_SPIKES_MIN}, {FLASH_SPIKES_MAX}],"
                f" got {self.spikes}",
            )
        if not 0.05 < float(self.outer_radius_ratio) <= 1.5:
            raise ValueError(
                f"outer_radius_ratio must be in (0.05, 1.5], got "
                f"{self.outer_radius_ratio}",
            )
        if not 0.0 <= float(self.inner_radius_ratio) < float(self.outer_radius_ratio):
            raise ValueError(
                "inner_radius_ratio must be in [0, outer_radius_ratio); "
                f"got inner={self.inner_radius_ratio} "
                f"outer={self.outer_radius_ratio}",
            )
        if not 0.0 <= float(self.halo_radius_ratio) <= 2.0:
            raise ValueError(
                f"halo_radius_ratio must be in [0, 2], got {self.halo_radius_ratio}",
            )
        if not 0.0 <= float(self.halo_opacity) <= 1.0:
            raise ValueError(
                f"halo_opacity must be in [0, 1], got {self.halo_opacity}",
            )
        if len(self.color) != 3 or any(
            not 0 <= int(c) <= 255 for c in self.color
        ):
            raise ValueError(
                f"color must be a 3-tuple of 0..255 ints, got {self.color!r}",
            )


def render_flash(
    canvas_shape: tuple[int, int],
    options: FlashOptions,
) -> np.ndarray:
    """Return a fresh HxWx4 uint8 RGBA buffer with the flash drawn.

    The output combines a radial halo (alpha gradient) below a solid
    starburst silhouette. Pixels outside both shapes stay fully
    transparent.
    """
    h, w = canvas_shape
    if h <= 0 or w <= 0:
        raise ValueError(
            f"canvas_shape must be positive, got {canvas_shape!r}",
        )
    cx, cy = options.center if options.center is not None else (w // 2, h // 2)
    diag = float(max(h, w))
    outer = float(options.outer_radius_ratio) * diag
    inner = float(options.inner_radius_ratio) * diag
    halo_r = float(options.halo_radius_ratio) * diag

    yy, xx = np.indices((h, w), dtype=np.float32)
    rel_x = xx - float(cx)
    rel_y = yy - float(cy)
    dist = np.sqrt(rel_x * rel_x + rel_y * rel_y)
    angle = np.arctan2(rel_y, rel_x) - np.radians(float(options.rotation_deg))

    out = np.zeros((h, w, 4), dtype=np.uint8)

    # ---- halo --------------------------------------------------------
    if halo_r > 0 and options.halo_opacity > 0:
        halo_norm = np.clip(dist / max(halo_r, 1e-6), 0.0, 1.0)
        halo_alpha = (1.0 - halo_norm) * float(options.halo_opacity)
        halo_alpha_8 = (halo_alpha * 255.0).astype(np.uint8)
        out[..., 0] = options.color[0]
        out[..., 1] = options.color[1]
        out[..., 2] = options.color[2]
        out[..., 3] = halo_alpha_8

    # ---- starburst silhouette ---------------------------------------
    spikes = int(options.spikes)
    spike_phase = (angle * spikes / 2.0) % np.pi
    # Triangle wave in [0, 1] peaking at the spike tips.
    triangle = 1.0 - np.abs((spike_phase / (np.pi / 2.0)) - 1.0)
    radius_mask = inner + (outer - inner) * triangle
    inside_burst = dist <= radius_mask
    out[inside_burst, 0] = options.color[0]
    out[inside_burst, 1] = options.color[1]
    out[inside_burst, 2] = options.color[2]
    out[inside_burst, 3] = 255

    return out
