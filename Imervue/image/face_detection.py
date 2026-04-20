"""
Face detection and per-image people tags.

Uses OpenCV's Haar frontal-face cascade — a classical detector that ships
with cv2, needs no extra download, and runs in real-time on a laptop CPU.
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
from dataclasses import dataclass

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
    def from_dict(cls, data: dict) -> "FaceTag":
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


def _load_cascade():
    import cv2
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    if cascade.empty():
        raise RuntimeError(f"failed to load Haar cascade from {cascade_path}")
    return cascade


def detect_faces(
    arr: np.ndarray, options: DetectorOptions | None = None,
) -> list[FaceTag]:
    """Detect faces in an HxWx{3,4} uint8 array. Returns ``FaceTag`` list."""
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
