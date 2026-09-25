"""Pure detection + censoring core for the safety_review plugin.

No Qt here. Heavy ML libraries (nudenet, ultralytics, huggingface_hub) and
Pillow are imported lazily inside the functions that need them so the module
imports cheaply and the dependency surface stays opt-in.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from safety_review._constants import (
    _ERAX_MODEL,
    _ERAX_REPO,
    _ERAX_REVISION,
    _IMAGE_EXTS,
    ANIME_MOSAIC_CLASSES,
    MIN_CONFIDENCE,
    MODE_ANIME,
    MODE_AUTO,
    MODE_REAL,
    SHAPE_PRECISE,
    SHAPE_RECT,
    STYLE_MOSAIC,
    _categories_to_anime_classes,
    _categories_to_real_labels,
)
from safety_review._censor_core import (
    _AnyPathDetector,
    _censor_region,
    _detect_image_mode,
    _ensure_parent,
    _expand_box,
    _junction_bridges,
    _merge_gap,
    _nudenet_corners,
    _open_upright,
    _save_as,
    _shrink_box_center,
)

logger = logging.getLogger("Imervue.plugin.safety_review")


# ---------------------------------------------------------------------------
# Cached models
# ---------------------------------------------------------------------------
_cached_detector = None
_cached_detector_lock = threading.Lock()

_cached_anime_model = None
_cached_anime_key = None          # source the cached model was loaded from
_cached_anime_lock = threading.Lock()

# user_setting_dict key holding a path to a user-supplied / fine-tuned YOLO
# ``.pt`` model to use instead of the downloaded EraX weights.
CUSTOM_MODEL_SETTING = "safety_review_custom_model"

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
            _cached_detector = _AnyPathDetector(NudeDetector())
        return _cached_detector


def _custom_model_path() -> str | None:
    """A user-supplied / fine-tuned YOLO ``.pt`` to use instead of EraX, or
    None. Read from ``user_setting_dict`` so a fine-tuned model can be dropped
    in without changing code."""
    try:
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        path = user_setting_dict.get(CUSTOM_MODEL_SETTING)
    except ImportError:   # running without Imervue's settings → use the default
        return None
    return path if path and os.path.isfile(path) else None


def _get_anime_model():
    """Return the cached YOLO model: the user's custom ``.pt`` when configured,
    otherwise the downloaded EraX weights. Reloads if the setting changes."""
    global _cached_anime_model, _cached_anime_key
    with _cached_anime_lock:
        key = _custom_model_path() or "__erax__"
        if _cached_anime_model is None or _cached_anime_key != key:
            from ultralytics import YOLO
            if key != "__erax__":
                _cached_anime_model = YOLO(key)
            else:
                from huggingface_hub import hf_hub_download
                model_path = hf_hub_download(
                    repo_id=_ERAX_REPO, filename=_ERAX_MODEL,
                    revision=_ERAX_REVISION)
                _cached_anime_model = YOLO(model_path)
            _cached_anime_key = key
        return _cached_anime_model


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _find_external_python() -> str | None:
    from Imervue.plugin.pip_installer import _find_python
    return _find_python()


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


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _detect_regions_real(detector, src: str, confidence: float,
                          labels: frozenset[str]):
    """NudeNet detection → list of (x1, y1, x2, y2); NudeNet itself reports (x, y, w, h)."""
    detections = detector.detect(src)
    boxes = []
    for d in detections:
        if d["class"] in labels and d["score"] >= confidence:
            boxes.append(_nudenet_corners(d["box"]))
    return boxes


# The scene-level (make_love) box bounds the whole scene; censor only its
# central portion (the junction sits there) so enabling it doesn't blanket the
# frame. Its class id comes from the configurable class list, so a fine-tuned
# model that renames / reorders / drops it still behaves correctly.
_MAKE_LOVE_CENTER_FRAC = 0.3


def _detect_anime_raw(src: str, confidence: float):
    """All EraX detections above *confidence* → list of ((x1,y1,x2,y2), cls).

    ``augment=True`` runs test-time augmentation (multi-scale + flips), which
    recovers genitalia the single-pass model scores below threshold — better
    recall for the price of a slower inference.
    """
    model = _get_anime_model()
    results = model(src, conf=confidence, iou=0.3, verbose=False, augment=True)
    out = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            out.append(((int(x1), int(y1), int(x2), int(y2)), int(box.cls[0])))
    return out


def _detect_regions_anime(src: str, confidence: float,
                           classes: frozenset[int] = ANIME_MOSAIC_CLASSES):
    """EraX YOLO11 detection → list of (x1, y1, x2, y2) for the requested
    *classes*.

    Only the classes the user selected are returned — no automatic dropping of
    detections. The scene-level (make_love) box, when requested, is shrunk to
    its centre so it covers the junction without blanketing the scene.
    """
    from safety_review._class_config import scene_class_id
    scene_cls = scene_class_id()
    regions = []
    for box, cls in _detect_anime_raw(src, confidence):
        if cls not in classes:
            continue
        regions.append(
            _shrink_box_center(box, _MAKE_LOVE_CENTER_FRAC)
            if cls == scene_cls else box)
    return regions


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


def _precise_backend_available() -> bool:
    """Whether the FastSAM segmentation backend can be imported.

    Precise mode only produces a real pixel mask when this is True; otherwise
    it silently falls back to the ellipse shape. The dialog checks this so it
    can tell the user up front instead of leaving them wondering why precise
    looks like an ellipse.
    """
    try:
        from ultralytics import FastSAM  # noqa: F401
        return True
    # Importing ultralytics pulls in torch, which fails in open-ended ways
    # (missing DLLs, version clashes); any failure means unavailable.
    except Exception:  # noqa: BLE001 - optional ML stack, logged below
        logger.debug("FastSAM backend unavailable", exc_info=True)
        return False


def _segment_boxes(src: str, boxes, mode: str):
    """Best-effort per-box full-image segmentation masks for precise mode.

    Returns a list aligned with *boxes* (each entry a mask or None), or None
    when segmentation is unavailable (no ultralytics / model download failed /
    no masks) so the caller falls back to the ellipse shape. Never raises — a
    precise run must degrade gracefully, not crash the batch.
    """
    try:
        model = _get_fastsam()
        with _open_upright(src) as im:   # FastSAM reads the file upright, like the detectors
            iw, ih = im.size
        masks = [_fastsam_box_mask(model, src, box, iw, ih) for box in boxes]
        if any(m is not None for m in masks):
            return masks
        logger.warning("Precise segmentation produced no masks for %s; "
                       "using ellipse fallback", src)
        return None
    except Exception:  # noqa: BLE001 — optional path, degrade to ellipse
        logger.warning("Precise segmentation unavailable; using ellipse "
                       "fallback", exc_info=True)
        return None


def _detect_boxes(detector, src, confidence, mode, categories):
    """Resolve the detection mode and return the list of boxes to censor."""
    actual_mode = mode
    if mode == MODE_AUTO:
        actual_mode = _detect_image_mode(src)
    if actual_mode == MODE_ANIME:
        # A custom / fine-tuned model may have its own (possibly new) classes,
        # so censor the configured class ids directly; the default EraX model
        # keeps the friendly category mapping.
        if _custom_model_path():
            from safety_review._class_config import censor_class_ids
            classes = censor_class_ids()
        else:
            classes = _categories_to_anime_classes(categories)
        return _detect_regions_anime(src, confidence, classes)
    real_labels = _categories_to_real_labels(categories)
    return _detect_regions_real(detector, src, confidence, real_labels)


# NudeNet label → configured class name, for labelling prefill in real mode.
_NUDENET_LABEL_TO_CLASS = {
    "MALE_GENITALIA_EXPOSED": "penis",
    "FEMALE_GENITALIA_EXPOSED": "vagina",
    "ANUS_EXPOSED": "anus",
    "FEMALE_BREAST_EXPOSED": "nipple",
}


def _detect_labeled(detector, src, confidence, mode):
    """Detect → ``[((x1,y1,x2,y2), class_id), …]`` for the manual editor's
    prefill, so drawn boxes come pre-classified for training-label export.

    Anime/YOLO gives class ids directly; NudeNet labels are mapped onto the
    configured class names. Unmapped / out-of-range detections are dropped.
    """
    from safety_review._class_config import get_classes
    classes = get_classes()
    actual = _detect_image_mode(src) if mode == MODE_AUTO else mode
    if actual == MODE_ANIME:
        return [(box, cls) for box, cls in _detect_anime_raw(src, confidence)
                if 0 <= cls < len(classes)]
    out = []
    for d in detector.detect(src):
        if d["score"] < confidence:
            continue
        name = _NUDENET_LABEL_TO_CLASS.get(d["class"])
        if name in classes:
            out.append((_nudenet_corners(d["box"]), classes.index(name)))
    return out


def _copy_unchanged(src: str, dst: str) -> None:
    """Copy the source verbatim when no regions were detected."""
    if os.path.normpath(src) != os.path.normpath(dst):
        import shutil
        _ensure_parent(dst)
        shutil.copy2(src, dst)


def _process_single_image(
    detector,
    src: str,
    dst: str,
    *, block_size: int,
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

    boxes = _detect_boxes(detector, src, confidence, mode, categories)
    if not boxes:
        if not only_censored:
            _copy_unchanged(src, dst)
        return 0

    img = _open_upright(src)

    iw, ih = img.width, img.height
    regions = [_expand_box(*box, padding, expand_pct, iw=iw, ih=ih) for box in boxes]
    # Precise mode segments each region into a full-image mask; cropping it to
    # the region below keeps it pixel-aligned. None → ellipse fallback.
    seg_masks = _segment_boxes(src, regions, mode) if shape == SHAPE_PRECISE else None
    for i, region in enumerate(regions):
        seg = _crop_seg_mask(seg_masks, i, region)
        _censor_region(img, *region, block_size,
                       style=style, shape=shape, seg_mask=seg)

    bridges = _junction_bridges(regions, _merge_gap(regions)) if merge_regions else []
    for bridge in bridges:
        # The junction bridge honours the user's chosen shape, like every other
        # censored region (precise has no mask for a bridge → ellipse fallback).
        _censor_region(img, *bridge, block_size, style=style, shape=shape)

    _save_as(img, dst)
    return len(regions) + len(bridges)


def _process_manual_image(src: str, dst: str, regions, block_size: int,
                          style: str = STYLE_MOSAIC, shape: str = SHAPE_RECT) -> int:
    """Censor a user-supplied list of *regions* on *src* and save to *dst*.

    No detection — the regions come straight from the manual editor, censored
    with the chosen style and shape. Returns the number of regions censored.
    """
    img = _open_upright(src)   # the manual editor shows the upright image
    for region in regions:
        _censor_region(img, *region, block_size, style=style, shape=shape)
    _save_as(img, dst)
    return len(regions)


def _crop_seg_mask(seg_masks, index: int, box):
    """Crop the full-image segmentation mask for *index* to *box*, or None."""
    if not seg_masks:
        return None
    mask = seg_masks[index] if index < len(seg_masks) else None
    return mask.crop(box) if mask is not None else None
