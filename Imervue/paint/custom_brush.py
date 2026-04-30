"""Custom brush-tip loader.

Lets the user supply their own PNG / JPEG / TIFF as a brush kernel.
The image's alpha channel (if present) is preferred — that's how
exported MediBang and Photoshop brush tips encode the stamp shape —
otherwise the grayscale luminance is used so plain black-on-white
stamps still work.

Sized down to the active brush size with bilinear filtering and
normalised to ``[0, 1]`` so the result drops into ``apply_dab`` in
place of the default round kernel.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def load_brush_tip(path: str | Path, size: int) -> np.ndarray:
    """Return an ``(size, size)`` float32 kernel in ``[0, 1]``.

    Errors are converted to :class:`OSError` so callers (the brush
    dock, the dispatcher) can swallow them and fall back to the
    default round kernel without crashing the app.
    """
    if size < 1:
        raise ValueError(f"size must be ≥ 1, got {size}")
    p = Path(path)
    if not p.is_file():
        raise OSError(f"brush tip not found: {path}")
    try:
        with Image.open(p) as src:
            tip = src.convert("RGBA")
            tip = tip.resize((size, size), Image.Resampling.BILINEAR)
            arr = np.array(tip, dtype=np.uint8)
    except (OSError, ValueError) as exc:
        raise OSError(f"failed to read brush tip {path}: {exc}") from exc

    return _kernel_from_rgba(arr)


def _kernel_from_rgba(arr: np.ndarray) -> np.ndarray:
    """Pick alpha if it carries non-trivial info, else fall back to luma."""
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"_kernel_from_rgba expects HxWx4 uint8 RGBA, got "
            f"{arr.shape} {arr.dtype}",
        )
    alpha = arr[..., 3]
    # Alpha-driven tip: many brush PNGs are pure-alpha shapes on a white
    # RGB background. Use the alpha channel directly when it actually
    # varies — otherwise the tip carries no shape and we fall through to
    # the luminance branch below.
    if alpha.max() > 0 and alpha.min() < alpha.max():
        return (alpha.astype(np.float32) / 255.0).astype(np.float32)
    # Fall back to luminance — handles plain black-shape-on-white PNGs.
    luma = (
        0.2126 * arr[..., 0]
        + 0.7152 * arr[..., 1]
        + 0.0722 * arr[..., 2]
    ).astype(np.float32)
    # Brush kernels usually paint where the source is dark — invert.
    luma = 255.0 - luma
    luma_max = float(luma.max())
    if luma_max <= 0:
        return np.zeros_like(luma, dtype=np.float32)
    return (luma / luma_max).astype(np.float32)


def is_supported_extension(path: str | Path) -> bool:
    """Return ``True`` if ``path`` looks like a brush-tip image we can read."""
    return Path(path).suffix.lower() in {
        ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp",
    }
