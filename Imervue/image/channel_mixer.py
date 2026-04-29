"""Channel mixer — per-output-channel R/G/B weight matrix.

Each output channel becomes a weighted sum of all three input channels
(plus an optional offset), giving you the full Photoshop Channel Mixer
control surface. The classic use is high-quality monochrome conversion
where the R/G/B contribution to luminance is tunable per shot.

Weights live in ``recipe.extra['channel_mixer']`` as a 3×3 matrix plus
3-element offset vector. Identity (R=1,0,0 / G=0,1,0 / B=0,0,1, offsets
all zero) short-circuits so default-state recipes pay nothing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger("Imervue.channel_mixer")

WEIGHT_MIN = -2.0
WEIGHT_MAX = 2.0
OFFSET_MIN = -1.0
OFFSET_MAX = 1.0


@dataclass
class ChannelMixerOptions:
    """3×3 weight matrix + 3-vector offset for the channel mixer.

    Each row is the weights for one output channel: ``red`` is
    ``[r_from_r, r_from_g, r_from_b]``, ``green`` and ``blue`` similarly.
    Offsets are added after weighting.
    """

    enabled: bool = False
    red: list[float] = field(default_factory=lambda: [1.0, 0.0, 0.0])
    green: list[float] = field(default_factory=lambda: [0.0, 1.0, 0.0])
    blue: list[float] = field(default_factory=lambda: [0.0, 0.0, 1.0])
    offsets: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    monochrome: bool = False  # if True, all three rows share the red row's weights

    def to_dict(self) -> dict:
        return {
            "enabled": bool(self.enabled),
            "red": [float(v) for v in self.red],
            "green": [float(v) for v in self.green],
            "blue": [float(v) for v in self.blue],
            "offsets": [float(v) for v in self.offsets],
            "monochrome": bool(self.monochrome),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> ChannelMixerOptions:
        if not isinstance(data, dict):
            return cls()
        try:
            return cls(
                enabled=bool(data.get("enabled", False)),
                red=_clamp_row(data.get("red"), [1.0, 0.0, 0.0],
                               WEIGHT_MIN, WEIGHT_MAX),
                green=_clamp_row(data.get("green"), [0.0, 1.0, 0.0],
                                 WEIGHT_MIN, WEIGHT_MAX),
                blue=_clamp_row(data.get("blue"), [0.0, 0.0, 1.0],
                                WEIGHT_MIN, WEIGHT_MAX),
                offsets=_clamp_row(data.get("offsets"), [0.0, 0.0, 0.0],
                                   OFFSET_MIN, OFFSET_MAX),
                monochrome=bool(data.get("monochrome", False)),
            )
        except (TypeError, ValueError):
            return cls()


def _clamp_row(value, default: list[float], low: float, high: float) -> list[float]:
    """Coerce ``value`` to a 3-element float list within ``[low, high]``."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return list(default)
    out = []
    for v in value:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return list(default)
        out.append(max(low, min(high, f)))
    return out


def _is_identity_matrix(opts: ChannelMixerOptions) -> bool:
    eps = 1e-6
    return (
        abs(opts.red[0] - 1) < eps and abs(opts.red[1]) < eps and abs(opts.red[2]) < eps
        and abs(opts.green[0]) < eps and abs(opts.green[1] - 1) < eps and abs(opts.green[2]) < eps
        and abs(opts.blue[0]) < eps and abs(opts.blue[1]) < eps and abs(opts.blue[2] - 1) < eps
        and all(abs(o) < eps for o in opts.offsets)
        and not opts.monochrome
    )


def apply_channel_mixer(arr: np.ndarray, options: ChannelMixerOptions) -> np.ndarray:
    """Apply the configured 3×3 weight matrix + offset to ``arr``."""
    if not options.enabled:
        return arr
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"apply_channel_mixer expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    if _is_identity_matrix(options):
        return arr

    matrix = _build_matrix(options)
    offset = np.asarray(options.offsets, dtype=np.float32) * 255.0
    rgb = arr[..., :3].astype(np.float32)
    # einsum: for every pixel multiply the 3-vector input by the 3×3 matrix.
    mixed = np.einsum("ijc,kc->ijk", rgb, matrix) + offset
    out = arr.copy()
    out[..., :3] = np.clip(mixed, 0.0, 255.0).astype(np.uint8)
    return out


def _build_matrix(options: ChannelMixerOptions) -> np.ndarray:
    """3×3 numpy matrix in (output, input) order."""
    if options.monochrome:
        # Flatten to a single weight row used for every output channel.
        row = options.red
        return np.array([row, row, row], dtype=np.float32)
    return np.array(
        [options.red, options.green, options.blue],
        dtype=np.float32,
    )
