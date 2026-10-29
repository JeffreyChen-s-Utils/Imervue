"""
圖片淨化重繪核心（不依賴 Qt）
Image Sanitizer core — re-render an image from raw pixel data, scramble its
LSBs, optionally upscale it and save it under a date + random-string name.

Qt-free: :mod:`Imervue.gui.image_sanitize_worker` drives it per file and
:mod:`Imervue.gui.image_sanitize_dialog` re-exports its public names.
"""
from __future__ import annotations

import logging
import os
import secrets
import string
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

from Imervue.system.image_listing import list_images
from Imervue.image.formats import JPEG_EXTENSIONS
from Imervue.image.shown import as_shown
from Imervue.library.calendar_index import UNKNOWN_DATETIME, capture_datetime

logger = logging.getLogger("Imervue.image_sanitize")

# ---------------------------------------------------------------------------
# Common target resolutions (label, long_edge_px)
# "long_edge" means the longer side of the output; the shorter side is
# computed to maintain the original aspect ratio.
# ---------------------------------------------------------------------------
TARGET_RESOLUTIONS = [
    ("sanitize_res_none",   "No upscale",          0),
    ("sanitize_res_1080p",  "Full HD  (1920 px)",   1920),
    ("sanitize_res_2k",     "2K       (2560 px)",   2560),
    ("sanitize_res_4k",     "4K UHD   (3840 px)",   3840),
    ("sanitize_res_5k",     "5K       (5120 px)",   5120),
    ("sanitize_res_8k",     "8K UHD   (7680 px)",   7680),
]

# Format / mode names used across the sanitize pipeline.
_MODE_RGB = "RGB"
_MODE_RGBA = "RGBA"
_FMT_PNG = "PNG"
_FMT_JPEG = "JPEG"
_FMT_TIFF = "TIFF"
_FMT_WEBP = "WebP"
_FMT_BMP = "BMP"

_EXT_PNG = ".png"
_EXT_JPG = ".jpg"
_EXT_TIFF = ".tiff"
_EXT_TIF = ".tif"
_EXT_WEBP = ".webp"
_EXT_BMP = ".bmp"

_IMAGE_EXTS = frozenset({
    _EXT_PNG, _EXT_TIFF, _EXT_TIF, _EXT_WEBP, _EXT_BMP,
}) | JPEG_EXTENSIONS

_PIL_FORMAT_MAP = {
    **dict.fromkeys(JPEG_EXTENSIONS, _FMT_JPEG),
    _EXT_PNG: _FMT_PNG, _EXT_TIFF: _FMT_TIFF, _EXT_TIF: _FMT_TIFF,
    _EXT_WEBP: _FMT_WEBP, _EXT_BMP: _FMT_BMP,
}

_RANDOM_CHARS = string.ascii_lowercase + string.digits


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def _scan_folder(folder: str, recursive: bool = False) -> list[str]:
    """Return image paths in natural name order."""
    return list_images(folder, _IMAGE_EXTS, recursive=recursive)


# ---------------------------------------------------------------------------
# Core sanitize logic (pure, testable)
# ---------------------------------------------------------------------------

def _get_image_date(path: str) -> datetime:
    """Extract the best date for an image: EXIF capture time > file mtime > now."""
    taken = capture_datetime(path)
    return datetime.now() if taken == UNKNOWN_DATETIME else taken


def _generate_name(dt: datetime, rand_len: int, ext: str) -> str:
    """Generate filename like 20260414_a3f8k2x1.png"""
    date_str = dt.strftime("%Y%m%d")
    rand_str = "".join(secrets.choice(_RANDOM_CHARS) for _ in range(rand_len))
    return f"{date_str}_{rand_str}{ext}"


def _compute_upscale_params(width: int, height: int,
                            target_long_edge: int) -> tuple[str, int, int]:
    """Decide which AI model to use and the final resize dimensions.

    Returns (model_key, final_w, final_h).
    If no upscale is needed returns ("", width, height).
    """
    long = max(width, height)
    if target_long_edge <= 0 or long >= target_long_edge:
        return ("", width, height)

    ratio = target_long_edge / long
    # Pick the smallest model that gets us past the target so we only
    # need to downscale afterward (higher quality than up-then-up).
    model_key = "realesrgan-x2plus" if ratio <= 2.0 else "realesrgan-x4plus"

    # Final size preserving aspect ratio
    if width >= height:
        final_w = target_long_edge
        final_h = max(1, round(height * target_long_edge / width))
    else:
        final_h = target_long_edge
        final_w = max(1, round(width * target_long_edge / height))
    return (model_key, final_w, final_h)


