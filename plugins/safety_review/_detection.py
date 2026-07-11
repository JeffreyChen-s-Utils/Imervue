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
    SHAPE_ELLIPSE,
    SHAPE_PRECISE,
    SHAPE_RECT,
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

_cached_fastsam = None
_cached_fastsam_lock = threading.Lock()

# FastSAM (ships via ultralytics) — a light segmentation model used only for
# the optional "precise" censor shape. Auto-downloaded by ultralytics on first
# use, like the anime YOLO weights.
_FASTSAM_MODEL = "FastSAM-s.pt"


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


def _scan_folder(folder: str, recursive: bool = False) -> list[str]:
    """Return a sorted list of image paths in *folder*.

    With *recursive* False only the folder's direct children are returned
    (sorted by filename). With *recursive* True the whole subtree is walked
    and the result is sorted by full path so each subfolder's images stay
    grouped and the order is deterministic across platforms.
    """
    if recursive:
        return _scan_folder_recursive(folder)
    result = []
    try:
        for entry in os.scandir(folder):
            if entry.is_file() and Path(entry.name).suffix.lower() in _IMAGE_EXTS:
                result.append(entry.path)
    except OSError:
        pass
    result.sort(key=lambda p: os.path.basename(p).lower())
    return result


def _scan_folder_recursive(folder: str) -> list[str]:
    """Return sorted image paths in *folder* and every subfolder below it."""
    result = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if Path(name).suffix.lower() in _IMAGE_EXTS:
                result.append(os.path.join(root, name))
    result.sort(key=lambda p: p.lower())
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


def _censored_region(region, w, h, block_size, style):
    """Return the censored copy of *region* (same size), for the chosen style."""
    from PIL import Image as _Img
    if style == STYLE_BLACK:
        return _Img.new(region.mode, (w, h), 0)
    if style == STYLE_BLUR:
        from PIL import ImageFilter
        radius = max(max(w, h) // 5, 10)
        return region.filter(ImageFilter.GaussianBlur(radius=radius))
    # mosaic (default)
    bs = max(2, block_size)
    small = region.resize(
        (max(1, w // bs), max(1, h // bs)),
        resample=_Img.Resampling.BILINEAR,
    )
    return small.resize((w, h), resample=_Img.Resampling.NEAREST)


def _ellipse_mask(w, h):
    """L-mode mask (255 inside the inscribed ellipse, 0 outside)."""
    from PIL import Image as _Img, ImageDraw
    mask = _Img.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, w - 1, h - 1), fill=255)
    return mask


def _region_mask(w, h, shape, seg_mask=None):
    """Compositing mask for the region, or ``None`` for a full-rectangle paste.

    RECT → None (paste the whole box). ELLIPSE → inscribed ellipse. PRECISE →
    the supplied per-region segmentation mask, falling back to an ellipse when
    no mask is available (segmentation model absent / failed).
    """
    if shape == SHAPE_ELLIPSE:
        return _ellipse_mask(w, h)
    if shape == SHAPE_PRECISE:
        return seg_mask if seg_mask is not None else _ellipse_mask(w, h)
    return None  # SHAPE_RECT


def _censor_region(img, x1, y1, x2, y2, block_size, style=STYLE_MOSAIC,
                   shape=SHAPE_RECT, seg_mask=None):
    """Censor a region in-place, confined to *shape*.

    The censored pixels are produced for the whole box, then composited back
    through the shape mask so only the ellipse / segmentation area is replaced
    and the rectangular corners keep their original pixels.
    """
    w = x2 - x1
    h = y2 - y1
    if w <= 0 or h <= 0:
        return
    box = (x1, y1, x2, y2)
    region = img.crop(box)
    censored = _censored_region(region, w, h, block_size, style)
    img.paste(censored, (x1, y1), _region_mask(w, h, shape, seg_mask))


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
    """EraX YOLO11 detection → list of (x1, y1, x2, y2).

    ``augment=True`` runs test-time augmentation (multi-scale + flips), which
    recovers genitalia the single-pass model scores below threshold — better
    recall for the price of a slower inference.
    """
    model = _get_anime_model()
    results = model(src, conf=confidence, iou=0.3, verbose=False, augment=True)
    boxes = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            if cls_id in classes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                boxes.append((int(x1), int(y1), int(x2), int(y2)))
    return boxes


def _get_fastsam():
    """Return a cached FastSAM model, downloading on first call."""
    global _cached_fastsam
    with _cached_fastsam_lock:
        if _cached_fastsam is None:
            from ultralytics import FastSAM
            _cached_fastsam = FastSAM(_FASTSAM_MODEL)
        return _cached_fastsam


def _fastsam_box_mask(model, src: str, box, iw: int, ih: int):
    """Segment one detection box → a full-image ``L`` mask, or None."""
    from PIL import Image as _Img
    results = model(src, bboxes=[list(box)], verbose=False, retina_masks=True)
    if not results:
        return None
    masks = getattr(results[0], "masks", None)
    if masks is None or masks.data is None or len(masks.data) == 0:
        return None
    arr = (masks.data[0].cpu().numpy() * 255).astype("uint8")
    mask = _Img.fromarray(arr, mode="L")
    if mask.size != (iw, ih):
        mask = mask.resize((iw, ih), _Img.Resampling.NEAREST)
    return mask


def _segment_boxes(src: str, boxes, mode: str):
    """Best-effort per-box full-image segmentation masks for precise mode.

    Returns a list aligned with *boxes* (each entry a mask or None), or None
    when segmentation is unavailable (no ultralytics / model download failed /
    no masks) so the caller falls back to the ellipse shape. Never raises — a
    precise run must degrade gracefully, not crash the batch.
    """
    try:
        from PIL import Image as _Img
        model = _get_fastsam()
        with _Img.open(src) as im:
            iw, ih = im.size
        masks = [_fastsam_box_mask(model, src, box, iw, ih) for box in boxes]
        return masks if any(m is not None for m in masks) else None
    except Exception:  # noqa: BLE001 — optional path, degrade to ellipse
        logger.info("Precise segmentation unavailable; using ellipse fallback",
                    exc_info=True)
        return None


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


def _ensure_parent(dst: str) -> None:
    """Create *dst*'s parent directory on demand, right before a write.

    Destination helpers only compute paths; the mirrored output tree is
    materialised here so a run that skips clean images (only-censored mode)
    never leaves empty subfolders behind.
    """
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _copy_unchanged(src: str, dst: str) -> None:
    """Copy the source verbatim when no regions were detected."""
    if os.path.normpath(src) != os.path.normpath(dst):
        import shutil
        _ensure_parent(dst)
        shutil.copy2(src, dst)


def _save_image(img, dst: str) -> None:
    _ensure_parent(dst)
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
    only_censored: bool = False,
    shape: str = SHAPE_RECT,
    merge_regions: bool = True,
) -> int:
    """Detect + censor one image.  Returns the number of regions processed.

    With *only_censored* True, an image with no detected regions is left
    entirely alone — nothing is written to *dst* — so a separate-output run
    collects only the images that were actually censored.

    *shape* confines each censor to the detected rectangle, the ellipse
    inscribed in it, or (precise) a per-region segmentation mask so the
    censor hugs the region instead of blanketing the whole box.

    *merge_regions* unions overlapping / adjacent boxes so the contact area
    between two detected regions (a penetration junction) is censored instead
    of being left in the gap between their boxes.
    """
    from PIL import Image

    boxes = _detect_boxes(detector, src, confidence, mode, categories)
    if not boxes:
        if not only_censored:
            _copy_unchanged(src, dst)
        return 0

    img = Image.open(src)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    iw, ih = img.width, img.height
    regions = [_expand_box(*box, padding, expand_pct, iw, ih) for box in boxes]
    if merge_regions and len(regions) > 1:
        regions = _merge_nearby_boxes(regions, _merge_gap(regions))
    # Precise mode segments each final region into a full-image mask; cropping
    # it to the region below keeps it pixel-aligned. None → ellipse fallback.
    seg_masks = _segment_boxes(src, regions, mode) if shape == SHAPE_PRECISE else None
    for i, region in enumerate(regions):
        seg = _crop_seg_mask(seg_masks, i, region)
        _censor_region(img, *region, block_size,
                       style=style, shape=shape, seg_mask=seg)

    _save_image(img, dst)
    return len(regions)


