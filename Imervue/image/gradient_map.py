"""Gradient map — remap luminance to a custom colour gradient.

Each pixel's luminance is treated as an index into a palette of stops,
and the output colour is interpolated between adjacent stops. Stops are
``(position_0_to_1, [r, g, b])`` tuples; positions are normalised so
0.0 maps to absolute black and 1.0 maps to absolute white. A blend
slider mixes the gradient-mapped output with the original RGB so users
can dial in subtle colour grading rather than a full duotone replace.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger("Imervue.gradient_map")

INTENSITY_MIN = 0.0
INTENSITY_MAX = 1.0


@dataclass
class GradientMapOptions:
    """Stops + intensity. Stops must include positions 0.0 and 1.0."""

    enabled: bool = False
    intensity: float = 1.0
    perceptual: bool = False  # interpolate stops in OkLCH instead of sRGB
    stops: list[tuple[float, list[int]]] = field(
        default_factory=lambda: [
            (0.0, [0, 0, 0]),
            (1.0, [255, 255, 255]),
        ],
    )

    def to_dict(self) -> dict:
        return {
            "enabled": bool(self.enabled),
            "intensity": float(self.intensity),
            "perceptual": bool(self.perceptual),
            "stops": [(float(p), [int(c) for c in rgb])
                      for (p, rgb) in self.stops],
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> GradientMapOptions:
        if not isinstance(data, dict):
            return cls()
        try:
            return cls(
                enabled=bool(data.get("enabled", False)),
                intensity=_clamp_float(
                    data.get("intensity", 1.0), INTENSITY_MIN, INTENSITY_MAX,
                ),
                perceptual=bool(data.get("perceptual", False)),
                stops=_normalise_stops(data.get("stops")),
            )
        except (TypeError, ValueError):
            return cls()


def _clamp_float(value, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _normalise_stops(raw) -> list[tuple[float, list[int]]]:
    """Coerce raw input to a sorted list with anchored 0.0 and 1.0 endpoints."""
    if not isinstance(raw, list) or not raw:
        return [(0.0, [0, 0, 0]), (1.0, [255, 255, 255])]
    out: list[tuple[float, list[int]]] = []
    for entry in raw:
        try:
            pos, rgb = entry
            position = max(0.0, min(1.0, float(pos)))
            colour = [max(0, min(255, int(c))) for c in rgb]
            if len(colour) != 3:
                continue
            out.append((position, colour))
        except (TypeError, ValueError):
            continue
    if not out:
        return [(0.0, [0, 0, 0]), (1.0, [255, 255, 255])]
    out.sort(key=lambda x: x[0])
    if out[0][0] > 0.0:
        out.insert(0, (0.0, list(out[0][1])))
    if out[-1][0] < 1.0:
        out.append((1.0, list(out[-1][1])))
    return out


def apply_gradient_map(arr: np.ndarray, options: GradientMapOptions) -> np.ndarray:
    """Map luminance through ``options.stops`` and blend by ``options.intensity``."""
    if not options.enabled or options.intensity <= 0.0:
        return arr
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"apply_gradient_map expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )

    lut = _build_gradient_lut(options.stops, options.perceptual)  # (256, 3) uint8
    luma = (
        0.2126 * arr[..., 0]
        + 0.7152 * arr[..., 1]
        + 0.0722 * arr[..., 2]
    ).astype(np.uint8)
    mapped = lut[luma]   # shape (H, W, 3)

    intensity = max(INTENSITY_MIN, min(INTENSITY_MAX, options.intensity))
    if intensity >= 1.0 - 1e-6:
        out_rgb = mapped
    else:
        rgb = arr[..., :3].astype(np.float32)
        mapped_f = mapped.astype(np.float32)
        blended = rgb * (1.0 - intensity) + mapped_f * intensity
        out_rgb = np.clip(blended, 0, 255).astype(np.uint8)

    out = arr.copy()
    out[..., :3] = out_rgb
    return out


def _build_gradient_lut(
    stops: list[tuple[float, list[int]]], perceptual: bool = False,
) -> np.ndarray:
    """Pre-compute a 256×3 uint8 LUT from the stop list.

    Linear sRGB interpolation by default; ``perceptual`` interpolates each
    segment in OkLCH so saturated gradients keep their colour through the
    midpoint instead of greying.
    """
    if perceptual:
        return _build_perceptual_lut(stops)
    positions = np.array([s[0] for s in stops], dtype=np.float32)
    colours = np.array([s[1] for s in stops], dtype=np.float32)
    indices = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    lut = np.zeros((256, 3), dtype=np.float32)
    for ch in range(3):
        lut[:, ch] = np.interp(indices, positions, colours[:, ch])
    return np.clip(lut + 0.5, 0, 255).astype(np.uint8)


def _segment_index(positions: list[float], p: float) -> int:
    """Index of the stop segment containing position ``p`` (assumes sorted)."""
    last = len(positions) - 2
    k = 0
    while k < last and positions[k + 1] <= p:
        k += 1
    return k


def _build_perceptual_lut(stops: list[tuple[float, list[int]]]) -> np.ndarray:
    """Build the LUT by mixing adjacent stops in OkLCH (perceptual)."""
    from Imervue.image.gradient_perceptual import mix_colors_perceptual
    positions = [float(s[0]) for s in stops]
    colours = [tuple(int(c) for c in s[1]) for s in stops]
    lut = np.zeros((256, 3), dtype=np.uint8)
    for i in range(256):
        p = i / 255.0
        if p <= positions[0]:
            lut[i] = colours[0]
        elif p >= positions[-1]:
            lut[i] = colours[-1]
        else:
            k = _segment_index(positions, p)
            span = positions[k + 1] - positions[k]
            t = (p - positions[k]) / span if span > 0 else 0.0
            lut[i] = mix_colors_perceptual(colours[k], colours[k + 1], t, mode="oklch")
    return lut