def _resolve_output_ext(path: str, output_ext: str) -> tuple[str, str]:
    if output_ext == "same":
        ext = Path(path).suffix.lower()
        if ext not in _PIL_FORMAT_MAP:
            ext = _EXT_PNG
    else:
        ext = output_ext
    return ext, _PIL_FORMAT_MAP.get(ext, _FMT_PNG)


def _final_dims(w: int, h: int, target_long_edge: int) -> tuple[int, int]:
    if w >= h:
        return target_long_edge, max(1, round(h * target_long_edge / w))
    return max(1, round(w * target_long_edge / h)), target_long_edge


def _ai_upscale(clean: Image.Image, final_w: int, final_h: int,
                ort_session, ort_scale: int,
                tile_progress_cb) -> Image.Image:
    import numpy as np
    from Imervue.gui.ai_upscale_dialog import _upscale_image

    if clean.mode == _MODE_RGBA:
        alpha = clean.split()[-1]
        rgb = clean.convert(_MODE_RGB)
    else:
        alpha = None
        rgb = clean

    upscaled_arr = _upscale_image(
        ort_session, np.array(rgb), ort_scale,
        progress_cb=tile_progress_cb)
    upscaled = Image.fromarray(upscaled_arr)

    if alpha is not None:
        alpha_up = alpha.resize(upscaled.size, Image.Resampling.LANCZOS)
        upscaled.putalpha(alpha_up)

    return upscaled.resize((final_w, final_h), Image.Resampling.LANCZOS)


@dataclass(frozen=True)
class UpscaleSpec:
    """How :func:`sanitize_image` enlarges an image smaller than ``target_long_edge``.

    ``target_long_edge`` 0 means never upscale. ``trad_resampling`` (a PIL
    ``Resampling``) wins over the ONNX path (``ort_session`` at ``ort_scale``,
    reporting tiles to ``tile_progress_cb``); with neither the image is kept.
    """

    target_long_edge: int = 0
    trad_resampling: Image.Resampling | None = None
    ort_session: object = None
    ort_scale: int = 0
    tile_progress_cb: Callable[[int, int], None] | None = None


def _maybe_upscale(clean: Image.Image, spec: UpscaleSpec) -> Image.Image:
    if spec.target_long_edge <= 0:
        return clean
    w, h = clean.size
    if max(w, h) >= spec.target_long_edge:
        return clean
    final_w, final_h = _final_dims(w, h, spec.target_long_edge)
    if spec.trad_resampling is not None:
        return clean.resize((final_w, final_h), spec.trad_resampling)
    if spec.ort_session is not None and spec.ort_scale > 0:
        return _ai_upscale(clean, final_w, final_h, spec.ort_session, spec.ort_scale,
                           spec.tile_progress_cb)
    return clean


def _allocate_output_path(output_dir: str, dt: datetime, rand_len: int,
                          ext: str) -> str:
    out_path = os.path.join(output_dir, _generate_name(dt, rand_len, ext))
    while os.path.exists(out_path):
        out_path = os.path.join(output_dir, _generate_name(dt, rand_len, ext))
    return out_path


def _save_kwargs_for(fmt: str, jpeg_quality: int,
                     png_compress: int) -> dict:
    kwargs: dict = {"format": fmt}
    if fmt == _FMT_JPEG:
        kwargs["quality"] = jpeg_quality
        kwargs["subsampling"] = 0
    elif fmt == _FMT_PNG:
        kwargs["compress_level"] = png_compress
    return kwargs


