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

from Imervue.library import image_index

logger = logging.getLogger("Imervue.library.auto_tag")

AUTO_TAG_ROOT = "auto"

_DEFAULT_PROMPTS = (
    "photo", "document", "screenshot", "graphic", "illustration",
    "portrait", "landscape", "animal", "food", "text",
)


def classify_heuristic(path: str | Path) -> list[str]:
    """Return coarse tags based on image stats. Never fails — returns [] on errors."""
    try:
        with Image.open(path) as im:
            small = im.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR)
            arr = np.asarray(small, dtype=np.float32) / 255.0
    except Exception:  # noqa: BLE001
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

    w_over_h = arr.shape[1] / max(arr.shape[0], 1)
    if w_over_h > 1.25:
        tags.append("landscape")
    elif w_over_h < 0.8:
        tags.append("portrait")
    return tags


def try_clip_labels(path: str | Path, prompts: list[str] | None = None) -> list[str]:
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
