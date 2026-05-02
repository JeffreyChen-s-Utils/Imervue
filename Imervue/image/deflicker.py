"""Time-lapse deflicker — normalise per-frame luminance across a sequence.

Sequential exposure differences in time-lapse shoots produce a
flicker-y final video. The simplest stable fix is to compute each
frame's mean luminance, decide on a target luminance (rolling mean
or fixed reference), and gain-correct each frame to match. This module
implements that as pure numpy so it runs without OpenCV.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.deflicker")

ROLLING_MIN = 1
ROLLING_MAX = 99


@dataclass(frozen=True)
class DeflickerOptions:
    """Configuration for :func:`compute_gain_factors`."""

    rolling_window: int = 9   # frames; odd numbers are easiest to interpret
    target_mode: str = "rolling"  # "rolling" or "global_mean"
    max_gain: float = 1.5
    min_gain: float = 0.66


def frame_luminance_means(frames: list[np.ndarray]) -> np.ndarray:
    """Return a 1-D array of Rec.709 luma means, one per frame."""
    if not frames:
        return np.empty(0, dtype=np.float32)
    means = np.empty(len(frames), dtype=np.float32)
    for i, frame in enumerate(frames):
        _validate_rgba(frame)
        means[i] = _frame_mean(frame)
    return means


def compute_gain_factors(
    means: np.ndarray, options: DeflickerOptions,
) -> np.ndarray:
    """Return one gain multiplier per frame to match the target luminance."""
    if means.size == 0:
        return means
    if options.target_mode == "global_mean":
        target = np.full_like(means, fill_value=float(means.mean()))
    else:
        target = _rolling_mean(means, max(ROLLING_MIN,
                                          min(ROLLING_MAX, options.rolling_window)))
    # Avoid divide-by-zero — black frames contribute no useful target.
    safe = np.where(means > 1e-3, means, 1.0)
    gains = target / safe
    return np.clip(gains, options.min_gain, options.max_gain)


def apply_gain(frame: np.ndarray, gain: float) -> np.ndarray:
    """Multiply ``frame``'s RGB by ``gain``, clipped to uint8 range."""
    _validate_rgba(frame)
    rgb = frame[..., :3].astype(np.float32) * float(gain)
    out = frame.copy()
    out[..., :3] = np.clip(rgb, 0.0, 255.0).astype(np.uint8)
    return out


def deflicker_frames(
    frames: list[np.ndarray], options: DeflickerOptions | None = None,
) -> list[np.ndarray]:
    """Apply gain correction to every frame in the sequence."""
    options = options or DeflickerOptions()
    means = frame_luminance_means(frames)
    gains = compute_gain_factors(means, options)
    return [apply_gain(f, g) for f, g in zip(frames, gains, strict=False)]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_rgba(arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"deflicker expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )


def _frame_mean(frame: np.ndarray) -> float:
    """Rec.709 luminance mean over the RGB channels."""
    rgb = frame[..., :3].astype(np.float32)
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    return float(luma.mean())


def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    """Centred rolling mean with edge replication for the boundary frames."""
    if window <= 1:
        return values.astype(np.float32)
    pad = window // 2
    padded = np.pad(values, (pad, pad), mode="edge")
    csum = np.cumsum(padded, dtype=np.float64)
    rolled = (csum[window:] - csum[:-window]) / window
    # Handle the zero-th edge case: cumsum loses the very first element
    leading = padded[:window].mean()
    return np.concatenate([[leading], rolled]).astype(np.float32)[: values.size]