_MERGE_GAP_FRAC = 0.4  # merge boxes within 40% of the median box edge


def _boxes_touch(a, b, gap: int) -> bool:
    """True when box *a* grown by *gap* px overlaps box *b*."""
    return (a[0] - gap <= b[2] and b[0] <= a[2] + gap
            and a[1] - gap <= b[3] and b[1] <= a[3] + gap)


def _union_box(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _merge_gap(boxes) -> int:
    """Gap threshold for merging, scaled to the boxes' median short edge."""
    edges = [min(x2 - x1, y2 - y1) for x1, y1, x2, y2 in boxes]
    if not edges:
        return 0
    median = sorted(edges)[len(edges) // 2]
    return int(median * _MERGE_GAP_FRAC)


def _merge_nearby_boxes(boxes, gap: int):
    """Merge boxes that overlap or lie within *gap* px into their bounding
    union.

    Two detected regions in contact — e.g. a penetration junction between the
    male and female genitalia — otherwise leave the contact area itself in the
    gap between their boxes uncensored. Merging closes that gap by censoring
    the union as one region. Distant regions (different people) stay separate.
    """
    regions = [tuple(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        out: list = []
        for box in regions:
            for i, existing in enumerate(out):
                if _boxes_touch(box, existing, gap):
                    out[i] = _union_box(box, existing)
                    changed = True
                    break
            else:
                out.append(box)
        regions = out
    return regions


def _crop_seg_mask(seg_masks, index: int, box):
    """Crop the full-image segmentation mask for *index* to *box*, or None."""
    if not seg_masks:
        return None
    mask = seg_masks[index] if index < len(seg_masks) else None
    return mask.crop(box) if mask is not None else None
