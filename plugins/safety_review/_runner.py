"""Subprocess runner for safety review plugin.

Usage (frozen env):
    python _runner.py <site_packages> single <input> <output> <block_size> <padding> [<mode> <confidence> <expand_pct> <style> <categories> <shape>]
    python _runner.py <site_packages> batch  <json_paths> <output_dir> <block_size> <padding> <overwrite> [<mode> <confidence> <expand_pct> <style> <categories> <source_root> <only_censored> <shape> <failed_dir> <scan_root> <merge_regions>]

``source_root`` (batch only, optional) mirrors each source's subfolder under
``output_dir`` so a recursive scan keeps its tree instead of flattening.
``only_censored`` (batch only, optional, "True"/"False") writes only images
that were actually censored, leaving clean images uncopied.
``shape`` (optional: rect / ellipse / precise) confines the censor to the box,
its inscribed ellipse, or a segmentation mask; precise degrades to ellipse in
this frozen-env runner.

Protocol — stdout lines:
    PROGRESS:<message>
    OK:<output_path>
    BATCH_PROGRESS:<current>:<total>:<filename>
    BATCH_OK:<success>:<failed>
    ERROR:<message>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# The constants and censor helpers are shared with the in-app detection path.
# In the frozen build this file runs in an external Python that cannot import
# the Qt plugin package, so it loads them as sibling modules instead.
if __package__:   # imported as part of the plugin package (tests)
    from safety_review._censor_core import (
        _censor_region,
        _detect_image_mode,
        _ensure_parent,
        _expand_box,
        _junction_bridges,
        _merge_gap,
        _shrink_box_center,
    )
    from safety_review._constants import (
        MIN_CONFIDENCE,
        SHAPE_ELLIPSE,
        SHAPE_RECT,
        STYLE_MOSAIC,
        _ERAX_MODEL,
        _ERAX_REPO,
        _ERAX_REVISION,
        _categories_to_anime_classes,
        _categories_to_real_labels,
    )
else:             # run as a script next to its siblings
    from _censor_core import (
        _censor_region,
        _detect_image_mode,
        _ensure_parent,
        _expand_box,
        _junction_bridges,
        _merge_gap,
        _shrink_box_center,
    )
    from _constants import (
        MIN_CONFIDENCE,
        SHAPE_ELLIPSE,
        SHAPE_RECT,
        STYLE_MOSAIC,
        _ERAX_MODEL,
        _ERAX_REPO,
        _ERAX_REVISION,
        _categories_to_anime_classes,
        _categories_to_real_labels,
    )


def _parse_categories(cats_str):
    """Parse comma-separated categories string → frozenset or None."""
    if not cats_str:
        return None
    return frozenset(c.strip() for c in cats_str.split(",") if c.strip())


def _batch_destination(src, output_dir, overwrite, source_root):
    """Resolve one batch destination, mirroring subfolders under *source_root*
    when given so a recursive scan keeps its tree instead of flattening.

    Only computes the path; the directory is created on demand at write time
    so a skipped (clean) image leaves no empty output folder behind.
    """
    if overwrite:
        return src
    target_dir = output_dir
    if source_root:
        rel = os.path.relpath(os.path.dirname(src), source_root)
        if rel != os.curdir and not rel.startswith(os.pardir):
            target_dir = os.path.join(output_dir, rel)
    stem = Path(src).stem
    suffix = Path(src).suffix or ".png"
    dst = os.path.join(target_dir, f"{stem}_censored{suffix}")
    counter = 1
    while os.path.exists(dst):
        dst = os.path.join(target_dir, f"{stem}_censored_{counter}{suffix}")
        counter += 1
    return dst


def _failed_dest(src, failed_dir, scan_root):
    """Mirrored path for a failed image under *failed_dir*, keeping its name."""
    target_dir = failed_dir
    if scan_root:
        rel = os.path.relpath(os.path.dirname(src), scan_root)
        if rel != os.curdir and not rel.startswith(os.pardir):
            target_dir = os.path.join(failed_dir, rel)
    return os.path.join(target_dir, os.path.basename(src))


def _copy_failed(src, failed_dir, scan_root):
    """Best-effort copy of a failed original into the mirrored failed folder."""
    import shutil
    try:
        dst = _failed_dest(src, failed_dir, scan_root)
        _ensure_parent(dst)
        shutil.copy2(src, dst)
    except OSError:
        pass


def _bootstrap_site_packages(site_packages: str) -> None:
    if site_packages and site_packages not in sys.path:
        sys.path.insert(0, site_packages)


def _detect_boxes_real(detector, src, confidence, labels):
    detections = detector.detect(src)
    return [
        tuple(d["box"])
        for d in detections
        if d["class"] in labels and d["score"] >= confidence
    ]


_ANIME_MAKE_LOVE_CLASS = 1
_MAKE_LOVE_CENTER_FRAC = 0.3


def _detect_boxes_anime(model, src, confidence, classes):
    # augment=True → test-time augmentation for better recall (see _detection).
    # Only the requested classes are returned — no automatic dropping.
    results = model(src, conf=confidence, iou=0.3, verbose=False, augment=True)
    boxes = []
    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            if cls not in classes:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            b = (int(x1), int(y1), int(x2), int(y2))
            boxes.append(_shrink_box_center(b, _MAKE_LOVE_CENTER_FRAC)
                         if cls == _ANIME_MAKE_LOVE_CLASS else b)
    return boxes


def _process_one(detector, src, dst, *, block_size, padding,
                  confidence=MIN_CONFIDENCE,
                  expand_pct=0, det_mode="real", anime_model=None,
                  style=STYLE_MOSAIC, categories=None, only_censored=False,
                  shape=SHAPE_RECT, merge_regions=True):
    """Detect + censor one image.  Returns number of regions processed.

    With *only_censored* True a clean image (no detections) is left alone —
    nothing is written to *dst*. *merge_regions* unions overlapping/adjacent
    boxes so a junction between two detected regions is censored."""
    from PIL import Image

    actual_mode = det_mode
    if det_mode == "auto":
        actual_mode = _detect_image_mode(src)

    if actual_mode == "anime":
        classes = _categories_to_anime_classes(categories)
        boxes = _detect_boxes_anime(anime_model, src, confidence, classes)
    else:
        labels = _categories_to_real_labels(categories)
        boxes = _detect_boxes_real(detector, src, confidence, labels)

    if not boxes:
        if not only_censored and os.path.normpath(src) != os.path.normpath(dst):
            import shutil
            _ensure_parent(dst)
            shutil.copy2(src, dst)
        return 0

    img = Image.open(src)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    iw, ih = img.width, img.height
    regions = [_expand_box(*box, padding, expand_pct, iw=iw, ih=ih) for box in boxes]
    for region in regions:
        _censor_region(img, *region, block_size, style=style, shape=shape)
    bridges = _junction_bridges(regions, _merge_gap(regions)) if merge_regions else []
    for bridge in bridges:
        _censor_region(img, *bridge, block_size, style=style, shape=shape)

    ext = Path(dst).suffix.lower()
    fmt_map = {
        ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
        ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
        ".webp": "WEBP",
    }
    fmt = fmt_map.get(ext, "PNG")
    save_img = img
    if fmt == "JPEG" and save_img.mode == "RGBA":
        save_img = save_img.convert("RGB")
    _ensure_parent(dst)
    save_img.save(dst, format=fmt)
    return len(regions) + len(bridges)


def _load_anime_model():
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO
    model_path = hf_hub_download(
        repo_id=_ERAX_REPO, filename=_ERAX_MODEL, revision=_ERAX_REVISION)
    return YOLO(model_path)


def _load_detectors(det_mode):
    """Load the detector(s) for *det_mode* → (nudenet_detector, anime_model)."""
    if det_mode == "auto":
        print("PROGRESS:Loading both detectors (auto mode)...", flush=True)
        from nudenet import NudeDetector
        return NudeDetector(), _load_anime_model()
    if det_mode == "anime":
        print("PROGRESS:Loading EraX anime detector...", flush=True)
        return None, _load_anime_model()
    from nudenet import NudeDetector
    print("PROGRESS:Loading NudeNet detector...", flush=True)
    return NudeDetector(), None


def _process_one_with_fallback(run_for_shape, shape, retries=1):
    """Run *run_for_shape(shape)*, retrying then downgrading to ellipse before
    surfacing the error, so only a genuinely unprocessable image fails."""
    attempts = [shape] * (1 + max(0, retries))
    if shape != SHAPE_ELLIPSE:
        attempts.append(SHAPE_ELLIPSE)
    last_exc = None
    for attempt_shape in attempts:
        try:
            return run_for_shape(attempt_shape)
        except Exception as exc:  # noqa: BLE001 - detector/torch fail in any way; re-raised below
            last_exc = exc
    raise last_exc


def _write_failed_log(failed_dir, failures):
    if failures and failed_dir:
        with open(os.path.join(failed_dir, "censor_failed.log"),
                  "w", encoding="utf-8") as fh:
            for fname, reason in failures:
                fh.write(f"{fname}: {reason}\n")


def _run_single(args):
    if len(args) < 6:
        print("ERROR:single mode requires: input output block_size padding",
              flush=True)
        sys.exit(1)
    input_path, output_path = args[2], args[3]
    block_size, padding = int(args[4]), int(args[5])
    det_mode = args[6] if len(args) > 6 else "real"
    confidence = float(args[7]) if len(args) > 7 else MIN_CONFIDENCE
    expand_pct = int(args[8]) if len(args) > 8 else 0
    style = args[9] if len(args) > 9 else STYLE_MOSAIC
    categories = _parse_categories(args[10]) if len(args) > 10 else None
    shape = args[11] if len(args) > 11 else SHAPE_RECT
    try:
        detector, anime_model = _load_detectors(det_mode)
        print("PROGRESS:Detecting...", flush=True)
        count = _process_one(detector, input_path, output_path,
                             block_size=block_size, padding=padding, confidence=confidence,
                             expand_pct=expand_pct, det_mode=det_mode,
                             anime_model=anime_model, style=style,
                             categories=categories, shape=shape)
        print("PROGRESS:No genitalia detected" if count == 0
              else f"PROGRESS:Censored {count} region(s)", flush=True)
        print(f"OK:{output_path}", flush=True)
    except Exception as exc:  # noqa: BLE001 - child-process boundary: report over the protocol
        print(f"ERROR:{exc}", flush=True)
        sys.exit(1)


def _run_batch(args):
    if len(args) < 7:
        print("ERROR:batch mode requires: json_paths output_dir "
              "block_size padding overwrite", flush=True)
        sys.exit(1)
    json_paths, output_dir = args[2], args[3]
    block_size, padding = int(args[4]), int(args[5])
    overwrite = args[6].lower() == "true"
    det_mode = args[7] if len(args) > 7 else "real"
    confidence = float(args[8]) if len(args) > 8 else MIN_CONFIDENCE
    expand_pct = int(args[9]) if len(args) > 9 else 0
    style = args[10] if len(args) > 10 else STYLE_MOSAIC
    categories = _parse_categories(args[11]) if len(args) > 11 else None
    source_root = args[12] if len(args) > 12 else ""
    only_censored = args[13].lower() == "true" if len(args) > 13 else False
    shape = args[14] if len(args) > 14 else SHAPE_RECT
    failed_dir = args[15] if len(args) > 15 else ""
    scan_root = args[16] if len(args) > 16 else ""
    merge_regions = args[17].lower() != "false" if len(args) > 17 else True

    with open(json_paths, encoding="utf-8") as f:
        paths = json.load(f)
    detector, anime_model = _load_detectors(det_mode)

    success = 0
    failures = []
    total = len(paths)
    for i, src in enumerate(paths):
        name = Path(src).name
        print(f"BATCH_PROGRESS:{i}:{total}:{name}", flush=True)
        try:
            dst = _batch_destination(src, output_dir, overwrite, source_root)
            _process_one_with_fallback(
                lambda shp, _s=src, _d=dst: _process_one(
                    detector, _s, _d, block_size=block_size, padding=padding,
                    confidence=confidence, expand_pct=expand_pct,
                    det_mode=det_mode, anime_model=anime_model,
                    style=style, categories=categories,
                    only_censored=only_censored, shape=shp,
                    merge_regions=merge_regions),
                shape)
            success += 1
        except Exception as exc:  # noqa: BLE001 - one bad image must not end the batch; recorded
            print(f"PROGRESS:Error on {name}: {exc}", flush=True)
            failures.append((name, str(exc)))
            if failed_dir:
                _copy_failed(src, failed_dir, scan_root)

    _write_failed_log(failed_dir, failures)
    print(f"BATCH_OK:{success}:{len(failures)}", flush=True)


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        print("ERROR:Not enough arguments", flush=True)
        sys.exit(1)
    _bootstrap_site_packages(args[0])
    mode = args[1]
    if mode == "single":
        _run_single(args)
    elif mode == "batch":
        _run_batch(args)
    else:
        print(f"ERROR:Unknown mode: {mode}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
