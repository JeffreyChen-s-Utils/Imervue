"""
Auto-tagging — heuristic content classifier + optional CLIP ONNX hook.

The heuristic classifier inspects image statistics to assign coarse tags
(``screenshot``, ``document``, ``photo``, ``graphic``) without any model
dependency. If ``onnxruntime`` and a CLIP model file are available, we
delegate to that for richer zero-shot labels. The hook is intentionally
lazy — the import chain for CLIP pulls in heavy packages we don't want
to load unless the user actually asks for auto-tagging.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.image.formats import ensure_pillow_opener
from Imervue.image.orientation import exif_orientation
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.image.shown import as_shown_8bit
from Imervue.library import image_index

logger = logging.getLogger("Imervue.library.auto_tag")

AUTO_TAG_ROOT = "auto"

_DEFAULT_PROMPTS = (
    "photo", "document", "screenshot", "graphic", "illustration",
    "portrait", "landscape", "animal", "food", "text",
)


_SAMPLE_EDGE = 64
_PREVIEW_EDGE = 256


def _shown_sample(path: str | Path) -> tuple[np.ndarray, float]:
    """A 64x64 RGB sample of *path* as the viewer shows it, and its upright width / height.

    Turned upright first, so a portrait phone photo (stored landscape with an
    EXIF turn) measures as portrait, with 16-bit and float grey scaled and
    colour profiles applied like on screen. The aspect is taken before the
    square sample, which has none. Raises ``IMAGE_READ_ERRORS``.
    """
    ensure_pillow_opener(Path(path).suffix)
    with Image.open(path) as im:
        code = exif_orientation(im)
        im.thumbnail((_PREVIEW_EDGE, _PREVIEW_EDGE))
        shown = as_shown_8bit(im, code, mode="RGB")
    aspect = shown.width / max(shown.height, 1)
    small = shown.resize((_SAMPLE_EDGE, _SAMPLE_EDGE), Image.Resampling.BILINEAR)
    return np.asarray(small, dtype=np.float32) / 255.0, aspect


def classify_heuristic(path: str | Path) -> list[str]:
    """Return coarse tags based on image stats; ``[]`` for an image Pillow cannot read."""
    try:
        arr, w_over_h = _shown_sample(path)
    except IMAGE_READ_ERRORS:
        return []

    # Saturation gives a cheap "photo vs document/screenshot" signal.
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    max_c = np.maximum.reduce([r, g, b])
    min_c = np.minimum.reduce([r, g, b])
    brightness = max_c
    saturation = np.where(max_c > 0, (max_c - min_c) / np.maximum(max_c, 1e-6), 0)
    mean_sat = float(saturation.mean())
    # Edge density: how many abrupt luma transitions — documents and
    # screenshots have sharp text-like edges.
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    gx = np.abs(np.diff(luma, axis=1)).mean()
    gy = np.abs(np.diff(luma, axis=0)).mean()
    edge_score = float(gx + gy)

    tags: list[str] = []
    if mean_sat < 0.1 and brightness.mean() > 0.7:
        tags.append("document")
    elif mean_sat < 0.15 and edge_score > 0.12:
        tags.append("screenshot")
    elif mean_sat > 0.25:
        tags.append("photo")
    else:
        tags.append("graphic")

    if w_over_h > 1.25:
        tags.append("landscape")
    elif w_over_h < 0.8:
        tags.append("portrait")
    return tags


def try_clip_labels(_path: str | Path, _prompts: list[str] | None = None) -> list[str]:
    """Attempt zero-shot labelling via a local CLIP ONNX model.

    Returns an empty list if onnxruntime or the model file isn't present —
    callers fall back to ``classify_heuristic``.
    """
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return []
    from Imervue.system.app_paths import app_dir
    model_path = app_dir() / "models" / "clip_vit_b32.onnx"
    if not model_path.is_file():
        return []
    # We keep the actual inference out of here to avoid hard-coding a tokenizer.
    # Plugins can replace this function by monkey-patching if they ship a full
    # CLIP pipeline; base install stays dependency-free.
    logger.debug("CLIP model present but inference hook not wired (%s)", model_path)
    return []


def auto_tag_image(path: str) -> list[str]:
    """Compute tags for ``path`` and write them into the library index under ``auto/*``."""
    labels = try_clip_labels(path) or classify_heuristic(path)
    tag_paths = [f"{AUTO_TAG_ROOT}/{label}" for label in labels]
    for tp in tag_paths:
        image_index.add_image_tag(path, tp)
    return tag_paths


def auto_tag_batch(paths: list[str], *, progress_cb=None) -> dict[str, list[str]]:
    """Tag a batch of images; optional ``progress_cb(current, total, path)``."""
    results: dict[str, list[str]] = {}
    total = len(paths)
    for i, p in enumerate(paths, start=1):
        results[p] = auto_tag_image(p)
        if progress_cb is not None:
            progress_cb(i, total, p)
    return results
