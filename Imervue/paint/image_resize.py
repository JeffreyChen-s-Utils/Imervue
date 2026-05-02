"""Pure-numpy whole-image resampling — Image Size dialog backend.

The PaintDocument's :meth:`resize` verb (added by Phase 25b) calls
into here to resize every layer image, layer mask, and the active
selection mask in lock-step so post-resize state stays consistent.

Resampling uses Pillow as the workhorse — bilinear / bicubic /
nearest are all already implemented and battle-tested there. We
keep this layer Qt-free and image-format-agnostic so unit tests
don't need a display server.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

# Pillow's documented filter names — the dialog combo maps user
# choices straight onto these.
RESAMPLE_FILTERS = ("nearest", "bilinear", "bicubic", "lanczos")
DEFAULT_RESAMPLE = "bilinear"

_FILTER_TO_PIL = {
    "nearest": Image.Resampling.NEAREST,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
    "lanczos": Image.Resampling.LANCZOS,
}

# Hard caps mirror the canvas creation dialog so a careless paste
# of huge dimensions can't OOM the Python process.
RESIZE_DIM_MIN = 1
RESIZE_DIM_MAX = 16384


def resize_rgba(
    arr: np.ndarray,
    new_w: int, new_h: int,
    *, resample: str = DEFAULT_RESAMPLE,
) -> np.ndarray:
    """Resample an HxWx4 ``uint8`` RGBA buffer to (``new_h``, ``new_w``).

    Returns a fresh contiguous array; the input is never mutated.
    Identity (target dims equal source dims) short-circuits to a
    copy so the caller gets the same lifecycle whether or not a
    real resize happened.
    """
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"resize_rgba expects HxWx4 uint8 RGBA, got {arr.shape}"
            f" {arr.dtype}",
        )
    new_w = _validate_dim(new_w, "width")
    new_h = _validate_dim(new_h, "height")
    if resample not in _FILTER_TO_PIL:
        raise ValueError(
            f"unknown resample {resample!r}; expected one of {RESAMPLE_FILTERS}",
        )
    if arr.shape[:2] == (new_h, new_w):
        return arr.copy()
    pil = Image.fromarray(arr, mode="RGBA")
    resized = pil.resize((new_w, new_h), _FILTER_TO_PIL[resample])
    return np.ascontiguousarray(np.asarray(resized, dtype=np.uint8))


def resize_mask(
    mask: np.ndarray,
    new_w: int, new_h: int,
    *, resample: str = DEFAULT_RESAMPLE,
) -> np.ndarray:
    """Resample an HxW ``uint8`` mask. Returns a fresh contiguous array.

    Greyscale masks use the same Pillow filter so a nearest-neighbour
    pass keeps a layer mask hard-edged where the matching layer was
    also nearest-resized.
    """
    if mask.ndim != 2 or mask.dtype != np.uint8:
        raise ValueError(
            f"resize_mask expects HxW uint8, got {mask.shape} {mask.dtype}",
        )
    new_w = _validate_dim(new_w, "width")
    new_h = _validate_dim(new_h, "height")
    if resample not in _FILTER_TO_PIL:
        raise ValueError(
            f"unknown resample {resample!r}",
        )
    if mask.shape == (new_h, new_w):
        return mask.copy()
    pil = Image.fromarray(mask, mode="L")
    resized = pil.resize((new_w, new_h), _FILTER_TO_PIL[resample])
    return np.ascontiguousarray(np.asarray(resized, dtype=np.uint8))


def resize_selection(
    selection: np.ndarray, new_w: int, new_h: int,
) -> np.ndarray:
    """Resample a bool HxW selection.

    Always uses nearest-neighbour — interpolating a bool mask to
    floats and re-thresholding produces a soft selection that
    surprises users. The convention matches Photoshop / MediBang.
    """
    if selection.ndim != 2 or selection.dtype != np.bool_:
        raise ValueError(
            f"resize_selection expects HxW bool, got {selection.shape}"
            f" {selection.dtype}",
        )
    as_uint = selection.astype(np.uint8) * 255
    resampled = resize_mask(as_uint, new_w, new_h, resample="nearest")
    return resampled >= 128


def scaled_dims_keep_aspect(
    src_w: int, src_h: int, target_w: int, target_h: int,
) -> tuple[int, int]:
    """Scale (``src_w``, ``src_h``) to fit inside (``target_w``,
    ``target_h``) while preserving aspect ratio.

    Useful for the dialog's "Constrain proportions" checkbox: if the
    user types only one dimension, the other is derived from the
    source aspect.
    """
    if src_w <= 0 or src_h <= 0:
        raise ValueError(f"src dims must be positive, got {src_w}x{src_h}")
    if target_w <= 0 or target_h <= 0:
        raise ValueError(
            f"target dims must be positive, got {target_w}x{target_h}",
        )
    src_aspect = src_w / src_h
    target_aspect = target_w / target_h
    if src_aspect > target_aspect:
        # Source is wider — limit by width.
        out_w = target_w
        out_h = max(1, int(round(target_w / src_aspect)))
    else:
        out_h = target_h
        out_w = max(1, int(round(target_h * src_aspect)))
    return (out_w, out_h)


def _validate_dim(value, label: str) -> int:
    try:
        as_int = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be int, got {value!r}") from exc
    if not RESIZE_DIM_MIN <= as_int <= RESIZE_DIM_MAX:
        raise ValueError(
            f"{label} must be in [{RESIZE_DIM_MIN}, {RESIZE_DIM_MAX}], got {as_int}",
        )
    return as_int
