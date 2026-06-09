"""Shared constants and category mapping helpers for the safety_review plugin.

Pure data + pure functions only — no Qt, no heavy ML imports. Splitting these
out keeps the Qt UI, the worker threads and the detection core importable
without dragging the whole 2000-line module into every consumer.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Detection modes
# ---------------------------------------------------------------------------
MODE_REAL = "real"
MODE_ANIME = "anime"
MODE_AUTO = "auto"

# ---------------------------------------------------------------------------
# NudeNet labels (real-photo mode)
# ---------------------------------------------------------------------------
MOSAIC_LABELS = frozenset({
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
})

# ---------------------------------------------------------------------------
# EraX-Anti-NSFW labels (anime mode) — YOLO11 classes
# ---------------------------------------------------------------------------
# Classes: 0=anus, 1=make_love, 2=nipple, 3=penis, 4=vagina
# We mosaic: anus, penis, vagina.  Skip nipple & make_love.
ANIME_MOSAIC_CLASSES = frozenset({0, 3, 4})   # anus, penis, vagina

_ERAX_REPO = "erax-ai/EraX-Anti-NSFW-V1.1"
_ERAX_MODEL = "erax-anti-nsfw-yolo11m-v1.1.pt"   # medium — best accuracy
# Pin an explicit commit so a future repo compromise cannot silently swap the
# weights we download (bandit B615). This is the latest commit on `main` as of
# 2024-12-25; the repo ships no tags, so a full SHA is the stable anchor.
_ERAX_REVISION = "90878ab981060833413ae1a24df72f5e1fff66bc"

# ---------------------------------------------------------------------------
# Packages per mode
# ---------------------------------------------------------------------------
REQUIRED_PACKAGES_REAL = [
    ("nudenet", "nudenet"),
    ("onnxruntime", "onnxruntime"),
]
REQUIRED_PACKAGES_ANIME = [
    ("ultralytics", "ultralytics"),
    ("huggingface_hub", "huggingface_hub"),
]
REQUIRED_PACKAGES_AUTO = REQUIRED_PACKAGES_REAL + [
    p for p in REQUIRED_PACKAGES_ANIME if p not in REQUIRED_PACKAGES_REAL
]

DEFAULT_BLOCK_SIZE = 4   # mosaic granularity — 4 px

# Per-mode defaults
# padding = fixed pixels, expand_pct = expand box by % of its own size
_MODE_DEFAULTS: dict[str, dict] = {
    MODE_REAL:  {"confidence": 0.25, "padding": 10, "expand_pct": 0},
    MODE_ANIME: {"confidence": 0.20, "padding": 0,  "expand_pct": 0},
    MODE_AUTO:  {"confidence": 0.25, "padding": 10, "expand_pct": 0},
}

DEFAULT_PADDING = 10
DEFAULT_EXPAND_PCT = 0     # 0 = use fixed padding only
MIN_CONFIDENCE = 0.25

# ---------------------------------------------------------------------------
# Censoring styles
# ---------------------------------------------------------------------------
STYLE_MOSAIC = "mosaic"
STYLE_BLUR = "blur"
STYLE_BLACK = "black"

# ---------------------------------------------------------------------------
# Abstract detection categories → per-mode labels / class IDs
# ---------------------------------------------------------------------------
CAT_GENITALIA = "genitalia"
CAT_ANUS = "anus"
CAT_NIPPLE = "nipple"
CAT_SEXUAL_ACT = "sexual_act"

ALL_CATEGORIES = (CAT_GENITALIA, CAT_ANUS, CAT_NIPPLE, CAT_SEXUAL_ACT)
DEFAULT_CATEGORIES = frozenset({CAT_GENITALIA, CAT_ANUS})

_CAT_TO_REAL_LABELS: dict[str, frozenset[str]] = {
    CAT_GENITALIA: frozenset({"FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED"}),
    CAT_ANUS: frozenset({"ANUS_EXPOSED"}),
    CAT_NIPPLE: frozenset({"FEMALE_BREAST_EXPOSED"}),
    CAT_SEXUAL_ACT: frozenset(),  # NudeNet has no "sexual act" label
}

_CAT_TO_ANIME_CLASSES: dict[str, frozenset[int]] = {
    CAT_GENITALIA: frozenset({3, 4}),   # penis, vagina
    CAT_ANUS: frozenset({0}),
    CAT_NIPPLE: frozenset({2}),
    CAT_SEXUAL_ACT: frozenset({1}),     # make_love
}

# Supported image extensions for folder scanning
_IMAGE_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp",
    ".gif", ".apng",
})

# Output format → Pillow format name (allocated once, reused)
_FMT_MAP = {
    ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
    ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
    ".webp": "WEBP",
}


def _categories_to_real_labels(categories) -> frozenset[str]:
    """Convert abstract category set → NudeNet label set."""
    if categories is None:
        categories = DEFAULT_CATEGORIES
    labels: set[str] = set()
    for cat in categories:
        labels |= _CAT_TO_REAL_LABELS.get(cat, frozenset())
    return frozenset(labels)


def _categories_to_anime_classes(categories) -> frozenset[int]:
    """Convert abstract category set → EraX YOLO class-ID set."""
    if categories is None:
        categories = DEFAULT_CATEGORIES
    classes: set[int] = set()
    for cat in categories:
        classes |= _CAT_TO_ANIME_CLASSES.get(cat, frozenset())
    return frozenset(classes)
