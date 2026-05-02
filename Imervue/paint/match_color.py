"""Match color — transfer per-channel mean + std-dev from a reference.

Reinhard's classic colour-transfer algorithm. For each channel the
source pixel is mean-and-std-normalised to z-scores, then re-scaled
into the reference's mean / std-dev distribution. Result: the
source ends up with the reference's overall colour temperature and
contrast while keeping its own structural detail.

Operates directly on RGB rather than going through LAB; the LAB
version produces marginally better results on highly-saturated
inputs but adds the conversion round-trip cost. RGB is good enough
for the common "match this colour mood" workflow and stays within
the project's pure-numpy budget.
"""
from __future__ import annotations

import numpy as np


def match_color(
    source: np.ndarray,
    reference: np.ndarray,
    *,
    strength: float = 1.0,
) -> np.ndarray:
    """Re-tint ``source`` to match ``reference``'s colour statistics.

    Both inputs must be HxWx4 uint8 RGBA (the alpha channel is
    preserved from the source). ``strength`` in ``[0, 1]`` blends
    between source-unchanged and full match — useful for "halfway
    toward the reference's mood" cases.
    """
    if (
        source.ndim != 3
        or source.shape[2] != 4
        or source.dtype != np.uint8
    ):
        raise ValueError(
            f"source must be HxWx4 uint8 RGBA, got "
            f"{source.shape} {source.dtype}",
        )
    if (
        reference.ndim != 3
        or reference.shape[2] != 4
        or reference.dtype != np.uint8
    ):
        raise ValueError(
            f"reference must be HxWx4 uint8 RGBA, got "
            f"{reference.shape} {reference.dtype}",
        )
    strength = max(0.0, min(1.0, float(strength)))
    if strength <= 0.0:
        return source.copy()

    src_rgb = source[..., :3].astype(np.float32)
    ref_rgb = reference[..., :3].astype(np.float32)
    out = source.copy()
    for ch in range(3):
        src_channel = src_rgb[..., ch]
        ref_channel = ref_rgb[..., ch]
        src_mean = float(src_channel.mean())
        src_std = float(src_channel.std())
        ref_mean = float(ref_channel.mean())
        ref_std = float(ref_channel.std())
        # Guard against a constant-channel input — keep the source
        # values rather than dividing by zero.
        if src_std < 1e-6:
            matched = src_channel + (ref_mean - src_mean)
        else:
            normalised = (src_channel - src_mean) / src_std
            matched = normalised * ref_std + ref_mean
        result = src_channel * (1.0 - strength) + matched * strength
        out[..., ch] = np.clip(result, 0.0, 255.0).astype(np.uint8)
    return out


def color_statistics(image: np.ndarray) -> dict[str, tuple[float, float]]:
    """Return per-channel ``(mean, std)`` tuples for an RGBA image.

    Useful for "show me the colour profile of this layer" workflows
    + as a debugging readout when match_color produces unexpected
    output."""
    if (
        image.ndim != 3
        or image.shape[2] != 4
        or image.dtype != np.uint8
    ):
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    rgb = image[..., :3].astype(np.float32)
    return {
        "r": (float(rgb[..., 0].mean()), float(rgb[..., 0].std())),
        "g": (float(rgb[..., 1].mean()), float(rgb[..., 1].std())),
        "b": (float(rgb[..., 2].mean()), float(rgb[..., 2].std())),
    }
