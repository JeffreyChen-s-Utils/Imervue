"""Pure detection + censoring core for the safety_review plugin.

No Qt here. Heavy ML libraries (nudenet, ultralytics, huggingface_hub) and
Pillow are imported lazily inside the functions that need them so the module
imports cheaply and the dependency surface stays opt-in.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

from safety_review._constants import (
    _ERAX_MODEL,
    _ERAX_REPO,
    _ERAX_REVISION,
    _FMT_MAP,
    _IMAGE_EXTS,
    ANIME_MOSAIC_CLASSES,
    MIN_CONFIDENCE,
    MODE_ANIME,
    MODE_AUTO,
    MODE_REAL,
    STYLE_BLACK,
    STYLE_BLUR,
    STYLE_MOSAIC,
    _categories_to_anime_classes,
    _categories_to_real_labels,
)

logger = logging.getLogger("Imervue.plugin.safety_review")

# Anime-color heuristic threshold — fewer unique quantized colours than this
# marks an image as an illustration rather than a photo.
_ANIME_COLOR_THRESHOLD = 1500

# ---------------------------------------------------------------------------
# Cached models
# ---------------------------------------------------------------------------
_cached_detector = None
_cached_detector_lock = threading.Lock()

_cached_anime_model = None
_cached_anime_lock = threading.Lock()


def _get_detector():
    """Return a cached NudeDetector, creating it on first call."""
    global _cached_detector
    with _cached_detector_lock:
        if _cached_detector is None:
            from nudenet import NudeDetector
            _cached_detector = NudeDetector()
        return _cached_detector


def _get_anime_model():
    """Return a cached EraX YOLO model, downloading on first call."""
    global _cached_anime_model
    with _cached_anime_lock:
        if _cached_anime_model is None:
            from huggingface_hub import hf_hub_download
            from ultralytics import YOLO
            model_path = hf_hub_download(
                repo_id=_ERAX_REPO, filename=_ERAX_MODEL,
                revision=_ERAX_REVISION)
            _cached_anime_model = YOLO(model_path)
        return _cached_anime_model


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _find_external_python() -> str | None:
    from Imervue.plugin.pip_installer import _find_python
    return _find_python()


def _subprocess_kwargs() -> dict:
    kw: dict = {
        "stdin": subprocess.DEVNULL,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kw


def _scan_folder(folder: str) -> list[str]:
    """Return sorted list of image paths in *folder* (non-recursive)."""
    result = []
    try:
        for entry in os.scandir(folder):
            if entry.is_file() and Path(entry.name).suffix.lower() in _IMAGE_EXTS:
                result.append(entry.path)
    except OSError:
        pass
    result.sort(key=lambda p: os.path.basename(p).lower())
    return result


# ---------------------------------------------------------------------------
# Geometry + rendering
# ---------------------------------------------------------------------------

def _detect_image_mode(src: str) -> str:
    """Heuristic: anime/illustration images have fewer unique quantized colors."""
    from PIL import Image
    img = Image.open(src).convert("RGB")
    img = img.resize((128, 128), Image.Resampling.BILINEAR)
    quantized = set()
    for r, g, b in img.getdata():
        quantized.add((r >> 3, g >> 3, b >> 3))
    return MODE_ANIME if len(quantized) < _ANIME_COLOR_THRESHOLD else MODE_REAL


def _expand_box(x1, y1, x2, y2, padding: int, expand_pct: int,
                 iw: int, ih: int):
    """Expand a bounding box by fixed padding AND/OR percentage of box size."""
    bw = x2 - x1
    bh = y2 - y1
    # Percentage-based expansion (% of the box's own size)
    if expand_pct > 0:
        ex = int(bw * expand_pct / 100)
        ey = int(bh * expand_pct / 100)
        x1 -= ex
        y1 -= ey
        x2 += ex
        y2 += ey
    # Fixed-pixel padding (additive)
    if padding > 0:
        x1 -= padding
        y1 -= padding
        x2 += padding
        y2 += padding
    return max(0, x1), max(0, y1), min(iw, x2), min(ih, y2)


def _censor_black(img, box):
    from PIL import ImageDraw
    ImageDraw.Draw(img).rectangle(box, fill=(0, 0, 0))


def _censor_blur(img, box, w, h):
    from PIL import ImageFilter
    region = img.crop(box)
    radius = max(max(w, h) // 5, 10)
    blurred = region.filter(ImageFilter.GaussianBlur(radius=radius))
    img.paste(blurred, (box[0], box[1]))


def _censor_mosaic(img, box, w, h, block_size):
    from PIL import Image as _Img
    region = img.crop(box)
    bs = max(2, block_size)
    small = region.resize(
        (max(1, w // bs), max(1, h // bs)),
        resample=_Img.Resampling.BILINEAR,
    )
    mosaic = small.resize((w, h), resample=_Img.Resampling.NEAREST)
    img.paste(mosaic, (box[0], box[1]))


def _censor_region(img, x1, y1, x2, y2, block_size, style=STYLE_MOSAIC):
    """Apply censoring (mosaic / blur / black) to a region (in-place)."""
    w = x2 - x1
    h = y2 - y1
    if w <= 0 or h <= 0:
        return
    box = (x1, y1, x2, y2)
    if style == STYLE_BLACK:
        _censor_black(img, box)
    elif style == STYLE_BLUR:
        _censor_blur(img, box, w, h)
    else:  # mosaic (default)
        _censor_mosaic(img, box, w, h, block_size)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _detect_regions_real(detector, src: str, confidence: float,
                          labels: frozenset[str]):
    """NudeNet detection → list of (x1, y1, x2, y2)."""
    detections = detector.detect(src)
    boxes = []
    for d in detections:
        if d["class"] in labels and d["score"] >= confidence:
            boxes.append(tuple(d["box"]))
    return boxes


def _detect_regions_anime(src: str, confidence: float,
                           classes: frozenset[int] = ANIME_MOSAIC_CLASSES):
    """EraX YOLO11 detection → list of (x1, y1, x2, y2)."""
    model = _get_anime_model()
    results = model(src, conf=confidence, iou=0.3, verbose=False)
    boxes = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            if cls_id in classes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                boxes.append((int(x1), int(y1), int(x2), int(y2)))
    return boxes


def _detect_boxes(detector, src, confidence, mode, categories):
    """Resolve the detection mode and return the list of boxes to censor."""
    actual_mode = mode
    if mode == MODE_AUTO:
        actual_mode = _detect_image_mode(src)
    if actual_mode == MODE_ANIME:
        classes = _categories_to_anime_classes(categories)
        return _detect_regions_anime(src, confidence, classes)
    real_labels = _categories_to_real_labels(categories)
    return _detect_regions_real(detector, src, confidence, real_labels)


def _copy_unchanged(src: str, dst: str) -> None:
    """Copy the source verbatim when no regions were detected."""
    if os.path.normpath(src) != os.path.normpath(dst):
        import shutil
        shutil.copy2(src, dst)


def _save_image(img, dst: str) -> None:
    fmt = _FMT_MAP.get(Path(dst).suffix.lower(), "PNG")
    if fmt == "JPEG" and img.mode == "RGBA":
        img = img.convert("RGB")
    img.save(dst, format=fmt)


def _process_single_image(
    detector,
    src: str,
    dst: str,
    block_size: int,
    padding: int,
    confidence: float = MIN_CONFIDENCE,
    expand_pct: int = 0,
    mode: str = MODE_REAL,
    style: str = STYLE_MOSAIC,
    categories=None,
) -> int:
    """Detect + censor one image.  Returns the number of regions processed."""
    from PIL import Image

    boxes = _detect_boxes(detector, src, confidence, mode, categories)
    if not boxes:
        _copy_unchanged(src, dst)
        return 0

    img = Image.open(src)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    iw, ih = img.width, img.height
    for box in boxes:
        ex1, ey1, ex2, ey2 = _expand_box(*box, padding, expand_pct, iw, ih)
        _censor_region(img, ex1, ey1, ex2, ey2, block_size, style=style)

    _save_image(img, dst)
    return len(boxes)
