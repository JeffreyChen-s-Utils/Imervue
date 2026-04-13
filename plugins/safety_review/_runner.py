"""Subprocess runner for safety review plugin.

Usage (frozen env):
    python _runner.py <site_packages> single <input> <output> <block_size> <padding> [<mode> <confidence> <expand_pct>]
    python _runner.py <site_packages> batch  <json_paths> <output_dir> <block_size> <padding> <overwrite> [<mode> <confidence> <expand_pct>]

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

# -----------------------------------------------------------------------
# NudeNet labels (real-photo mode)
# -----------------------------------------------------------------------
MOSAIC_LABELS = frozenset({
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
})

# EraX YOLO classes (anime mode): 0=anus, 1=make_love, 2=nipple, 3=penis, 4=vagina
ANIME_MOSAIC_CLASSES = frozenset({0, 3, 4})  # anus, penis, vagina

_ERAX_REPO = "erax-ai/EraX-Anti-NSFW-V1.1"
_ERAX_MODEL = "erax-anti-nsfw-yolo11m-v1.1.pt"

MIN_CONFIDENCE = 0.25


def _bootstrap_site_packages(site_packages: str) -> None:
    if site_packages and site_packages not in sys.path:
        sys.path.insert(0, site_packages)


def _expand_box(x1, y1, x2, y2, padding, expand_pct, iw, ih):
    bw = x2 - x1
    bh = y2 - y1
    if expand_pct > 0:
        ex = int(bw * expand_pct / 100)
        ey = int(bh * expand_pct / 100)
        x1 -= ex; y1 -= ey; x2 += ex; y2 += ey
    if padding > 0:
        x1 -= padding; y1 -= padding; x2 += padding; y2 += padding
    return max(0, x1), max(0, y1), min(iw, x2), min(ih, y2)


def _mosaic_region(img, x1, y1, x2, y2, block_size):
    from PIL import Image

    w = x2 - x1
    h = y2 - y1
    if w <= 0 or h <= 0:
        return
    region = img.crop((x1, y1, x2, y2))
    bs = max(2, block_size)
    small = region.resize(
        (max(1, w // bs), max(1, h // bs)),
        resample=Image.Resampling.BILINEAR,
    )
    mosaic = small.resize((w, h), resample=Image.Resampling.NEAREST)
    img.paste(mosaic, (x1, y1))


def _detect_boxes_real(detector, src, confidence, labels):
    detections = detector.detect(src)
    return [
        tuple(d["box"])
        for d in detections
        if d["class"] in labels and d["score"] >= confidence
    ]


def _detect_boxes_anime(model, src, confidence, classes):
    results = model(src, conf=confidence, iou=0.3, verbose=False)
    boxes = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            if cls_id in classes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                boxes.append((int(x1), int(y1), int(x2), int(y2)))
    return boxes


def _process_one(detector, src, dst, block_size, padding,
                  confidence=MIN_CONFIDENCE, labels=MOSAIC_LABELS,
                  expand_pct=0, det_mode="real", anime_model=None):
    """Detect + mosaic one image.  Returns number of regions mosaiced."""
    from PIL import Image

    if det_mode == "anime":
        boxes = _detect_boxes_anime(anime_model, src, confidence,
                                     ANIME_MOSAIC_CLASSES)
    else:
        boxes = _detect_boxes_real(detector, src, confidence, labels)

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
        _mosaic_region(img, x1, y1, x2, y2, block_size)

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
    save_img.save(dst, format=fmt)
    return len(boxes)


def _load_anime_model():
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO
    model_path = hf_hub_download(repo_id=_ERAX_REPO, filename=_ERAX_MODEL)
    return YOLO(model_path)


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        print("ERROR:Not enough arguments", flush=True)
        sys.exit(1)

    site_packages = args[0]
    mode = args[1]
    _bootstrap_site_packages(site_packages)

    if mode == "single":
        if len(args) < 6:
            print("ERROR:single mode requires: input output block_size padding",
                  flush=True)
            sys.exit(1)
        input_path, output_path = args[2], args[3]
        block_size, padding = int(args[4]), int(args[5])
        det_mode = args[6] if len(args) > 6 else "real"
        confidence = float(args[7]) if len(args) > 7 else MIN_CONFIDENCE
        expand_pct = int(args[8]) if len(args) > 8 else 0
        try:
            detector = None
            anime_model = None
            if det_mode == "anime":
                print("PROGRESS:Loading EraX anime detector...", flush=True)
                anime_model = _load_anime_model()
            else:
                from nudenet import NudeDetector
                print("PROGRESS:Loading NudeNet detector...", flush=True)
                detector = NudeDetector()

            print("PROGRESS:Detecting...", flush=True)
            count = _process_one(detector, input_path, output_path,
                                 block_size, padding,
                                 confidence=confidence,
                                 labels=MOSAIC_LABELS,
                                 expand_pct=expand_pct,
                                 det_mode=det_mode,
                                 anime_model=anime_model)
            if count == 0:
                print("PROGRESS:No genitalia detected", flush=True)
            else:
                print(f"PROGRESS:Mosaiced {count} region(s)", flush=True)
            print(f"OK:{output_path}", flush=True)
        except Exception as exc:
            print(f"ERROR:{exc}", flush=True)
            sys.exit(1)

    elif mode == "batch":
        if len(args) < 7:
            print("ERROR:batch mode requires: json_paths output_dir "
                  "block_size padding overwrite", flush=True)
            sys.exit(1)
        json_paths = args[2]
        output_dir = args[3]
        block_size = int(args[4])
        padding = int(args[5])
        overwrite = args[6].lower() == "true"
        det_mode = args[7] if len(args) > 7 else "real"
        confidence = float(args[8]) if len(args) > 8 else MIN_CONFIDENCE
        expand_pct = int(args[9]) if len(args) > 9 else 0

        with open(json_paths, encoding="utf-8") as f:
            paths = json.load(f)

        detector = None
        anime_model = None
        if det_mode == "anime":
            print("PROGRESS:Loading EraX anime detector...", flush=True)
            anime_model = _load_anime_model()
        else:
            from nudenet import NudeDetector
            print("PROGRESS:Loading NudeNet detector...", flush=True)
            detector = NudeDetector()

        success = 0
        failed = 0
        total = len(paths)

        for i, src in enumerate(paths):
            name = Path(src).name
            print(f"BATCH_PROGRESS:{i}:{total}:{name}", flush=True)
            try:
                if overwrite:
                    dst = src
                else:
                    stem = Path(src).stem
                    suffix = Path(src).suffix or ".png"
                    dst = str(Path(output_dir) / f"{stem}_censored{suffix}")
                    counter = 1
                    while os.path.exists(dst):
                        dst = str(
                            Path(output_dir)
                            / f"{stem}_censored_{counter}{suffix}"
                        )
                        counter += 1
                _process_one(detector, src, dst, block_size, padding,
                             confidence=confidence, labels=MOSAIC_LABELS,
                             expand_pct=expand_pct, det_mode=det_mode,
                             anime_model=anime_model)
                success += 1
            except Exception as exc:
                print(f"PROGRESS:Error on {name}: {exc}", flush=True)
                failed += 1

        print(f"BATCH_OK:{success}:{failed}", flush=True)
    else:
        print(f"ERROR:Unknown mode: {mode}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
