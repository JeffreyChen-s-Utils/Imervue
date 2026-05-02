"""Procedural film-grain overlay.

Generates per-image Gaussian noise and adds it to the luminance channel.
The grain is deterministic when ``seed`` is set so subsequent reloads
produce the same texture instead of shimmering — essential when the
graded image gets re-exported across multiple sessions. Size controls
the grain "kernel" radius (a tiny box-blur on the noise field) so
users can sweep from fine 35mm-style grain to coarse Tri-X.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.film_grain")

INTENSITY_MIN = 0.0
INTENSITY_MAX = 1.0
SIZE_MIN = 1
SIZE_MAX = 8


@dataclass
class FilmGrainOptions:
    """Intensity / size / monochrome / seed for the grain overlay."""

    enabled: bool = False
    intensity: float = 0.25  # 0.0 = no grain, 1.0 = ±64 noise on uint8
    size: int = 1            # box-blur radius applied to the noise field
    monochrome: bool = True  # if False, each channel gets independent noise
    seed: int = 0            # 0 means "always derive from luminance hash"

    def to_dict(self) -> dict:
        return {
            "enabled": bool(self.enabled),
            "intensity": float(self.intensity),
            "size": int(self.size),
            "monochrome": bool(self.monochrome),
            "seed": int(self.seed),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> FilmGrainOptions:
        if not isinstance(data, dict):
            return cls()
        try:
            return cls(
                enabled=bool(data.get("enabled", False)),
                intensity=_clamp_float(
                    data.get("intensity", 0.25), INTENSITY_MIN, INTENSITY_MAX,
                ),
                size=_clamp_int(data.get("size", 1), SIZE_MIN, SIZE_MAX),
                monochrome=bool(data.get("monochrome", True)),
                seed=int(data.get("seed", 0)),
            )
        except (TypeError, ValueError):
            return cls()


def _clamp_int(value, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _clamp_float(value, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def apply_film_grain(arr: np.ndarray, options: FilmGrainOptions) -> np.ndarray:
    """Add Gaussian noise tinted by ``options`` to the RGB channels of ``arr``."""
    if not options.enabled or options.intensity <= 0.0:
        return arr
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"apply_film_grain expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )

    rng = _make_rng(arr, options.seed)
    h, w = arr.shape[:2]
    intensity = max(INTENSITY_MIN, min(INTENSITY_MAX, options.intensity))
    # ±64 standard deviation at full intensity is dramatic but not destructive
    # (most pixels still recognisable). Scale linearly with the slider.
    sigma = 64.0 * intensity

    if options.monochrome:
        noise = rng.normal(0.0, sigma, size=(h, w)).astype(np.float32)
        if options.size > 1:
            noise = _box_blur(noise, options.size)
        delta = np.repeat(noise[..., None], 3, axis=2)
    else:
        noise = rng.normal(0.0, sigma, size=(h, w, 3)).astype(np.float32)
        if options.size > 1:
            for c in range(3):
                noise[..., c] = _box_blur(noise[..., c], options.size)
        delta = noise

    rgb = arr[..., :3].astype(np.float32) + delta
    out = arr.copy()
    out[..., :3] = np.clip(rgb, 0.0, 255.0).astype(np.uint8)
    return out


def _make_rng(arr: np.ndarray, seed: int) -> np.random.Generator:
    """Build a deterministic ``np.random.Generator`` for stable grain.

    A non-zero ``seed`` is honoured directly. Otherwise we derive a seed
    from a hash of the image dimensions so different images get different
    grain but the same image always gets the same grain across reloads.
    """
    if seed:
        return np.random.default_rng(int(seed))
    h, w = arr.shape[:2]
    derived = (h * 7919 + w * 31) & 0x7FFFFFFF
    return np.random.default_rng(int(derived))


def _box_blur(field: np.ndarray, radius: int) -> np.ndarray:
    """Cheap box blur via cumulative-sum trick.

    Implementation note: a Gaussian blur would be more accurate but the
    grain is already random — perfect frequency response is not the
    point. The cumulative-sum approach gives O(N) per axis which keeps
    the grain affordable even on 6000×4000 RAW exports.
    """
    radius = max(1, int(radius))
    kernel = 2 * radius + 1
    arr = np.pad(field, radius, mode="edge")
    csum = np.cumsum(arr, axis=0)
    arr = csum[kernel:, :] - csum[:-kernel, :]
    csum = np.cumsum(arr, axis=1)
    arr = csum[:, kernel:] - csum[:, :-kernel]
    return arr.astype(np.float32) / (kernel * kernel)
