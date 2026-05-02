"""Levels adjustment — black point / white point / gamma remap.

The classic Photoshop Levels tool: clip everything below ``black`` to 0,
clip everything above ``white`` to 255, then push the result through a
gamma curve. Operates on uint8 RGBA arrays in place of the recipe
pipeline; identity options short-circuit so unchanged recipes pay nothing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.levels")

LEVELS_MIN = 0
LEVELS_MAX = 255
GAMMA_MIN = 0.1
GAMMA_MAX = 9.99


@dataclass
class LevelsOptions:
    """Black point, white point, and gamma — all per-channel-uniform."""

    enabled: bool = False
    black: int = 0      # 0..254
    white: int = 255    # 1..255
    gamma: float = 1.0  # 0.1..9.99 (1.0 = identity)

    def to_dict(self) -> dict:
        return {
            "enabled": bool(self.enabled),
            "black": int(self.black),
            "white": int(self.white),
            "gamma": float(self.gamma),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> LevelsOptions:
        if not isinstance(data, dict):
            return cls()
        try:
            return cls(
                enabled=bool(data.get("enabled", False)),
                black=_clamp_int(data.get("black", 0), LEVELS_MIN, LEVELS_MAX - 1),
                white=_clamp_int(data.get("white", 255), LEVELS_MIN + 1, LEVELS_MAX),
                gamma=_clamp_float(data.get("gamma", 1.0), GAMMA_MIN, GAMMA_MAX),
            )
        except (TypeError, ValueError):
            return cls()


def _clamp_int(value, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _clamp_float(value, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def apply_levels(arr: np.ndarray, options: LevelsOptions) -> np.ndarray:
    """Stretch ``[black, white]`` to ``[0, 255]`` then apply gamma."""
    if not options.enabled:
        return arr
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"apply_levels expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    black = max(LEVELS_MIN, min(LEVELS_MAX - 1, options.black))
    white = max(black + 1, min(LEVELS_MAX, options.white))
    gamma = _clamp_float(options.gamma, GAMMA_MIN, GAMMA_MAX)

    if black == LEVELS_MIN and white == LEVELS_MAX and abs(gamma - 1.0) < 1e-6:
        return arr

    # Build a 256-entry LUT once and apply via take() — ~constant cost per pixel.
    lut = _build_lut(black, white, gamma)
    out = arr.copy()
    out[..., :3] = lut.take(arr[..., :3])
    return out


def _build_lut(black: int, white: int, gamma: float) -> np.ndarray:
    """Pre-compute the 256-entry remap LUT used by ``apply_levels``."""
    indices = np.arange(256, dtype=np.float32)
    span = max(1, white - black)
    stretched = np.clip((indices - black) / span, 0.0, 1.0)
    # gamma 1.0 = identity; >1 brightens midtones, <1 darkens midtones.
    # We follow the Photoshop convention where the gamma slider's "midtone"
    # mark is 1.0 and increasing the value pushes midtones brighter, which
    # matches ``output = input ** (1/gamma)``.
    gamma_corrected = np.power(stretched, 1.0 / gamma)
    return np.clip(gamma_corrected * 255.0 + 0.5, 0, 255).astype(np.uint8)
