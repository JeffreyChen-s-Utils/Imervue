"""
Face detection and per-image people tags.

Uses OpenCV's Haar frontal-face cascade — a classical detector that ships
with the OpenCV 4 wheels (OpenCV 5 dropped it), needs no extra download,
and runs in real-time on a laptop CPU.
Results are not as accurate as modern CNN detectors but perfectly
adequate for a "show me faces in this photo" assist feature.

A :class:`FaceTag` pairs a detected region with an optional person name,
so the results can be persisted as part of a per-image sidecar (see
``face_tags_store``) and later surfaced through the hierarchical-tags
panel. Face *recognition* (auto-matching faces across images) is out of
scope here — we provide detection + manual naming only.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger("Imervue.face_detection")


@dataclass
class FaceTag:
    """A single detected or user-labelled face region."""

    x: int
    y: int
    w: int
    h: int
    name: str = ""

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> FaceTag:
        return cls(
            x=int(data["x"]),
            y=int(data["y"]),
            w=int(data["w"]),
            h=int(data["h"]),
            name=str(data.get("name", "")),
        )


@dataclass
class DetectorOptions:
    """Parameters for the Haar detector."""

    min_size: int = 32              # ignore faces smaller than this many pixels
    scale_factor: float = 1.1       # pyramid downscale
    min_neighbors: int = 4          # higher = fewer false positives
    max_faces: int = 64


_CASCADE_FILE = "haarcascade_frontalface_default.xml"


class FaceDetectorUnavailableError(RuntimeError):
    """The installed OpenCV has no Haar face detector.

    OpenCV 5 moved ``CascadeClassifier`` to opencv_contrib and no longer ships
    the cascade XML files in any wheel, so detection needs OpenCV 4.
    """


def _load_cascade():
    """The frontal-face cascade, read through Python so any install path works.

    ``cv2.CascadeClassifier(path)`` can't open a path with non-ASCII
    characters on Windows — OpenCV installed in a user folder with a Chinese
    name, or an Imervue build unpacked into such a folder — and came back
    empty, so detection always failed. The XML is read here and handed to
    OpenCV from memory instead.
    """
    import cv2
    classifier = getattr(cv2, "CascadeClassifier", None)
    data_dir = getattr(getattr(cv2, "data", None), "haarcascades", None)
    cascade_path = os.path.join(data_dir, _CASCADE_FILE) if data_dir else ""
    if classifier is None or not os.path.isfile(cascade_path):
        raise FaceDetectorUnavailableError(
            f"OpenCV {getattr(cv2, '__version__', '?')} has no Haar face "
            f"cascade; install OpenCV 4 (pip install \"opencv-python<5\")",
        )
    failure = f"failed to load Haar cascade from {cascade_path}"
    try:
        xml = Path(cascade_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(failure) from exc
    storage = cv2.FileStorage(xml, cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
    cascade = classifier()
    if not cascade.read(storage.getFirstTopLevelNode()) or cascade.empty():
        raise RuntimeError(failure)
    return cascade


def detect_faces(
    arr: np.ndarray, options: DetectorOptions | None = None,
) -> list[FaceTag]:
    """Detect faces in an HxWx{3,4} uint8 array. Returns ``FaceTag`` list.

    Raises ``ImportError`` without cv2 and :class:`FaceDetectorUnavailableError`
    when the installed OpenCV has no Haar cascade (OpenCV 5).
    """
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise ValueError("detect_faces expects HxWx3 RGB or HxWx4 RGBA uint8")
    opts = options or DetectorOptions()

    import cv2
    rgb = arr[..., :3]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    cascade = _load_cascade()
    rects = cascade.detectMultiScale(
        gray,
        scaleFactor=max(1.01, opts.scale_factor),
        minNeighbors=max(1, opts.min_neighbors),
        minSize=(opts.min_size, opts.min_size),
    )
    if rects is None or len(rects) == 0:
        return []
    rects = sorted(
        ((int(x), int(y), int(w), int(h)) for x, y, w, h in rects),
        key=lambda r: r[2] * r[3],
        reverse=True,
    )[: opts.max_faces]
    return [FaceTag(x=x, y=y, w=w, h=h) for x, y, w, h in rects]


def face_tags_from_dict_list(items: list[dict]) -> list[FaceTag]:
    out: list[FaceTag] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            out.append(FaceTag.from_dict(it))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def face_tags_to_dict_list(tags: list[FaceTag]) -> list[dict]:
    return [t.to_dict() for t in tags]
