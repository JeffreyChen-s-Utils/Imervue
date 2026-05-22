"""Non-destructive image annotations stored as a JSON sidecar.

Reviewers and creators often want to mark up an image — draw an
arrow pointing at the problem, circle a face, add a text note —
without modifying the source file. This module is the storage +
data-model layer; the overlay that *draws* the annotations on the
viewer lives in
:mod:`Imervue.gpu_image_view.annotation_overlay`.

Schema (one file per image, ``<image>.annotations.json``):

.. code-block:: json

    {
        "schema_version": 1,
        "annotations": [
            {
                "kind": "arrow",
                "points": [[0.20, 0.30], [0.55, 0.42]],
                "color": "#ff3030",
                "stroke_px": 3.0,
                "text": ""
            }
        ]
    }

Coordinates are **normalised** to ``[0, 1] x [0, 1]`` so a saved
annotation survives image resize / aspect adjustments — the
overlay denormalises against the image's current displayed size
at paint time.

Five kinds (extensible — see :data:`SUPPORTED_KINDS`):

* ``arrow``    — two-point line with arrowhead at the second point
* ``rect``     — two opposing corners
* ``circle``   — centre + radius point (the magnitude of point[1] -
  point[0] is the radius)
* ``freehand`` — N points, drawn as a polyline
* ``text``     — single anchor point + ``text`` string

Pure module — no Qt, no IO outside of the documented sidecar path.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("Imervue.image.annotations")

SCHEMA_VERSION: int = 1
"""Bumps on schema-breaking changes. Older files keep working
because the loader merges defaults; newer files load on older
runtimes by ignoring unknown fields."""

SUPPORTED_KINDS: tuple[str, ...] = (
    "arrow", "rect", "circle", "freehand", "text",
)
"""Annotation kinds the renderer knows how to draw. The loader
drops unknown kinds rather than refusing the whole file, so a
forward-incompatible sidecar still surfaces what it can."""

DEFAULT_COLOR: str = "#ff3030"
"""Bright red — the canonical review-markup colour. Visible on
most photo subject matter without prior tuning."""

DEFAULT_STROKE_PX: float = 3.0
"""Three-pixel stroke at 1:1 zoom — heavy enough to read on a
mid-DPI display, light enough not to drown the underlying image."""


@dataclass(frozen=True)
class Annotation:
    """One mark on the image. Immutable so callers can pass these
    around freely — mutating annotations creates a new instance
    via :func:`dataclasses.replace`."""

    kind: str
    points: tuple[tuple[float, float], ...]
    color: str = DEFAULT_COLOR
    stroke_px: float = DEFAULT_STROKE_PX
    text: str = ""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "points": [list(p) for p in self.points],
            "color": self.color,
            "stroke_px": float(self.stroke_px),
            "text": self.text,
        }


@dataclass
class AnnotationLayer:
    """All annotations attached to one image. Mutable: the overlay
    appends / removes as the user draws or selects + deletes."""

    annotations: list[Annotation] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    def is_empty(self) -> bool:
        return not self.annotations

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "annotations": [a.to_dict() for a in self.annotations],
        }


def sidecar_path_for(image_path: str | Path) -> Path:
    """Return ``<image>.annotations.json`` next to the image file."""
    p = Path(image_path)
    return p.with_name(p.name + ".annotations.json")


def has_sidecar(image_path: str | Path) -> bool:
    """``True`` when an annotation sidecar exists for ``image_path``."""
    return sidecar_path_for(image_path).is_file()


def load(image_path: str | Path) -> AnnotationLayer:
    """Read the sidecar for ``image_path``. Missing or malformed
    files return an empty layer — the viewer should show no
    annotations rather than refusing to display the image."""
    path = sidecar_path_for(image_path)
    if not path.is_file():
        return AnnotationLayer()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("annotation sidecar unreadable %s: %s", path, exc)
        return AnnotationLayer()
    return _coerce_layer(raw)


def save(image_path: str | Path, layer: AnnotationLayer) -> Path:
    """Write ``layer`` to the sidecar. Empty layers delete the
    sidecar file (so a "remove last annotation" action doesn't
    leave junk files in the user's folder)."""
    path = sidecar_path_for(image_path)
    if layer.is_empty():
        if path.exists():
            try:
                path.unlink()
            except OSError as exc:
                logger.warning("can't remove empty sidecar %s: %s", path, exc)
        return path
    path.write_text(
        json.dumps(layer.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _coerce_layer(raw: object) -> AnnotationLayer:
    """Validate + normalise the loaded JSON object. Same forgiving
    rule the pet-script loader uses: a malformed entry drops
    silently, not "whole file lost"."""
    if not isinstance(raw, dict):
        return AnnotationLayer()
    annotations_raw = raw.get("annotations", [])
    if not isinstance(annotations_raw, list):
        return AnnotationLayer()
    out: list[Annotation] = []
    for entry in annotations_raw:
        coerced = _coerce_annotation(entry)
        if coerced is not None:
            out.append(coerced)
    try:
        version = int(raw.get("schema_version", SCHEMA_VERSION))
    except (TypeError, ValueError):
        version = SCHEMA_VERSION
    return AnnotationLayer(annotations=out, schema_version=version)


def _coerce_annotation(raw: object) -> Annotation | None:
    if not isinstance(raw, dict):
        return None
    kind = raw.get("kind")
    if kind not in SUPPORTED_KINDS:
        return None
    points = _coerce_points(raw.get("points"))
    if not _points_valid_for_kind(kind, points):
        return None
    color = raw.get("color", DEFAULT_COLOR)
    if not isinstance(color, str) or not color:
        color = DEFAULT_COLOR
    try:
        stroke_px = float(raw.get("stroke_px", DEFAULT_STROKE_PX))
    except (TypeError, ValueError):
        stroke_px = DEFAULT_STROKE_PX
    stroke_px = max(0.5, min(50.0, stroke_px))
    text = raw.get("text", "")
    if not isinstance(text, str):
        text = ""
    return Annotation(
        kind=kind,
        points=points,
        color=color,
        stroke_px=stroke_px,
        text=text,
    )


def _coerce_points(raw: object) -> tuple[tuple[float, float], ...]:
    """Filter to a tuple of (x, y) float pairs each clamped to the
    ``[0, 1]`` normalised range. Bogus entries drop."""
    if not isinstance(raw, list):
        return ()
    out: list[tuple[float, float]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        try:
            x = max(0.0, min(1.0, float(item[0])))
            y = max(0.0, min(1.0, float(item[1])))
        except (TypeError, ValueError):
            continue
        out.append((x, y))
    return tuple(out)


def _points_valid_for_kind(kind: str, points: tuple[tuple[float, float], ...]) -> bool:
    """Each annotation kind has a minimum point count below which
    it's useless. arrow / rect / circle need two; freehand needs
    two; text needs one."""
    if kind in ("arrow", "rect", "circle", "freehand"):
        return len(points) >= 2
    if kind == "text":
        return len(points) >= 1
    return False


# ---------------------------------------------------------------
# Coordinate-space helpers
# ---------------------------------------------------------------


def normalize_point(
    point: tuple[float, float],
    image_size: tuple[int, int],
) -> tuple[float, float]:
    """Convert pixel-space ``(x, y)`` to normalised ``[0, 1]``
    coordinates against an image of ``image_size`` pixels.

    Defensive against zero-sized images (returns ``(0, 0)``); the
    caller should typically have checked, but the helper shouldn't
    raise on a stale image reference."""
    width, height = image_size
    if width <= 0 or height <= 0:
        return (0.0, 0.0)
    nx = max(0.0, min(1.0, float(point[0]) / float(width)))
    ny = max(0.0, min(1.0, float(point[1]) / float(height)))
    return (nx, ny)


def denormalize_point(
    norm_point: tuple[float, float],
    image_size: tuple[int, int],
) -> tuple[float, float]:
    """Inverse of :func:`normalize_point`. Pixel coordinates for
    the overlay renderer to draw at."""
    width, height = image_size
    return (
        max(0.0, min(float(width), float(norm_point[0]) * float(width))),
        max(0.0, min(float(height), float(norm_point[1]) * float(height))),
    )