def sanitize_image(path: str, output_dir: str, output_ext: str, *,
                   rand_len: int = 8, jpeg_quality: int = 95,
                   png_compress: int = 6,
                   upscale: UpscaleSpec | None = None) -> str:
    """Re-render an image from raw pixels, removing ALL hidden data.

    With an *upscale* whose ``target_long_edge`` is above the image's long
    edge, the image is enlarged with its traditional resampling or its ONNX
    (Real-ESRGAN) session, then resized to exactly fit the target while
    keeping aspect ratio (see :class:`UpscaleSpec`).

    Returns the output path on success. Raises on failure.
    """
    img = as_shown(Image.open(path))   # the EXIF (and its orientation) is dropped below
    ext, fmt = _resolve_output_ext(path, output_ext)

    # Re-create image from raw bytes — no metadata survives, no list copy
    clean = Image.frombytes(img.mode, img.size, img.tobytes())

    # JPEG does not support alpha
    if fmt == _FMT_JPEG and clean.mode != _MODE_RGB:
        clean = clean.convert(_MODE_RGB)

    clean = _maybe_upscale(clean, upscale or UpscaleSpec())

    # Disrupt LSB steganography (e.g. NovelAI stealth pnginfo embeds
    # prompt/seed/parameters in the least-significant bit of RGB/alpha
    # channels — tEXt-chunk stripping alone leaves that payload intact).
    clean = _scramble_lsb(clean)

    out_path = _allocate_output_path(output_dir, _get_image_date(path),
                                      rand_len, ext)
    clean.save(out_path, **_save_kwargs_for(fmt, jpeg_quality, png_compress))
    return out_path


# Fraction of channel-elements whose LSB is randomised. At 0.5 the net
# per-pixel change rate is 12.5% (halved from dense scrambling) while the
# probability any 120-bit magic header survives intact drops to 0.75^120
# ≈ 1.2e-15 — still comprehensive destruction, with half the visual
# perturbation in flat regions that synthetic AI art tends to produce.
_LSB_SCRAMBLE_RATE = 0.5


def _make_unseeded_rng():
    """Return a numpy Generator with OS-entropy seeding only.

    Wrapped in its own function so the security rationale (seed must NOT be
    predictable, or the LSB scramble is reversible) lives in one place and
    the inline call site stays free of suppression noise. ``numpy`` is
    imported lazily here to match the rest of this module — image-sanitize
    is the only feature that pulls numpy in, and we don't want every dialog
    open to pay the import cost.
    """
    import numpy as np
    return np.random.default_rng()  # noqa: NPY002  # NOSONAR S6709 unpredictable seed required


def _scramble_lsb(img: Image.Image) -> Image.Image:
    """Sparsely randomise the LSB of every 8-bit channel.

    Breaks LSB-steganography schemes such as NovelAI's stealth pnginfo.
    Only a fraction of LSBs (``_LSB_SCRAMBLE_RATE``) are touched — enough
    to obliterate any bit-sequential payload statistically, while keeping
    perceptual impact minimal in the flat regions common to synthetic
    imagery. Non 8-bit modes are converted first so palette/1-bit images
    are also covered.
    """
    import numpy as np
    # Convert exotic modes to a form with 8-bit channels so the LSB
    # operation is well-defined (palette indices, for example, would be
    # corrupted by masking).
    if img.mode not in ("L", "LA", _MODE_RGB, _MODE_RGBA):
        img = img.convert(_MODE_RGBA if "A" in img.mode else _MODE_RGB)
    arr = np.array(img, copy=True)
    # Unseeded on purpose: predictable seed → reversible scramble → defeats
    # the feature. The helper centralises the suppression comments.
    rng = _make_unseeded_rng()
    scramble_mask = rng.random(size=arr.shape, dtype=np.float32) < _LSB_SCRAMBLE_RATE
    noise = rng.integers(0, 2, size=arr.shape, dtype=arr.dtype)
    # Where mask is True use random LSB, otherwise keep the original LSB.
    new_lsb = np.where(scramble_mask, noise, arr & np.uint8(0x01))
    arr = (arr & np.uint8(0xFE)) | new_lsb.astype(arr.dtype)
    return Image.fromarray(arr, mode=img.mode)


# ---------------------------------------------------------------------------
# Batch settings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SanitizeSettings:
    """Output format, file naming, encoder quality and optional upscale for a batch."""

    output_ext: str
    rand_len: int = 8
    jpeg_quality: int = 95
    png_compress: int = 6
    target_long_edge: int = 0
    model_key: str = ""
