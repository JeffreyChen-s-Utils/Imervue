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

The argv parsing lives in ``_runner_args`` and the per-image batch bookkeeping
(destinations, shape fallback, failed folder) in ``_runner_batch``; both are
loaded as siblings like ``_censor_core`` and re-exported here.
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
    from safety_review._constants import (
        MIN_CONFIDENCE,
        SHAPE_RECT,
        STYLE_MOSAIC,
        _ERAX_MODEL,
        _ERAX_REPO,
        _ERAX_REVISION,
        _categories_to_anime_classes,
        _categories_to_real_labels,
    )
    from safety_review._runner_args import (
        _batch_options,
        _bootstrap_site_packages,
        _parse_categories,
        _single_options,
    )
    from safety_review._runner_batch import (
        _batch_destination,
        _copy_failed,
        _failed_dest,
        _process_one_with_fallback,
        _write_failed_log,
    )
else:             # run as a script next to its siblings
    from _censor_core import (
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
    from _constants import (
        MIN_CONFIDENCE,
        SHAPE_RECT,
        STYLE_MOSAIC,
        _ERAX_MODEL,
        _ERAX_REPO,
        _ERAX_REVISION,
        _categories_to_anime_classes,
        _categories_to_real_labels,
    )
    from _runner_args import (
        _batch_options,
        _bootstrap_site_packages,
        _parse_categories,
        _single_options,
    )
    from _runner_batch import (
        _batch_destination,
        _copy_failed,
        _failed_dest,
        _process_one_with_fallback,
        _write_failed_log,
    )

__all__ = [
    "_ERAX_MODEL",
    "_ERAX_REPO",
    "_ERAX_REVISION",
    "_AnyPathDetector",
    "_batch_destination",
    "_bootstrap_site_packages",
    "_censor_region",
    "_copy_failed",
    "_detect_boxes_anime",
    "_detect_boxes_real",
    "_detect_image_mode",
    "_expand_box",
    "_failed_dest",
    "_junction_bridges",
    "_load_anime_model",
    "_load_detectors",
    "_merge_gap",
    "_parse_categories",
    "_process_one",
    "_process_one_with_fallback",
    "_run_batch",
    "_run_single",
    "_save_as",
    "_shrink_box_center",
    "_write_failed_log",
    "main",
]


def _detect_boxes_real(detector, src, confidence, labels):
    detections = detector.detect(src)
    return [
        _nudenet_corners(d["box"])
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

    img = _open_upright(src)   # the detectors' boxes are in upright coordinates

    iw, ih = img.width, img.height
    regions = [_expand_box(*box, padding, expand_pct, iw=iw, ih=ih) for box in boxes]
    for region in regions:
        _censor_region(img, *region, block_size, style=style, shape=shape)
    bridges = _junction_bridges(regions, _merge_gap(regions)) if merge_regions else []
    for bridge in bridges:
        _censor_region(img, *bridge, block_size, style=style, shape=shape)

    _save_as(img, dst)
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
        return _AnyPathDetector(NudeDetector()), _load_anime_model()
    if det_mode == "anime":
        print("PROGRESS:Loading EraX anime detector...", flush=True)
        return None, _load_anime_model()
    from nudenet import NudeDetector
    print("PROGRESS:Loading NudeNet detector...", flush=True)
    return _AnyPathDetector(NudeDetector()), None


def _run_single(args):
    if len(args) < 6:
        print("ERROR:single mode requires: input output block_size padding",
              flush=True)
        sys.exit(1)
    opts = _single_options(args)
    try:
        detector, anime_model = _load_detectors(opts.det_mode)
        print("PROGRESS:Detecting...", flush=True)
        count = _process_one(detector, opts.input_path, opts.output_path,
                             block_size=opts.block_size, padding=opts.padding,
                             confidence=opts.confidence,
                             expand_pct=opts.expand_pct, det_mode=opts.det_mode,
                             anime_model=anime_model, style=opts.style,
                             categories=opts.categories, shape=opts.shape)
        print("PROGRESS:No genitalia detected" if count == 0
              else f"PROGRESS:Censored {count} region(s)", flush=True)
        print(f"OK:{opts.output_path}", flush=True)
    except Exception as exc:  # noqa: BLE001 - child-process boundary: report over the protocol
        print(f"ERROR:{exc}", flush=True)
        sys.exit(1)


def _run_batch(args):
    if len(args) < 7:
        print("ERROR:batch mode requires: json_paths output_dir "
              "block_size padding overwrite", flush=True)
        sys.exit(1)
    opts = _batch_options(args)

    with open(opts.json_paths, encoding="utf-8") as f:
        paths = json.load(f)
    detector, anime_model = _load_detectors(opts.det_mode)

    success = 0
    failures = []
    total = len(paths)
    for i, src in enumerate(paths):
        name = Path(src).name
        print(f"BATCH_PROGRESS:{i}:{total}:{name}", flush=True)
        try:
            dst = _batch_destination(src, opts.output_dir, opts.overwrite,
                                     opts.source_root)
            _process_one_with_fallback(
                lambda shp, _s=src, _d=dst: _process_one(
                    detector, _s, _d, block_size=opts.block_size,
                    padding=opts.padding, confidence=opts.confidence,
                    expand_pct=opts.expand_pct, det_mode=opts.det_mode,
                    anime_model=anime_model, style=opts.style,
                    categories=opts.categories,
                    only_censored=opts.only_censored, shape=shp,
                    merge_regions=opts.merge_regions),
                opts.shape)
            success += 1
        except Exception as exc:  # noqa: BLE001 - one bad image must not end the batch; recorded
            print(f"PROGRESS:Error on {name}: {exc}", flush=True)
            failures.append((name, str(exc)))
            if opts.failed_dir:
                _copy_failed(src, opts.failed_dir, opts.scan_root)

    _write_failed_log(opts.failed_dir, failures)
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
