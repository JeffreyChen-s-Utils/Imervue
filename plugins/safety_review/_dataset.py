"""YOLO training-dataset export for the safety_review plugin.

Turns hand-labelled boxes from the manual editor into an ultralytics YOLO
dataset — ``images/`` + ``labels/`` (one ``.txt`` of ``cls cx cy w h`` per
image) + a ``data.yaml`` naming the classes — so the user can accumulate a
dataset by reviewing images and then fine-tune a model on it.

``to_yolo_lines`` is pure and unit-tested; the writers do small, testable
filesystem work under a temp directory.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def to_yolo_lines(labeled_regions, img_w: int, img_h: int) -> list[str]:
    """``[((x1,y1,x2,y2), cls), …]`` + image size → YOLO label lines.

    Each line is ``cls cx cy w h`` with the centre and size normalised to
    ``[0, 1]``. Zero-area boxes and a zero-size image are skipped.
    """
    if img_w <= 0 or img_h <= 0:
        return []
    lines = []
    for (x1, y1, x2, y2), cls in labeled_regions:
        w, h = x2 - x1, y2 - y1
        if w <= 0 or h <= 0:
            continue
        cx = (x1 + x2) / 2 / img_w
        cy = (y1 + y2) / 2 / img_h
        lines.append(f"{int(cls)} {cx:.6f} {cy:.6f} {w / img_w:.6f} {h / img_h:.6f}")
    return lines


def data_yaml_text(classes) -> str:
    """ultralytics ``data.yaml`` body for *classes* (index = class id)."""
    names = "\n".join(f"  {i}: {name}" for i, name in enumerate(classes))
    return (
        "path: .\n"
        "train: images\n"
        "val: images\n"
        f"nc: {len(classes)}\n"
        "names:\n"
        f"{names}\n"
    )


def write_data_yaml(dataset_dir: str, classes) -> None:
    Path(dataset_dir).mkdir(parents=True, exist_ok=True)
    with open(os.path.join(dataset_dir, "data.yaml"), "w", encoding="utf-8") as fh:
        fh.write(data_yaml_text(classes))


def export_label(dataset_dir: str, image_path: str, labeled_regions,
                 img_w: int, img_h: int, classes) -> int:
    """Copy *image_path* into ``images/`` and write its YOLO label into
    ``labels/``, refreshing ``data.yaml``. Returns the number of labels
    written (an image with no boxes still writes an empty label, a valid
    "negative" sample for training)."""
    images_dir = Path(dataset_dir) / "images"
    labels_dir = Path(dataset_dir) / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(image_path).stem
    dst_image = images_dir / (stem + Path(image_path).suffix)
    if os.path.normpath(str(dst_image)) != os.path.normpath(image_path):
        shutil.copy2(image_path, dst_image)

    lines = to_yolo_lines(labeled_regions, img_w, img_h)
    with open(labels_dir / (stem + ".txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        if lines:
            fh.write("\n")

    write_data_yaml(dataset_dir, classes)
    return len(lines)
