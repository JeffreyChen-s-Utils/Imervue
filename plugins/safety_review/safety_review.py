"""
Safety Review — auto-detect and mosaic exposed genitalia.

Uses NudeNet to detect NSFW regions.  Only genitalia (male & female)
and anus are mosaiced; **nipples / breasts are never touched**.

Workflows
---------
* **Scan All** — one click to process every image in the current folder,
  overwriting originals.  A progress dialog tracks completion.
* **Single Quick Apply** — right-click in deep-zoom → applies to the
  current image immediately.
* **Batch (selected)** — tile-grid selection → batch dialog with output
  options.

Dependencies (auto-installed on first use):
  - nudenet
  - onnxruntime
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.pip_installer import ensure_dependencies
from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.system.app_paths import (
    frozen_site_packages as _frozen_site_packages,
    is_frozen as _is_frozen,
)

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.plugin.safety_review")

_PLUGIN_DIR = Path(__file__).resolve().parent
_RUNNER_SCRIPT = _PLUGIN_DIR / "_runner.py"

# ---------------------------------------------------------------------------
# Detection modes
# ---------------------------------------------------------------------------
MODE_REAL = "real"
MODE_ANIME = "anime"

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
# Auto-detect mode
# ---------------------------------------------------------------------------
MODE_AUTO = "auto"

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import threading as _threading

# Cached NudeNet detector (real-photo mode)
_cached_detector = None
_cached_detector_lock = _threading.Lock()


def _get_detector():
    """Return a cached NudeDetector, creating it on first call."""
    global _cached_detector
    with _cached_detector_lock:
        if _cached_detector is None:
            from nudenet import NudeDetector
            _cached_detector = NudeDetector()
        return _cached_detector


# Cached EraX YOLO model (anime mode)
_cached_anime_model = None
_cached_anime_lock = _threading.Lock()


def _get_anime_model():
    """Return a cached EraX YOLO model, downloading on first call."""
    global _cached_anime_model
    with _cached_anime_lock:
        if _cached_anime_model is None:
            from huggingface_hub import hf_hub_download
            from ultralytics import YOLO
            model_path = hf_hub_download(
                repo_id=_ERAX_REPO, filename=_ERAX_MODEL)
            _cached_anime_model = YOLO(model_path)
        return _cached_anime_model


def _detect_image_mode(src: str) -> str:
    """Heuristic: anime/illustration images have fewer unique quantized colors."""
    from PIL import Image
    img = Image.open(src).convert("RGB")
    img = img.resize((128, 128), Image.Resampling.BILINEAR)
    quantized = set()
    for r, g, b in img.getdata():
        quantized.add((r >> 3, g >> 3, b >> 3))
    return MODE_ANIME if len(quantized) < 1500 else MODE_REAL


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


# Format → extension mapping (allocated once, reused)
_FMT_MAP = {
    ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
    ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
    ".webp": "WEBP",
}


def _censor_region(img, x1, y1, x2, y2, block_size,
                   style=STYLE_MOSAIC, _bilinear=None, _nearest=None):
    """Apply censoring (mosaic / blur / black) to a region (in-place)."""
    w = x2 - x1
    h = y2 - y1
    if w <= 0 or h <= 0:
        return
    if style == STYLE_BLACK:
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle((x1, y1, x2, y2), fill=(0, 0, 0))
    elif style == STYLE_BLUR:
        from PIL import ImageFilter
        region = img.crop((x1, y1, x2, y2))
        radius = max(max(w, h) // 5, 10)
        blurred = region.filter(ImageFilter.GaussianBlur(radius=radius))
        img.paste(blurred, (x1, y1))
    else:  # mosaic (default)
        if _bilinear is None:
            from PIL import Image as _Img
            _censor_region.__defaults__ = (
                STYLE_MOSAIC,
                _Img.Resampling.BILINEAR, _Img.Resampling.NEAREST,
            )
            _bilinear = _censor_region.__defaults__[1]
            _nearest = _censor_region.__defaults__[2]
        region = img.crop((x1, y1, x2, y2))
        bs = max(2, block_size)
        small = region.resize(
            (max(1, w // bs), max(1, h // bs)), resample=_bilinear,
        )
        mosaic = small.resize((w, h), resample=_nearest)
        img.paste(mosaic, (x1, y1))


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

    actual_mode = mode
    if mode == MODE_AUTO:
        actual_mode = _detect_image_mode(src)

    if actual_mode == MODE_ANIME:
        classes = _categories_to_anime_classes(categories)
        boxes = _detect_regions_anime(src, confidence, classes)
    else:
        real_labels = _categories_to_real_labels(categories)
        boxes = _detect_regions_real(detector, src, confidence, real_labels)

    if not boxes:
        if os.path.normpath(src) != os.path.normpath(dst):
            import shutil
            shutil.copy2(src, dst)
        return 0

    img = Image.open(src)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    iw, ih = img.width, img.height
    for x1, y1, x2, y2 in boxes:
        x1, y1, x2, y2 = _expand_box(x1, y1, x2, y2, padding, expand_pct,
                                       iw, ih)
        _censor_region(img, x1, y1, x2, y2, block_size, style=style)

    fmt = _FMT_MAP.get(Path(dst).suffix.lower(), "PNG")
    if fmt == "JPEG" and img.mode == "RGBA":
        img = img.convert("RGB")
    img.save(dst, format=fmt)
    return len(boxes)


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class _SingleWorker(QThread):
    """In-process: detect + mosaic a single image."""
    # (step 0-3, step_text)
    progress = Signal(int, str)
    result_ready = Signal(bool, str, int)  # (ok, path_or_error, regions_count)

    STEPS = 3  # load model, detect, save

    def __init__(self, input_path: str, output_path: str,
                 block_size: int, padding: int,
                 mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None):
        super().__init__()
        self._input = input_path
        self._output = output_path
        self._bs = block_size
        self._pad = padding
        self._mode = mode
        self._conf = confidence
        self._expand_pct = expand_pct
        self._style = style
        self._categories = categories

    def run(self):
        try:
            self.progress.emit(0, "Loading model...")
            if self._mode == MODE_AUTO:
                _get_detector()  # pre-load both
                _get_anime_model()
                detector = _get_detector()
            elif self._mode == MODE_ANIME:
                detector = None
            else:
                detector = _get_detector()
            self.progress.emit(1, "Detecting regions...")
            count = _process_single_image(
                detector, self._input, self._output, self._bs, self._pad,
                confidence=self._conf,
                expand_pct=self._expand_pct, mode=self._mode,
                style=self._style, categories=self._categories,
            )
            self.progress.emit(2, "Saving...")
            self.progress.emit(3, "Done")
            self.result_ready.emit(True, self._output, count)
        except Exception as exc:
            logger.error("Single safety review failed: %s", exc, exc_info=True)
            self.result_ready.emit(False, str(exc), 0)


class _BatchWorker(QThread):
    """In-process: detect + mosaic a list of images."""
    # (current_idx, total, filename, elapsed_sec, eta_sec)
    progress = Signal(int, int, str, float, float)
    result_ready = Signal(int, int, int)   # (success, failed, total_regions)

    def __init__(self, paths: list[str], output_dir: str | None,
                 block_size: int, padding: int, overwrite: bool,
                 mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None):
        super().__init__()
        self._paths = paths
        self._output_dir = output_dir
        self._bs = block_size
        self._pad = padding
        self._overwrite = overwrite
        self._mode = mode
        self._conf = confidence
        self._expand_pct = expand_pct
        self._style = style
        self._categories = categories

    def run(self):
        import time

        if self._mode == MODE_AUTO:
            detector = _get_detector()
            _get_anime_model()
        elif self._mode == MODE_ANIME:
            detector = None
        else:
            detector = _get_detector()
        success = 0
        failed = 0
        total_regions = 0
        total = len(self._paths)
        t0 = time.monotonic()

        for i, src in enumerate(self._paths):
            name = Path(src).name
            elapsed = time.monotonic() - t0
            if i > 0:
                eta = elapsed / i * (total - i)
            else:
                eta = 0.0
            self.progress.emit(i, total, name, elapsed, eta)
            try:
                if self._overwrite:
                    dst = src
                else:
                    stem = Path(src).stem
                    suffix = Path(src).suffix or ".png"
                    dst = str(Path(self._output_dir) / f"{stem}_censored{suffix}")
                    counter = 1
                    while os.path.exists(dst):
                        dst = str(
                            Path(self._output_dir)
                            / f"{stem}_censored_{counter}{suffix}"
                        )
                        counter += 1

                count = _process_single_image(
                    detector, src, dst, self._bs, self._pad,
                    confidence=self._conf,
                    expand_pct=self._expand_pct, mode=self._mode,
                    style=self._style, categories=self._categories,
                )
                total_regions += count
                success += 1
            except Exception as exc:
                logger.error("Batch safety review failed for %s: %s", src, exc)
                failed += 1

        self.result_ready.emit(success, failed, total_regions)


class _SubprocessSingleWorker(QThread):
    """Frozen-env: run detector in an external Python process."""
    progress = Signal(str)
    result_ready = Signal(bool, str, int)

    def __init__(self, python: str, site_packages: str,
                 input_path: str, output_path: str,
                 block_size: int, padding: int,
                 mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None):
        super().__init__()
        self._python = python
        self._sp = site_packages
        self._input = input_path
        self._output = output_path
        self._bs = block_size
        self._pad = padding
        self._mode = mode
        self._conf = confidence
        self._expand_pct = expand_pct
        self._style = style
        self._categories = categories

    def run(self):
        try:
            cats_str = ",".join(sorted(self._categories)) if self._categories else ""
            cmd = [
                self._python, str(_RUNNER_SCRIPT),
                self._sp, "single",
                self._input, self._output,
                str(self._bs), str(self._pad),
                self._mode, str(self._conf),
                str(self._expand_pct),
                self._style, cats_str,
            ]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                **_subprocess_kwargs(),
            )
            for line in proc.stdout:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                if line.startswith("PROGRESS:"):
                    self.progress.emit(line[9:])
                elif line.startswith("OK:"):
                    self.result_ready.emit(True, line[3:], -1)
                    proc.wait()
                    return
                elif line.startswith("ERROR:"):
                    self.result_ready.emit(False, line[6:], 0)
                    proc.wait()
                    return
            proc.wait()
            if proc.returncode != 0:
                self.result_ready.emit(
                    False, f"Process exited with code {proc.returncode}", 0)
            else:
                self.result_ready.emit(True, self._output, -1)
        except Exception as exc:
            logger.error("Subprocess single worker failed: %s", exc, exc_info=True)
            self.result_ready.emit(False, str(exc), 0)


class _SubprocessBatchWorker(QThread):
    """Frozen-env: batch detect in external Python."""
    progress = Signal(int, int, str)
    result_ready = Signal(int, int, int)

    def __init__(self, python: str, site_packages: str,
                 paths: list[str], output_dir: str | None,
                 block_size: int, padding: int, overwrite: bool,
                 mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None):
        super().__init__()
        self._python = python
        self._sp = site_packages
        self._paths = paths
        self._output_dir = output_dir or ""
        self._bs = block_size
        self._pad = padding
        self._overwrite = overwrite
        self._mode = mode
        self._conf = confidence
        self._expand_pct = expand_pct
        self._style = style
        self._categories = categories

    def run(self):
        tmp_path = None
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8",
            )
            tmp_path = tmp.name
            json.dump(self._paths, tmp)
            tmp.close()

            cats_str = ",".join(sorted(self._categories)) if self._categories else ""
            cmd = [
                self._python, str(_RUNNER_SCRIPT),
                self._sp, "batch",
                tmp_path, self._output_dir,
                str(self._bs), str(self._pad),
                str(self._overwrite),
                self._mode, str(self._conf),
                str(self._expand_pct),
                self._style, cats_str,
            ]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                **_subprocess_kwargs(),
            )
            for line in proc.stdout:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                if line.startswith("BATCH_PROGRESS:"):
                    # Protocol: BATCH_PROGRESS:<int>:<int>:<filename>
                    # Use maxsplit=2 so colons in filename are preserved.
                    parts = line[15:].split(":", 2)
                    if len(parts) == 3:
                        try:
                            self.progress.emit(
                                int(parts[0]), int(parts[1]), parts[2])
                        except (ValueError, RuntimeError):
                            pass
                elif line.startswith("BATCH_OK:"):
                    parts = line[9:].split(":", 1)
                    try:
                        s, f = int(parts[0]), int(parts[1])
                    except (ValueError, IndexError):
                        s, f = 0, len(self._paths)
                    self.result_ready.emit(s, f, -1)
                    proc.wait()
                    return
                elif line.startswith("ERROR:"):
                    self.result_ready.emit(0, len(self._paths), 0)
                    proc.wait()
                    return

            proc.wait()
            self.result_ready.emit(0, len(self._paths), 0)
        except Exception as exc:
            logger.error("Subprocess batch worker failed: %s", exc, exc_info=True)
            self.result_ready.emit(0, len(self._paths), 0)
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# Shared UI helper
# ---------------------------------------------------------------------------

def _build_mode_row(layout, lang):
    """Add detection-mode combo, style combo, confidence, expand%,
    and category checkboxes to *layout*.

    Returns (mode_combo, conf_spin, expand_spin, style_combo, cat_checks).
    ``cat_checks`` is a dict  {category_name: QCheckBox}.
    """
    # -- Detection mode --
    mode_row = QHBoxLayout()
    mode_row.addWidget(QLabel(
        lang.get("safety_review_mode", "Detection mode:")
    ))
    mode_combo = QComboBox()
    mode_combo.addItem(
        lang.get("safety_review_mode_auto", "Auto"), MODE_AUTO)
    mode_combo.addItem(
        lang.get("safety_review_mode_real", "Real Photo"), MODE_REAL)
    mode_combo.addItem(
        lang.get("safety_review_mode_anime", "Anime / Illustration"), MODE_ANIME)
    mode_row.addWidget(mode_combo, 1)
    layout.addLayout(mode_row)

    # -- Censor style --
    style_row = QHBoxLayout()
    style_row.addWidget(QLabel(
        lang.get("safety_review_style", "Censor style:")
    ))
    style_combo = QComboBox()
    style_combo.addItem(
        lang.get("safety_review_style_mosaic", "Mosaic"), STYLE_MOSAIC)
    style_combo.addItem(
        lang.get("safety_review_style_blur", "Gaussian Blur"), STYLE_BLUR)
    style_combo.addItem(
        lang.get("safety_review_style_black", "Black Bar"), STYLE_BLACK)
    style_row.addWidget(style_combo, 1)
    layout.addLayout(style_row)

    # -- Confidence --
    conf_row = QHBoxLayout()
    conf_row.addWidget(QLabel(
        lang.get("safety_review_confidence", "Min confidence:")
    ))
    conf_spin = QDoubleSpinBox()
    conf_spin.setRange(0.01, 1.0)
    conf_spin.setSingleStep(0.05)
    conf_spin.setDecimals(2)
    conf_spin.setValue(_MODE_DEFAULTS[MODE_AUTO]["confidence"])
    conf_row.addWidget(conf_spin)
    layout.addLayout(conf_row)

    # -- Expand % --
    expand_row = QHBoxLayout()
    expand_row.addWidget(QLabel(
        lang.get("safety_review_expand_pct",
                  "Expand detection box (%):")
    ))
    expand_spin = QSpinBox()
    expand_spin.setRange(0, 200)
    expand_spin.setSingleStep(10)
    expand_spin.setValue(_MODE_DEFAULTS[MODE_AUTO]["expand_pct"])
    expand_spin.setSuffix("%")
    expand_row.addWidget(expand_spin)
    layout.addLayout(expand_row)

    # -- Category checkboxes --
    cat_label = QLabel(
        lang.get("safety_review_categories", "Detection categories:"))
    layout.addWidget(cat_label)

    _cat_display = {
        CAT_GENITALIA: lang.get("safety_review_cat_genitalia",
                                "Genitalia (penis / vagina)"),
        CAT_ANUS: lang.get("safety_review_cat_anus", "Anus"),
        CAT_NIPPLE: lang.get("safety_review_cat_nipple", "Nipple / Breast"),
        CAT_SEXUAL_ACT: lang.get("safety_review_cat_sexual_act",
                                  "Sexual Act (anime only)"),
    }
    cat_checks: dict[str, QCheckBox] = {}
    cat_row = QHBoxLayout()
    for cat in ALL_CATEGORIES:
        cb = QCheckBox(_cat_display[cat])
        cb.setChecked(cat in DEFAULT_CATEGORIES)
        cat_checks[cat] = cb
        cat_row.addWidget(cb)
    layout.addLayout(cat_row)

    def _on_mode_changed(index):
        mode = mode_combo.itemData(index)
        defaults = _MODE_DEFAULTS.get(mode, _MODE_DEFAULTS[MODE_REAL])
        conf_spin.setValue(defaults["confidence"])
        expand_spin.setValue(defaults["expand_pct"])
        # Sexual-act checkbox only relevant for anime / auto
        sa_cb = cat_checks[CAT_SEXUAL_ACT]
        sa_cb.setEnabled(mode != MODE_REAL)
        if mode == MODE_REAL:
            sa_cb.setChecked(False)

    mode_combo.currentIndexChanged.connect(_on_mode_changed)
    # Trigger initial state
    _on_mode_changed(mode_combo.currentIndex())

    return mode_combo, conf_spin, expand_spin, style_combo, cat_checks


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

# Supported image extensions for folder scanning
_IMAGE_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp",
    ".gif", ".apng",
})


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


class ScanAllDialog(QDialog):
    """Scan folder dialog — user picks a folder, configures mode, then starts."""

    def __init__(self, main_gui: GPUImageView,
                 initial_paths: list[str] | None = None,
                 block_size: int = DEFAULT_BLOCK_SIZE,
                 padding: int = DEFAULT_PADDING,
                 get_frozen_env=None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths: list[str] = initial_paths or []
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._get_frozen_env = get_frozen_env
        self._block_size = block_size
        self._padding = padding
        self._finished = False

        self.setWindowTitle(
            self._lang.get("safety_review_scan_all_title",
                           "Safety Review — Scan All")
        )
        self.setMinimumWidth(500)
        self._build_ui()

        # If initial paths provided, infer folder and update count
        if self._paths:
            folder = str(Path(self._paths[0]).parent)
            self._folder_edit.setText(folder)
            self._update_count()

    # ---- UI ----

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Source folder
        folder_lbl = QLabel(
            self._lang.get("safety_review_scan_folder",
                           "Source folder:"))
        layout.addWidget(folder_lbl)

        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText(
            self._lang.get("safety_review_scan_folder_hint",
                           "Choose a folder containing images..."))
        self._browse_folder_btn = QPushButton(
            self._lang.get("export_browse", "Browse..."))
        self._browse_folder_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._folder_edit, 1)
        folder_row.addWidget(self._browse_folder_btn)
        layout.addLayout(folder_row)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

        # Overwrite vs output folder
        self._overwrite_check = QCheckBox(
            self._lang.get("safety_review_overwrite",
                           "Overwrite original files (no backup!)"))
        self._overwrite_check.setChecked(True)
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self._overwrite_check)

        self._out_dir_label = QLabel(
            self._lang.get("safety_review_output_dir", "Output folder:"))
        self._out_dir_label.setVisible(False)
        layout.addWidget(self._out_dir_label)

        out_row = QHBoxLayout()
        self._out_dir_edit = QLineEdit()
        self._out_dir_edit.setVisible(False)
        self._out_browse_btn = QPushButton(
            self._lang.get("export_browse", "Browse..."))
        self._out_browse_btn.setVisible(False)
        self._out_browse_btn.clicked.connect(self._browse_out_dir)
        out_row.addWidget(self._out_dir_edit, 1)
        out_row.addWidget(self._out_browse_btn)
        layout.addLayout(out_row)

        # Mode + style + confidence + categories
        (self._mode_combo, self._conf_spin, self._expand_spin,
         self._style_combo, self._cat_checks) = _build_mode_row(
            layout, self._lang)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # Progress
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setFormat("%v / %m  (%p%)")
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        self._time_label = QLabel("")
        layout.addWidget(self._time_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton(
            self._lang.get("export_cancel", "Cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        self._start_btn = QPushButton(
            self._lang.get("safety_review_start", "Start"))
        self._start_btn.clicked.connect(self._start)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._start_btn)
        layout.addLayout(btn_row)

    # ---- Folder picking ----

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            self._lang.get("safety_review_scan_folder", "Source folder"),
        )
        if folder:
            self._folder_edit.setText(folder)
            self._paths = _scan_folder(folder)
            self._update_count()
            # Pre-fill output dir
            if not self._out_dir_edit.text():
                self._out_dir_edit.setText(folder)

    def _browse_out_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            self._lang.get("safety_review_output_dir", "Output folder"),
        )
        if folder:
            self._out_dir_edit.setText(folder)

    def _update_count(self):
        count = len(self._paths)
        self._count_label.setText(
            self._lang.get(
                "safety_review_scan_all_info",
                "Scanning {count} images — genitalia will be mosaiced, "
                "nipples will NOT be touched.",
            ).format(count=count)
        )
        self._start_btn.setEnabled(count > 0)

    def _on_overwrite_toggled(self, checked):
        self._out_dir_label.setVisible(not checked)
        self._out_dir_edit.setVisible(not checked)
        self._out_browse_btn.setVisible(not checked)

    def _on_mode_changed(self, index):
        mode = self._mode_combo.itemData(index)
        defaults = _MODE_DEFAULTS.get(mode, _MODE_DEFAULTS[MODE_REAL])
        self._padding = defaults["padding"]

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        s = int(seconds)
        if s < 60:
            return f"{s}s"
        m, s = divmod(s, 60)
        if m < 60:
            return f"{m}m {s:02d}s"
        h, m = divmod(m, 60)
        return f"{h}h {m:02d}m {s:02d}s"

    def _start(self):
        if not self._paths:
            return

        overwrite = self._overwrite_check.isChecked()
        output_dir = None if overwrite else self._out_dir_edit.text().strip()
        if not overwrite and (not output_dir or not Path(output_dir).is_dir()):
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        mode = self._mode_combo.currentData()
        conf = self._conf_spin.value()
        expand = self._expand_spin.value()
        style = self._style_combo.currentData()
        categories = frozenset(
            cat for cat, cb in self._cat_checks.items() if cb.isChecked()
        )

        self._start_btn.setEnabled(False)
        self._browse_folder_btn.setEnabled(False)
        self._mode_combo.setEnabled(False)
        self._conf_spin.setEnabled(False)
        self._expand_spin.setEnabled(False)
        self._style_combo.setEnabled(False)
        self._overwrite_check.setEnabled(False)
        for cb in self._cat_checks.values():
            cb.setEnabled(False)

        self._status_label.setText(
            self._lang.get("safety_review_installing",
                           "Installing dependencies..."))

        def _on_deps_ready():
            self._progress.setMaximum(len(self._paths))
            self._progress.setVisible(True)
            self._status_label.setText("")

            frozen_env = self._get_frozen_env() if self._get_frozen_env else None
            if frozen_env:
                python, sp = frozen_env
                self._worker = _SubprocessBatchWorker(
                    python, sp, self._paths, output_dir,
                    self._block_size, self._padding, overwrite=overwrite,
                    mode=mode, confidence=conf, expand_pct=expand,
                    style=style, categories=categories,
                )
            else:
                self._worker = _BatchWorker(
                    self._paths, output_dir,
                    self._block_size, self._padding, overwrite=overwrite,
                    mode=mode, confidence=conf, expand_pct=expand,
                    style=style, categories=categories,
                )
            self._worker.progress.connect(self._on_progress)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        _ensure_deps(self._gui.main_window, _on_deps_ready, mode=mode)

    def _on_progress(self, current, total, name, *time_args):
        self._progress.setValue(current)
        self._status_label.setText(f"{current + 1}/{total}  {name}")
        # time_args = (elapsed, eta) from _BatchWorker; empty from subprocess
        if len(time_args) >= 2:
            elapsed, eta = time_args[0], time_args[1]
            elapsed_str = self._fmt_time(elapsed)
            eta_str = self._fmt_time(eta) if current > 0 else "..."
            self._time_label.setText(
                self._lang.get(
                    "safety_review_time",
                    "Elapsed: {elapsed}    ETA: {eta}    (~{speed:.1f}s / image)",
                ).format(
                    elapsed=elapsed_str,
                    eta=eta_str,
                    speed=elapsed / max(current, 1),
                )
            )

    def _cleanup(self):
        self._worker = None

    def _on_finished(self, success, failed, total_regions):
        self._finished = True
        self._progress.setValue(len(self._paths))

        if total_regions >= 0:
            msg = self._lang.get(
                "safety_review_scan_all_done",
                "Done — {success}/{total} images processed, "
                "{regions} region(s) mosaiced, {failed} failed.",
            ).format(
                success=success,
                total=success + failed,
                regions=total_regions,
                failed=failed,
            )
        else:
            msg = self._lang.get(
                "safety_review_batch_done",
                "Processed {success}/{total} image(s)",
            ).format(success=success, total=success + failed)

        self._status_label.setText(msg)
        self._time_label.setText("")
        self._cancel_btn.setText(self._lang.get("safety_review_close", "Close"))
        self._start_btn.setVisible(False)

        if hasattr(self._gui.main_window, "toast"):
            if failed:
                self._gui.main_window.toast.info(msg)
            else:
                self._gui.main_window.toast.success(msg)

        # Reload viewer only when files were overwritten in-place
        if self._overwrite_check.isChecked():
            self._reload_viewer()

    def _reload_viewer(self):
        """Refresh tile grid or deep-zoom after overwriting files."""
        try:
            if self._gui.tile_grid_mode:
                self._gui.load_tile_grid_async(list(self._gui.model.images))
            elif self._gui.deep_zoom:
                images = self._gui.model.images
                if images and 0 <= self._gui.current_index < len(images):
                    path = images[self._gui.current_index]
                    self._gui._clear_deep_zoom()
                    self._gui.load_deep_zoom_image(path)
        except Exception:
            logger.debug("Viewer reload after scan-all failed", exc_info=True)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            try:
                self._worker.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


class SafetyReviewDialog(QDialog):
    """Single-image dialog with settings."""

    def __init__(self, main_gui: GPUImageView, image_path: str,
                 get_frozen_env=None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._image_path = image_path
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._get_frozen_env = get_frozen_env

        self.setWindowTitle(
            self._lang.get("safety_review_title", "Safety Review — Auto Mosaic")
        )
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            self._lang.get("safety_review_source", "Source:")
            + f"  {Path(self._image_path).name}"
        ))
        info = QLabel(self._lang.get(
            "safety_review_info",
            "Detects and mosaics exposed genitalia (male & female). "
            "Nipples are NOT mosaiced.",
        ))
        info.setWordWrap(True)
        layout.addWidget(info)

        # Mode + style + confidence + categories
        (self._mode_combo, self._conf_spin, self._expand_spin,
         self._style_combo, self._cat_checks) = _build_mode_row(
            layout, self._lang)
        self._mode_combo.currentIndexChanged.connect(
            self._on_mode_changed_single)

        # Block size
        bs_row = QHBoxLayout()
        bs_row.addWidget(QLabel(
            self._lang.get("safety_review_block_size", "Mosaic block size (px):")
        ))
        self._block_spin = QSpinBox()
        self._block_spin.setRange(2, 64)
        self._block_spin.setValue(DEFAULT_BLOCK_SIZE)
        bs_row.addWidget(self._block_spin)
        layout.addLayout(bs_row)

        # Padding
        pad_row = QHBoxLayout()
        pad_row.addWidget(QLabel(
            self._lang.get("safety_review_padding", "Padding around region (px):")
        ))
        self._padding_spin = QSpinBox()
        self._padding_spin.setRange(0, 200)
        self._padding_spin.setValue(DEFAULT_PADDING)
        pad_row.addWidget(self._padding_spin)
        layout.addLayout(pad_row)

        # Output
        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        stem = Path(self._image_path).stem
        suffix = Path(self._image_path).suffix
        default_out = Path(self._image_path).parent / f"{stem}_censored{suffix}"
        self._path_edit.setText(str(default_out))
        browse_btn = QPushButton(self._lang.get("export_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Overwrite shortcut
        self._overwrite_check = QCheckBox(
            self._lang.get(
                "safety_review_overwrite_single",
                "Overwrite original file",
            )
        )
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self._overwrite_check)

        # Progress — 3 steps: load model → detect → save
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, _SingleWorker.STEPS)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("%v / %m")
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._run_btn = QPushButton(
            self._lang.get("safety_review_run", "Apply Mosaic")
        )
        self._run_btn.clicked.connect(self._do_run)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._run_btn)
        layout.addLayout(btn_row)

    def _on_mode_changed_single(self, index):
        mode = self._mode_combo.itemData(index)
        defaults = _MODE_DEFAULTS.get(mode, _MODE_DEFAULTS[MODE_REAL])
        self._padding_spin.setValue(defaults["padding"])

    def _on_overwrite_toggled(self, checked):
        if checked:
            self._path_edit.setText(self._image_path)
        self._path_edit.setEnabled(not checked)

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self._lang.get("export_save", "Save"),
            self._path_edit.text(),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)",
        )
        if path:
            self._path_edit.setText(path)

    def _do_run(self):
        output = self._path_edit.text().strip()
        if not output:
            return

        self._run_btn.setEnabled(False)
        self._status_label.setText(
            self._lang.get("safety_review_installing",
                           "Installing dependencies..."))

        bs = self._block_spin.value()
        pad = self._padding_spin.value()
        mode = self._mode_combo.currentData()
        conf = self._conf_spin.value()
        expand = self._expand_spin.value()
        style = self._style_combo.currentData()
        categories = frozenset(
            cat for cat, cb in self._cat_checks.items() if cb.isChecked()
        )

        def _on_deps_ready():
            self._progress_bar.setVisible(True)
            self._status_label.setText("")

            frozen_env = self._get_frozen_env() if self._get_frozen_env else None
            if frozen_env:
                python, sp = frozen_env
                self._worker = _SubprocessSingleWorker(
                    python, sp, self._image_path, output, bs, pad,
                    mode=mode, confidence=conf, expand_pct=expand,
                    style=style, categories=categories,
                )
                self._worker.progress.connect(self._on_progress_text)
            else:
                self._worker = _SingleWorker(
                    self._image_path, output, bs, pad,
                    mode=mode, confidence=conf, expand_pct=expand,
                    style=style, categories=categories,
                )
                self._worker.progress.connect(self._on_progress_step)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        _ensure_deps(self._gui.main_window, _on_deps_ready, mode=mode)

    def _on_progress_step(self, step: int, msg: str):
        """From _SingleWorker (int, str)."""
        self._progress_bar.setValue(step)
        self._status_label.setText(msg)

    def _on_progress_text(self, msg: str):
        """From _SubprocessSingleWorker (str only)."""
        self._status_label.setText(msg)

    def _cleanup(self):
        self._worker = None

    def _on_finished(self, ok: bool, result: str, count: int):
        self._progress_bar.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            if count == 0:
                text = self._lang.get(
                    "safety_review_nothing",
                    "No genitalia detected — image unchanged.",
                )
            else:
                text = self._lang.get(
                    "safety_review_done", "Done! Saved to: {path}"
                ).format(path=result)
            self._status_label.setText(text)
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.success(
                    self._lang.get("safety_review_done_short", "Mosaic applied!")
                    if count else text
                )
            # Reload the current image in viewer if it was overwritten
            if self._overwrite_check.isChecked():
                self._reload_viewer()
            QTimer.singleShot(500, self.accept)
        else:
            self._status_label.setText(f"Error: {result}")
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.info(f"Error: {result}")

    def _reload_viewer(self):
        try:
            images = self._gui.model.images
            if images and 0 <= self._gui.current_index < len(images):
                path = images[self._gui.current_index]
                self._gui._clear_deep_zoom()
                self._gui.load_deep_zoom_image(path)
        except Exception:
            logger.debug("Viewer reload after single review failed", exc_info=True)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            try:
                self._worker.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


class BatchSafetyReviewDialog(QDialog):
    """Batch dialog — selected images, choose overwrite or separate output."""

    def __init__(self, main_gui: GPUImageView, paths: list[str],
                 get_frozen_env=None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths = paths
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._get_frozen_env = get_frozen_env

        self.setWindowTitle(
            self._lang.get("safety_review_batch_title", "Batch Safety Review")
        )
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            self._lang.get(
                "batch_export_count", "{count} image(s) selected"
            ).format(count=len(self._paths))
        ))

        info = QLabel(self._lang.get(
            "safety_review_info",
            "Detects and mosaics exposed genitalia (male & female). "
            "Nipples are NOT mosaiced.",
        ))
        info.setWordWrap(True)
        layout.addWidget(info)

        # Mode + style + confidence + categories
        (self._mode_combo, self._conf_spin, self._expand_spin,
         self._style_combo, self._cat_checks) = _build_mode_row(
            layout, self._lang)
        self._mode_combo.currentIndexChanged.connect(
            self._on_mode_changed_batch)

        # Block size
        bs_row = QHBoxLayout()
        bs_row.addWidget(QLabel(
            self._lang.get("safety_review_block_size", "Mosaic block size (px):")
        ))
        self._block_spin = QSpinBox()
        self._block_spin.setRange(2, 64)
        self._block_spin.setValue(DEFAULT_BLOCK_SIZE)
        bs_row.addWidget(self._block_spin)
        layout.addLayout(bs_row)

        # Padding
        pad_row = QHBoxLayout()
        pad_row.addWidget(QLabel(
            self._lang.get("safety_review_padding", "Padding around region (px):")
        ))
        self._padding_spin = QSpinBox()
        self._padding_spin.setRange(0, 200)
        self._padding_spin.setValue(DEFAULT_PADDING)
        pad_row.addWidget(self._padding_spin)
        layout.addLayout(pad_row)

        # Overwrite
        self._overwrite_check = QCheckBox(
            self._lang.get(
                "safety_review_overwrite",
                "Overwrite original files (no backup!)",
            )
        )
        self._overwrite_check.setChecked(False)
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self._overwrite_check)

        # Output dir
        self._dir_label = QLabel(
            self._lang.get("safety_review_output_dir", "Output folder:")
        )
        layout.addWidget(self._dir_label)
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        if self._paths:
            self._dir_edit.setText(str(Path(self._paths[0]).parent))
        self._browse_btn = QPushButton(
            self._lang.get("export_browse", "Browse..."))
        self._browse_btn.clicked.connect(self._browse)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(self._browse_btn)
        layout.addLayout(dir_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setFormat("%v / %m  (%p%)")
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        self._time_label = QLabel("")
        layout.addWidget(self._time_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._run_btn = QPushButton(
            self._lang.get("safety_review_run", "Apply Mosaic")
        )
        self._run_btn.clicked.connect(self._do_run)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._run_btn)
        layout.addLayout(btn_row)

    def _on_mode_changed_batch(self, index):
        mode = self._mode_combo.itemData(index)
        defaults = _MODE_DEFAULTS.get(mode, _MODE_DEFAULTS[MODE_REAL])
        self._padding_spin.setValue(defaults["padding"])

    def _on_overwrite_toggled(self, checked):
        self._dir_edit.setEnabled(not checked)
        self._browse_btn.setEnabled(not checked)
        self._dir_label.setEnabled(not checked)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("safety_review_output_dir", "Output folder"),
        )
        if folder:
            self._dir_edit.setText(folder)

    def _do_run(self):
        overwrite = self._overwrite_check.isChecked()
        output_dir = self._dir_edit.text().strip()
        if not overwrite and (not output_dir or not Path(output_dir).is_dir()):
            return

        self._run_btn.setEnabled(False)
        self._status_label.setText(
            self._lang.get("safety_review_installing",
                           "Installing dependencies..."))

        bs = self._block_spin.value()
        pad = self._padding_spin.value()
        mode = self._mode_combo.currentData()
        conf = self._conf_spin.value()
        expand = self._expand_spin.value()
        style = self._style_combo.currentData()
        categories = frozenset(
            cat for cat, cb in self._cat_checks.items() if cb.isChecked()
        )

        def _on_deps_ready():
            self._progress.setVisible(True)
            self._progress.setMaximum(len(self._paths))
            self._progress.setValue(0)
            self._status_label.setText("")

            frozen_env = self._get_frozen_env() if self._get_frozen_env else None
            if frozen_env:
                python, sp = frozen_env
                self._worker = _SubprocessBatchWorker(
                    python, sp, self._paths, output_dir, bs, pad, overwrite,
                    mode=mode, confidence=conf, expand_pct=expand,
                    style=style, categories=categories,
                )
            else:
                self._worker = _BatchWorker(
                    self._paths, output_dir, bs, pad, overwrite,
                    mode=mode, confidence=conf, expand_pct=expand,
                    style=style, categories=categories,
                )
            self._worker.progress.connect(self._on_progress)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        _ensure_deps(self._gui.main_window, _on_deps_ready, mode=mode)

    def _on_progress(self, current, total, name, *time_args):
        self._progress.setValue(current)
        self._status_label.setText(f"{current + 1}/{total}  {name}")
        if len(time_args) >= 2:
            elapsed, eta = time_args[0], time_args[1]
            elapsed_str = ScanAllDialog._fmt_time(elapsed)
            eta_str = ScanAllDialog._fmt_time(eta) if current > 0 else "..."
            self._time_label.setText(
                self._lang.get(
                    "safety_review_time",
                    "Elapsed: {elapsed}    ETA: {eta}    (~{speed:.1f}s / image)",
                ).format(
                    elapsed=elapsed_str,
                    eta=eta_str,
                    speed=elapsed / max(current, 1),
                )
            )

    def _cleanup(self):
        self._worker = None

    def _on_finished(self, success, failed, total_regions):
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        self._time_label.setText("")

        if total_regions >= 0:
            msg = self._lang.get(
                "safety_review_scan_all_done",
                "Done — {success}/{total} images processed, "
                "{regions} region(s) mosaiced, {failed} failed.",
            ).format(
                success=success, total=success + failed,
                regions=total_regions, failed=failed,
            )
        else:
            msg = self._lang.get(
                "safety_review_batch_done",
                "Processed {success}/{total} image(s)",
            ).format(success=success, total=success + failed)
        self._status_label.setText(msg)

        if hasattr(self._gui.main_window, "toast"):
            if failed:
                self._gui.main_window.toast.info(msg)
            else:
                self._gui.main_window.toast.success(msg)

        # Reload viewer
        if self._overwrite_check.isChecked():
            try:
                if self._gui.tile_grid_mode:
                    self._gui.load_tile_grid_async(list(self._gui.model.images))
                elif self._gui.deep_zoom:
                    images = self._gui.model.images
                    if images and 0 <= self._gui.current_index < len(images):
                        self._gui._clear_deep_zoom()
                        self._gui.load_deep_zoom_image(
                            images[self._gui.current_index])
            except Exception:
                logger.debug("Viewer reload after batch review failed",
                             exc_info=True)

        QTimer.singleShot(500, self.accept)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            try:
                self._worker.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

REQUIRED_PACKAGES_AUTO = REQUIRED_PACKAGES_REAL + [
    p for p in REQUIRED_PACKAGES_ANIME if p not in REQUIRED_PACKAGES_REAL
]


def _ensure_deps(parent, on_ready, mode: str = MODE_REAL):
    if mode == MODE_AUTO:
        pkgs = REQUIRED_PACKAGES_AUTO
    elif mode == MODE_ANIME:
        pkgs = REQUIRED_PACKAGES_ANIME
    else:
        pkgs = REQUIRED_PACKAGES_REAL
    try:
        ensure_dependencies(parent, pkgs, on_ready)
    except Exception:
        logger.error("ensure_dependencies raised", exc_info=True)


class SafetyReviewPlugin(ImervuePlugin):
    plugin_name = "Safety Review"
    plugin_version = "1.0.0"
    plugin_description = (
        "Auto-detect and mosaic exposed genitalia using NudeNet. "
        "Nipples are never mosaiced."
    )
    plugin_author = "Imervue"

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def on_build_menu_bar(self, plugin_menu) -> None:
        lang = language_wrapper.language_word_dict

        # Try to reuse AI Tools submenu
        ai_menu = None
        for action in plugin_menu.actions():
            m = action.menu()
            if m and action.text().replace("&", "") == lang.get(
                    "bg_remove_menu", "AI Tools"):
                ai_menu = m
                break
        if ai_menu is None:
            ai_menu = plugin_menu.addMenu(
                lang.get("bg_remove_menu", "AI Tools"))

        ai_menu.addSeparator()

        # ★ Scan All — the primary action
        scan_all = ai_menu.addAction(
            lang.get("safety_review_scan_all",
                      "Safety Review — Scan All Images")
        )
        scan_all.triggered.connect(self._scan_all)

        # Single
        single = ai_menu.addAction(
            lang.get("safety_review_title",
                      "Safety Review — Auto Mosaic")
        )
        single.triggered.connect(self._open_single_dialog)

        # Batch
        batch = ai_menu.addAction(
            lang.get("safety_review_batch_title",
                      "Batch Safety Review")
        )
        batch.triggered.connect(self._open_batch_dialog)

    def on_build_context_menu(self, menu: QMenu, viewer: GPUImageView) -> None:
        lang = language_wrapper.language_word_dict

        # Deep zoom — quick-apply on current image
        if viewer.deep_zoom:
            images = viewer.model.images
            if images and 0 <= viewer.current_index < len(images):
                path = images[viewer.current_index]
                action = menu.addAction(
                    lang.get("safety_review_quick",
                              "Safety Review — Quick Mosaic")
                )
                action.triggered.connect(lambda: self._quick_single(path))

        # Tile grid — batch on selection
        if (viewer.tile_grid_mode and viewer.tile_selection_mode
                and viewer.selected_tiles):
            paths = list(viewer.selected_tiles)
            action = menu.addAction(
                lang.get("safety_review_batch_title",
                          "Batch Safety Review")
            )
            action.triggered.connect(lambda: self._run_batch(paths))

        # Always show Scan All in context menu
        if viewer.model.images:
            action = menu.addAction(
                lang.get("safety_review_scan_all",
                          "Safety Review — Scan All Images")
            )
            action.triggered.connect(self._scan_all)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _get_frozen_env(self) -> tuple[str, str] | None:
        if not _is_frozen():
            return None
        python = _find_external_python()
        if not python:
            logger.error("No external Python for subprocess")
            return None
        return python, str(_frozen_site_packages())

    def _scan_all(self):
        """Open the scan-all dialog — user picks folder and settings."""
        initial = list(self.viewer.model.images) if self.viewer.model.images else None
        try:
            dlg = ScanAllDialog(
                self.viewer, initial_paths=initial,
                get_frozen_env=self._get_frozen_env)
            dlg.exec()
        except Exception:
            logger.error("Scan-all dialog failed", exc_info=True)

    def _quick_single(self, path: str):
        """Right-click quick apply — opens single-image dialog."""
        if not Path(path).is_file():
            return
        self._run_single(path)

    def _open_single_dialog(self):
        images = self.viewer.model.images
        if not images or self.viewer.current_index >= len(images):
            return
        path = images[self.viewer.current_index]
        self._run_single(path)

    def _run_single(self, path: str):
        if not Path(path).is_file():
            return
        try:
            dlg = SafetyReviewDialog(
                self.viewer, path,
                get_frozen_env=self._get_frozen_env)
            dlg.exec()
        except Exception:
            logger.error("Single dialog failed", exc_info=True)

    def _open_batch_dialog(self):
        if (self.viewer.tile_grid_mode and self.viewer.tile_selection_mode
                and self.viewer.selected_tiles):
            paths = list(self.viewer.selected_tiles)
        else:
            paths = list(self.viewer.model.images)
        if paths:
            self._run_batch(paths)

    def _run_batch(self, paths: list[str]):
        try:
            dlg = BatchSafetyReviewDialog(
                self.viewer, paths,
                get_frozen_env=self._get_frozen_env)
            dlg.exec()
        except Exception:
            logger.error("Batch dialog failed", exc_info=True)

    # ------------------------------------------------------------------
    # Translations
    # ------------------------------------------------------------------

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "safety_review_title": "Safety Review \u2014 Auto Mosaic",
                "safety_review_batch_title": "Batch Safety Review",
                "safety_review_scan_all": "Safety Review \u2014 Scan All Images",
                "safety_review_scan_all_title": "Safety Review \u2014 Scan All",
                "safety_review_scan_all_confirm":
                    "This will scan {count} image(s) and mosaic any detected "
                    "genitalia directly on the original files.\n\n"
                    "Nipples will NOT be mosaiced.\n\n"
                    "Continue?",
                "safety_review_scan_all_info":
                    "Scanning {count} images \u2014 genitalia will be mosaiced, "
                    "nipples will NOT be touched.",
                "safety_review_scan_all_done":
                    "Done \u2014 {success}/{total} images processed, "
                    "{regions} region(s) mosaiced, {failed} failed.",
                "safety_review_quick": "Safety Review \u2014 Quick Mosaic",
                "safety_review_source": "Source:",
                "safety_review_info":
                    "Detects and mosaics exposed genitalia (male & female). "
                    "Nipples are NOT mosaiced.",
                "safety_review_block_size": "Mosaic block size (px):",
                "safety_review_padding": "Padding around region (px):",
                "safety_review_overwrite":
                    "Overwrite original files (no backup!)",
                "safety_review_overwrite_single": "Overwrite original file",
                "safety_review_output_dir": "Output folder:",
                "safety_review_run": "Apply Mosaic",
                "safety_review_done": "Done! Saved to: {path}",
                "safety_review_done_short": "Mosaic applied!",
                "safety_review_nothing":
                    "No genitalia detected \u2014 image unchanged.",
                "safety_review_batch_done":
                    "Processed {success}/{total} image(s)",
                "safety_review_close": "Close",
                "safety_review_time":
                    "Elapsed: {elapsed}    ETA: {eta}    (~{speed:.1f}s / image)",
                "safety_review_mode": "Detection mode:",
                "safety_review_mode_real": "Real Photo",
                "safety_review_mode_anime": "Anime / Illustration",
                "safety_review_confidence": "Min confidence:",
                "safety_review_start": "Start",
                "safety_review_installing": "Installing dependencies...",
                "safety_review_expand_pct": "Expand detection box (%):",
                "safety_review_scan_folder": "Source folder:",
                "safety_review_scan_folder_hint":
                    "Choose a folder to scan for images",
                "safety_review_mode_auto": "Auto-detect",
                "safety_review_style": "Censor style:",
                "safety_review_style_mosaic": "Mosaic",
                "safety_review_style_blur": "Gaussian Blur",
                "safety_review_style_black": "Black Bar",
                "safety_review_categories": "Detection categories:",
                "safety_review_cat_genitalia": "Genitalia (penis / vagina)",
                "safety_review_cat_anus": "Anus",
                "safety_review_cat_nipple": "Nipple / Breast",
                "safety_review_cat_sexual_act": "Sexual Act (anime only)",
            },
            "Traditional_Chinese": {
                "safety_review_title":
                    "\u5b89\u5168\u5be9\u6838 \u2014 \u81ea\u52d5\u6253\u78bc",
                "safety_review_batch_title":
                    "\u6279\u6b21\u5b89\u5168\u5be9\u6838",
                "safety_review_scan_all":
                    "\u5b89\u5168\u5be9\u6838 \u2014 \u6383\u63cf\u6240\u6709\u5716\u7247",
                "safety_review_scan_all_title":
                    "\u5b89\u5168\u5be9\u6838 \u2014 \u6383\u63cf\u5168\u90e8",
                "safety_review_scan_all_confirm":
                    "\u5c07\u6383\u63cf {count} \u5f35\u5716\u7247\uff0c"
                    "\u5075\u6e2c\u5230\u7684\u751f\u6b96\u5668\u6703\u76f4\u63a5\u6253\u78bc"
                    "\u5728\u539f\u59cb\u6a94\u6848\u4e0a\u3002\n\n"
                    "\u7537\u5973\u4e73\u982d\u90fd\u4e0d\u6703\u88ab\u6253\u78bc\u3002\n\n"
                    "\u7e7c\u7e8c\uff1f",
                "safety_review_scan_all_info":
                    "\u6b63\u5728\u6383\u63cf {count} \u5f35\u5716\u7247"
                    " \u2014 \u751f\u6b96\u5668\u6703\u88ab\u6253\u78bc\uff0c"
                    "\u4e73\u982d\u4e0d\u6703\u88ab\u8655\u7406\u3002",
                "safety_review_scan_all_done":
                    "\u5b8c\u6210 \u2014 \u5df2\u8655\u7406 {success}/{total}"
                    " \u5f35\u5716\u7247\uff0c"
                    "\u6253\u78bc {regions} \u500b\u5340\u57df\uff0c"
                    "{failed} \u5f35\u5931\u6557\u3002",
                "safety_review_quick":
                    "\u5b89\u5168\u5be9\u6838 \u2014 \u5feb\u901f\u6253\u78bc",
                "safety_review_source": "\u4f86\u6e90\uff1a",
                "safety_review_info":
                    "\u5075\u6e2c\u4e26\u6253\u78bc\u88f8\u9732\u7684"
                    "\u751f\u6b96\u5668\uff08\u7537\u5973\uff09\u3002"
                    "\u4e73\u982d\u4e0d\u6703\u88ab\u6253\u78bc\u3002",
                "safety_review_block_size":
                    "\u99ac\u8cfd\u514b\u5927\u5c0f (px)\uff1a",
                "safety_review_padding":
                    "\u5340\u57df\u5916\u64f4 (px)\uff1a",
                "safety_review_overwrite":
                    "\u8986\u84cb\u539f\u59cb\u6a94\u6848\uff08\u4e0d\u5099\u4efd\uff01\uff09",
                "safety_review_overwrite_single":
                    "\u8986\u84cb\u539f\u59cb\u6a94\u6848",
                "safety_review_output_dir":
                    "\u8f38\u51fa\u8cc7\u6599\u593e\uff1a",
                "safety_review_run": "\u57f7\u884c\u6253\u78bc",
                "safety_review_done":
                    "\u5b8c\u6210\uff01\u5df2\u5132\u5b58\u81f3\uff1a{path}",
                "safety_review_done_short": "\u6253\u78bc\u5b8c\u6210\uff01",
                "safety_review_nothing":
                    "\u672a\u5075\u6e2c\u5230\u751f\u6b96\u5668"
                    " \u2014 \u5716\u7247\u672a\u8b8a\u66f4\u3002",
                "safety_review_batch_done":
                    "\u5df2\u8655\u7406 {success}/{total} \u5f35\u5716\u7247",
                "safety_review_close": "\u95dc\u9589",
                "safety_review_time":
                    "\u5df2\u7d93\u904e: {elapsed}    \u9810\u8a08: {eta}    (~{speed:.1f}\u79d2 / \u5f35)",
                "safety_review_mode": "\u5075\u6e2c\u6a21\u5f0f\uff1a",
                "safety_review_mode_real": "\u771f\u4eba\u7167\u7247",
                "safety_review_mode_anime": "\u52d5\u756b / \u63d2\u756b",
                "safety_review_confidence": "\u6700\u4f4e\u4fe1\u5fc3\u5ea6\uff1a",
                "safety_review_start": "\u958b\u59cb",
                "safety_review_installing": "\u6b63\u5728\u5b89\u88dd\u76f8\u4f9d\u5957\u4ef6\u2026",
                "safety_review_expand_pct": "\u5075\u6e2c\u6846\u64f4\u5f35 (%)\uff1a",
                "safety_review_scan_folder": "\u4f86\u6e90\u8cc7\u6599\u593e\uff1a",
                "safety_review_scan_folder_hint":
                    "\u9078\u64c7\u8981\u6383\u63cf\u7684\u8cc7\u6599\u593e",
                "safety_review_mode_auto": "\u81ea\u52d5\u5224\u65b7",
                "safety_review_style": "\u6253\u78bc\u6a23\u5f0f\uff1a",
                "safety_review_style_mosaic": "\u99ac\u8cfd\u514b",
                "safety_review_style_blur": "\u9ad8\u65af\u6a21\u7cca",
                "safety_review_style_black": "\u9ed1\u689d\u906e\u64cb",
                "safety_review_categories": "\u5075\u6e2c\u985e\u5225\uff1a",
                "safety_review_cat_genitalia": "\u751f\u6b96\u5668 (\u9670\u8396 / \u9670\u9053)",
                "safety_review_cat_anus": "\u809b\u9580",
                "safety_review_cat_nipple": "\u4e73\u982d / \u4e73\u623f",
                "safety_review_cat_sexual_act": "\u6027\u884c\u70ba (\u50c5\u52d5\u756b)",
            },
            "Chinese": {
                "safety_review_title":
                    "\u5b89\u5168\u5ba1\u6838 \u2014 \u81ea\u52a8\u6253\u7801",
                "safety_review_batch_title":
                    "\u6279\u91cf\u5b89\u5168\u5ba1\u6838",
                "safety_review_scan_all":
                    "\u5b89\u5168\u5ba1\u6838 \u2014 \u626b\u63cf\u6240\u6709\u56fe\u7247",
                "safety_review_scan_all_title":
                    "\u5b89\u5168\u5ba1\u6838 \u2014 \u626b\u63cf\u5168\u90e8",
                "safety_review_scan_all_confirm":
                    "\u5c06\u626b\u63cf {count} \u5f20\u56fe\u7247\uff0c"
                    "\u68c0\u6d4b\u5230\u7684\u751f\u6b96\u5668\u4f1a\u76f4\u63a5\u6253\u7801"
                    "\u5728\u539f\u59cb\u6587\u4ef6\u4e0a\u3002\n\n"
                    "\u7537\u5973\u4e73\u5934\u90fd\u4e0d\u4f1a\u88ab\u6253\u7801\u3002\n\n"
                    "\u7ee7\u7eed\uff1f",
                "safety_review_scan_all_info":
                    "\u6b63\u5728\u626b\u63cf {count} \u5f20\u56fe\u7247"
                    " \u2014 \u751f\u6b96\u5668\u4f1a\u88ab\u6253\u7801\uff0c"
                    "\u4e73\u5934\u4e0d\u4f1a\u88ab\u5904\u7406\u3002",
                "safety_review_scan_all_done":
                    "\u5b8c\u6210 \u2014 \u5df2\u5904\u7406 {success}/{total}"
                    " \u5f20\u56fe\u7247\uff0c"
                    "\u6253\u7801 {regions} \u4e2a\u533a\u57df\uff0c"
                    "{failed} \u5f20\u5931\u8d25\u3002",
                "safety_review_quick":
                    "\u5b89\u5168\u5ba1\u6838 \u2014 \u5feb\u901f\u6253\u7801",
                "safety_review_source": "\u6765\u6e90\uff1a",
                "safety_review_info":
                    "\u68c0\u6d4b\u5e76\u6253\u7801\u88f8\u9732\u7684"
                    "\u751f\u6b96\u5668\uff08\u7537\u5973\uff09\u3002"
                    "\u4e73\u5934\u4e0d\u4f1a\u88ab\u6253\u7801\u3002",
                "safety_review_block_size":
                    "\u9a6c\u8d5b\u514b\u5927\u5c0f (px)\uff1a",
                "safety_review_padding":
                    "\u533a\u57df\u5916\u6269 (px)\uff1a",
                "safety_review_overwrite":
                    "\u8986\u76d6\u539f\u59cb\u6587\u4ef6\uff08\u4e0d\u5907\u4efd\uff01\uff09",
                "safety_review_overwrite_single":
                    "\u8986\u76d6\u539f\u59cb\u6587\u4ef6",
                "safety_review_output_dir":
                    "\u8f93\u51fa\u6587\u4ef6\u5939\uff1a",
                "safety_review_run": "\u6267\u884c\u6253\u7801",
                "safety_review_done":
                    "\u5b8c\u6210\uff01\u5df2\u4fdd\u5b58\u81f3\uff1a{path}",
                "safety_review_done_short": "\u6253\u7801\u5b8c\u6210\uff01",
                "safety_review_nothing":
                    "\u672a\u68c0\u6d4b\u5230\u751f\u6b96\u5668"
                    " \u2014 \u56fe\u7247\u672a\u53d8\u66f4\u3002",
                "safety_review_batch_done":
                    "\u5df2\u5904\u7406 {success}/{total} \u5f20\u56fe\u7247",
                "safety_review_close": "\u5173\u95ed",
                "safety_review_time":
                    "\u5df2\u7ecf\u8fc7: {elapsed}    \u9884\u8ba1: {eta}    (~{speed:.1f}\u79d2 / \u5f20)",
                "safety_review_mode": "\u68c0\u6d4b\u6a21\u5f0f\uff1a",
                "safety_review_mode_real": "\u771f\u4eba\u7167\u7247",
                "safety_review_mode_anime": "\u52a8\u6f2b / \u63d2\u753b",
                "safety_review_confidence": "\u6700\u4f4e\u7f6e\u4fe1\u5ea6\uff1a",
                "safety_review_start": "\u5f00\u59cb",
                "safety_review_installing": "\u6b63\u5728\u5b89\u88c5\u4f9d\u8d56\u5305\u2026",
                "safety_review_expand_pct": "\u68c0\u6d4b\u6846\u6269\u5f20 (%)\uff1a",
                "safety_review_scan_folder": "\u6e90\u6587\u4ef6\u5939\uff1a",
                "safety_review_scan_folder_hint":
                    "\u9009\u62e9\u8981\u626b\u63cf\u7684\u6587\u4ef6\u5939",
                "safety_review_mode_auto": "\u81ea\u52a8\u5224\u65ad",
                "safety_review_style": "\u6253\u7801\u6837\u5f0f\uff1a",
                "safety_review_style_mosaic": "\u9a6c\u8d5b\u514b",
                "safety_review_style_blur": "\u9ad8\u65af\u6a21\u7cca",
                "safety_review_style_black": "\u9ed1\u6761\u906e\u6321",
                "safety_review_categories": "\u68c0\u6d4b\u7c7b\u522b\uff1a",
                "safety_review_cat_genitalia": "\u751f\u6b96\u5668 (\u9634\u830e / \u9634\u9053)",
                "safety_review_cat_anus": "\u809b\u95e8",
                "safety_review_cat_nipple": "\u4e73\u5934 / \u4e73\u623f",
                "safety_review_cat_sexual_act": "\u6027\u884c\u4e3a (\u4ec5\u52a8\u6f2b)",
            },
            "Japanese": {
                "safety_review_title":
                    "\u5b89\u5168\u5be9\u67fb \u2014 \u81ea\u52d5\u30e2\u30b6\u30a4\u30af",
                "safety_review_batch_title":
                    "\u4e00\u62ec\u5b89\u5168\u5be9\u67fb",
                "safety_review_scan_all":
                    "\u5b89\u5168\u5be9\u67fb \u2014 \u5168\u753b\u50cf\u30b9\u30ad\u30e3\u30f3",
                "safety_review_scan_all_title":
                    "\u5b89\u5168\u5be9\u67fb \u2014 \u5168\u30b9\u30ad\u30e3\u30f3",
                "safety_review_scan_all_confirm":
                    "{count}\u679a\u306e\u753b\u50cf\u3092\u30b9\u30ad\u30e3\u30f3\u3057\u3001"
                    "\u691c\u51fa\u3055\u308c\u305f\u6027\u5668\u3092\u539f\u30d5\u30a1\u30a4\u30eb\u306b"
                    "\u76f4\u63a5\u30e2\u30b6\u30a4\u30af\u3057\u307e\u3059\u3002\n\n"
                    "\u4e73\u9996\u306f\u30e2\u30b6\u30a4\u30af\u3055\u308c\u307e\u305b\u3093\u3002\n\n"
                    "\u7d9a\u884c\u3057\u307e\u3059\u304b\uff1f",
                "safety_review_scan_all_info":
                    "{count}\u679a\u306e\u753b\u50cf\u3092\u30b9\u30ad\u30e3\u30f3\u4e2d"
                    " \u2014 \u6027\u5668\u306f\u30e2\u30b6\u30a4\u30af\u3001"
                    "\u4e73\u9996\u306f\u305d\u306e\u307e\u307e\u3002",
                "safety_review_scan_all_done":
                    "\u5b8c\u4e86 \u2014 {success}/{total}\u679a\u51e6\u7406\u3001"
                    "{regions}\u7b87\u6240\u30e2\u30b6\u30a4\u30af\u3001"
                    "{failed}\u679a\u5931\u6557\u3002",
                "safety_review_quick":
                    "\u5b89\u5168\u5be9\u67fb \u2014 \u30af\u30a4\u30c3\u30af\u30e2\u30b6\u30a4\u30af",
                "safety_review_source": "\u30bd\u30fc\u30b9\uff1a",
                "safety_review_info":
                    "\u9732\u51fa\u3057\u305f\u6027\u5668\uff08\u7537\u5973\uff09\u3092"
                    "\u691c\u51fa\u3057\u3066\u30e2\u30b6\u30a4\u30af\u3057\u307e\u3059\u3002"
                    "\u4e73\u9996\u306f\u30e2\u30b6\u30a4\u30af\u3055\u308c\u307e\u305b\u3093\u3002",
                "safety_review_block_size":
                    "\u30e2\u30b6\u30a4\u30af\u30b5\u30a4\u30ba (px)\uff1a",
                "safety_review_padding":
                    "\u9818\u57df\u62e1\u5f35 (px)\uff1a",
                "safety_review_overwrite":
                    "\u5143\u30d5\u30a1\u30a4\u30eb\u3092\u4e0a\u66f8\u304d"
                    "\uff08\u30d0\u30c3\u30af\u30a2\u30c3\u30d7\u306a\u3057\uff01\uff09",
                "safety_review_overwrite_single":
                    "\u5143\u30d5\u30a1\u30a4\u30eb\u3092\u4e0a\u66f8\u304d",
                "safety_review_output_dir":
                    "\u51fa\u529b\u30d5\u30a9\u30eb\u30c0\uff1a",
                "safety_review_run": "\u30e2\u30b6\u30a4\u30af\u9069\u7528",
                "safety_review_done":
                    "\u5b8c\u4e86\uff01\u4fdd\u5b58\u5148\uff1a{path}",
                "safety_review_done_short":
                    "\u30e2\u30b6\u30a4\u30af\u5b8c\u4e86\uff01",
                "safety_review_nothing":
                    "\u6027\u5668\u672a\u691c\u51fa"
                    " \u2014 \u753b\u50cf\u672a\u5909\u66f4\u3002",
                "safety_review_batch_done":
                    "{success}/{total}\u679a\u306e\u753b\u50cf\u3092\u51e6\u7406\u3057\u307e\u3057\u305f",
                "safety_review_close": "\u9589\u3058\u308b",
                "safety_review_time":
                    "\u7d4c\u904e: {elapsed}    \u6b8b\u308a: {eta}    (~{speed:.1f}\u79d2 / \u679a)",
                "safety_review_mode": "\u691c\u51fa\u30e2\u30fc\u30c9\uff1a",
                "safety_review_mode_real": "\u5b9f\u5199\u771f",
                "safety_review_mode_anime": "\u30a2\u30cb\u30e1 / \u30a4\u30e9\u30b9\u30c8",
                "safety_review_confidence": "\u6700\u4f4e\u4fe1\u983c\u5ea6\uff1a",
                "safety_review_start": "\u958b\u59cb",
                "safety_review_installing":
                    "\u4f9d\u5b58\u30d1\u30c3\u30b1\u30fc\u30b8\u3092\u30a4\u30f3\u30b9\u30c8\u30fc\u30eb\u4e2d\u2026",
                "safety_review_expand_pct":
                    "\u691c\u51fa\u30dc\u30c3\u30af\u30b9\u62e1\u5f35 (%)\uff1a",
                "safety_review_scan_folder": "\u30bd\u30fc\u30b9\u30d5\u30a9\u30eb\u30c0\uff1a",
                "safety_review_scan_folder_hint":
                    "\u30b9\u30ad\u30e3\u30f3\u3059\u308b\u30d5\u30a9\u30eb\u30c0\u3092\u9078\u629e",
                "safety_review_mode_auto": "\u81ea\u52d5\u5224\u5b9a",
                "safety_review_style": "\u30e2\u30b6\u30a4\u30af\u30b9\u30bf\u30a4\u30eb\uff1a",
                "safety_review_style_mosaic": "\u30e2\u30b6\u30a4\u30af",
                "safety_review_style_blur": "\u30ac\u30a6\u30b7\u30a2\u30f3\u30d6\u30e9\u30fc",
                "safety_review_style_black": "\u9ed2\u30d0\u30fc",
                "safety_review_categories": "\u691c\u51fa\u30ab\u30c6\u30b4\u30ea\uff1a",
                "safety_review_cat_genitalia": "\u6027\u5668 (\u30da\u30cb\u30b9 / \u30f4\u30a1\u30ae\u30ca)",
                "safety_review_cat_anus": "\u808b\u9580",
                "safety_review_cat_nipple": "\u4e73\u9996 / \u4e73\u623f",
                "safety_review_cat_sexual_act": "\u6027\u884c\u70ba (\u30a2\u30cb\u30e1\u306e\u307f)",
            },
            "Korean": {
                "safety_review_title":
                    "\uc548\uc804 \uac80\ud1a0 \u2014 \uc790\ub3d9 \ubaa8\uc790\uc774\ud06c",
                "safety_review_batch_title":
                    "\uc77c\uad04 \uc548\uc804 \uac80\ud1a0",
                "safety_review_scan_all":
                    "\uc548\uc804 \uac80\ud1a0 \u2014 \ubaa8\ub4e0 \uc774\ubbf8\uc9c0 \uc2a4\uca94",
                "safety_review_scan_all_title":
                    "\uc548\uc804 \uac80\ud1a0 \u2014 \uc804\uccb4 \uc2a4\ucafc",
                "safety_review_scan_all_confirm":
                    "{count}\uac1c\uc758 \uc774\ubbf8\uc9c0\ub97c \uc2a4\ucafc\ud558\uace0 "
                    "\uac10\uc9c0\ub41c \uc131\uae30\ub97c \uc6d0\ubcf8 \ud30c\uc77c\uc5d0 "
                    "\uc9c1\uc811 \ubaa8\uc790\uc774\ud06c\ud569\ub2c8\ub2e4.\n\n"
                    "\uc720\ub450\ub294 \ubaa8\uc790\uc774\ud06c\ub418\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.\n\n"
                    "\uacc4\uc18d\ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?",
                "safety_review_scan_all_info":
                    "{count}\uac1c \uc774\ubbf8\uc9c0 \uc2a4\ucafc \uc911"
                    " \u2014 \uc131\uae30 \ubaa8\uc790\uc774\ud06c, "
                    "\uc720\ub450 \ubbf8\ucc98\ub9ac.",
                "safety_review_scan_all_done":
                    "\uc644\ub8cc \u2014 {success}/{total}\uac1c \ucc98\ub9ac, "
                    "{regions}\uac1c \uc601\uc5ed \ubaa8\uc790\uc774\ud06c, "
                    "{failed}\uac1c \uc2e4\ud328.",
                "safety_review_quick":
                    "\uc548\uc804 \uac80\ud1a0 \u2014 \ube60\ub978 \ubaa8\uc790\uc774\ud06c",
                "safety_review_source": "\uc18c\uc2a4:",
                "safety_review_info":
                    "\ub178\ucd9c\ub41c \uc131\uae30(\ub0a8\ub140)\ub97c "
                    "\uac10\uc9c0\ud558\uc5ec \ubaa8\uc790\uc774\ud06c\ud569\ub2c8\ub2e4. "
                    "\uc720\ub450\ub294 \ubaa8\uc790\uc774\ud06c\ub418\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
                "safety_review_block_size":
                    "\ubaa8\uc790\uc774\ud06c \ud06c\uae30 (px):",
                "safety_review_padding":
                    "\uc601\uc5ed \ud655\uc7a5 (px):",
                "safety_review_overwrite":
                    "\uc6d0\ubcf8 \ud30c\uc77c \ub36e\uc5b4\uc4f0\uae30"
                    " (\ubc31\uc5c5 \uc5c6\uc74c!)",
                "safety_review_overwrite_single":
                    "\uc6d0\ubcf8 \ud30c\uc77c \ub36e\uc5b4\uc4f0\uae30",
                "safety_review_output_dir":
                    "\ucd9c\ub825 \ud3f4\ub354:",
                "safety_review_run": "\ubaa8\uc790\uc774\ud06c \uc801\uc6a9",
                "safety_review_done":
                    "\uc644\ub8cc! \uc800\uc7a5 \uc704\uce58: {path}",
                "safety_review_done_short":
                    "\ubaa8\uc790\uc774\ud06c \uc644\ub8cc!",
                "safety_review_nothing":
                    "\uc131\uae30 \ubbf8\uac10\uc9c0"
                    " \u2014 \uc774\ubbf8\uc9c0 \ubcc0\uacbd \uc5c6\uc74c.",
                "safety_review_batch_done":
                    "{success}/{total}\uac1c \uc774\ubbf8\uc9c0 \ucc98\ub9ac \uc644\ub8cc",
                "safety_review_close": "\ub2eb\uae30",
                "safety_review_time":
                    "\uacbd\uacfc: {elapsed}    \ub0a8\uc740 \uc2dc\uac04: {eta}    (~{speed:.1f}\ucd08 / \uc7a5)",
                "safety_review_mode": "\uac10\uc9c0 \ubaa8\ub4dc:",
                "safety_review_mode_real": "\uc2e4\uc0ac\uc9c4",
                "safety_review_mode_anime": "\uc560\ub2c8\uba54\uc774\uc158 / \uc77c\ub7ec\uc2a4\ud2b8",
                "safety_review_confidence": "\ucd5c\uc18c \uc2e0\ub8b0\ub3c4:",
                "safety_review_start": "\uc2dc\uc791",
                "safety_review_installing":
                    "\uc758\uc874\uc131 \ud328\ud0a4\uc9c0 \uc124\uce58 \uc911\u2026",
                "safety_review_expand_pct":
                    "\uac10\uc9c0 \ubc15\uc2a4 \ud655\uc7a5 (%)\uff1a",
                "safety_review_scan_folder": "\uc18c\uc2a4 \ud3f4\ub354:",
                "safety_review_scan_folder_hint":
                    "\uc2a4\ucafc\ud560 \ud3f4\ub354\ub97c \uc120\ud0dd\ud558\uc138\uc694",
                "safety_review_mode_auto": "\uc790\ub3d9 \uac10\uc9c0",
                "safety_review_style": "\ubaa8\uc790\uc774\ud06c \uc2a4\ud0c0\uc77c:",
                "safety_review_style_mosaic": "\ubaa8\uc790\uc774\ud06c",
                "safety_review_style_blur": "\uac00\uc6b0\uc2dc\uc548 \ube14\ub7ec",
                "safety_review_style_black": "\uac80\uc740 \ub9c9\ub300",
                "safety_review_categories": "\uac10\uc9c0 \uce74\ud14c\uace0\ub9ac:",
                "safety_review_cat_genitalia": "\uc131\uae30 (\uc74c\uacbd / \uc9c8)",
                "safety_review_cat_anus": "\ud56d\ubb38",
                "safety_review_cat_nipple": "\uc720\ub450 / \uc720\ubc29",
                "safety_review_cat_sexual_act": "\uc131\ud589\uc704 (\uc560\ub2c8\uba54\uc774\uc158\ub9cc)",
            },
        }
