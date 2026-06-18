"""False-colour exposure map — paint each luminance zone a distinct colour.

Maps pixel brightness through an IRE-style zone ramp (crushed blacks → purple,
shadows → blue, mid-grey → green, skin → grey/pink, highlights → yellow, blown
→ red) so exposure can be judged precisely by colour rather than guessed from a
greyscale image. The convention follows on-set monitor false-colour.

Pure NumPy: a 256-entry lookup table indexed by luma.
"""
from __future__ import annotations

import numpy as np

_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4

# (inclusive-low IRE %, exclusive-high IRE %, RGB colour) zones.
_ZONES = (
    (0, 3, (40, 0, 60)),       # crushed black — purple
    (3, 12, (0, 0, 200)),      # deep shadow — blue
    (12, 38, (0, 170, 190)),   # shadow — teal
    (38, 48, (0, 190, 0)),     # lower mid — green
    (48, 54, (140, 140, 140)), # mid-grey — grey
    (54, 70, (220, 130, 160)), # skin / upper mid — pink
    (70, 88, (210, 200, 0)),   # highlight — straw
    (88, 97, (240, 150, 0)),   # bright highlight — orange
    (97, 101, (230, 0, 0)),    # clipped white — red
)
_IRE_MAX = 100.0


def _build_lut() -> np.ndarray:
    lut = np.zeros((256, _RGB_CHANNELS), dtype=np.uint8)
    for low, high, color in _ZONES:
        lo = int(round(low / _IRE_MAX * 255))
        hi = int(round(high / _IRE_MAX * 255))
        lut[lo:hi] = color
    lut[255] = _ZONES[-1][2]  # ensure the very top maps to the clip colour
    return lut


_LUT = _build_lut()


def false_color(img: np.ndarray) -> np.ndarray:
    """Return an HxWx4 RGBA false-colour exposure map of *img*."""
    if img.ndim != _RGB_CHANNELS or img.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {img.shape}")
    rgb = img[:, :, :3].astype(np.float32)
    luma = np.clip(np.rint(rgb @ _LUMA_WEIGHTS), 0, 255).astype(np.uint8)
    mapped = _LUT[luma]
    out = np.empty((*luma.shape, _RGBA_CHANNELS), dtype=np.uint8)
    out[..., :3] = mapped
    out[..., 3] = 255
    return out
