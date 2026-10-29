"""
Annotation data model.

No Qt imports: this module can be imported from worker threads and exercised
from unit tests without a display. The interactive canvas in
``annotation_dialog.py`` has its own QPainter-based drawing path for live
preview, while the headless PIL bake lives in ``annotation_render.py`` (fonts
in ``annotation_fonts.py``, freehand brushes in ``annotation_brushes.py``) —
the two paths aim to be visually equivalent but don't share code because
QPainter and PIL's coordinate / antialiasing conventions differ enough to make
sharing brittle. ``bake`` and ``jitter_seed`` stay importable from here.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from Imervue.gui.annotation_brushes import jitter_seed
from Imervue.gui.annotation_render import bake
from Imervue.system.atomic_write import write_text_atomically

__all__ = [
    "ALL_BRUSHES", "ALL_KINDS", "Annotation", "AnnotationKind", "AnnotationProject",
    "BrushType", "KIND_ARROW", "KIND_BLUR", "KIND_FREEHAND", "KIND_LINE",
    "KIND_MOSAIC", "KIND_TEXT", "TOOL_CROP", "TOOL_MOVE", "TOOL_SELECT",
    "bake", "jitter_seed",
]

AnnotationKind = Literal[
    "rect",
    "ellipse",
    "line",
    "arrow",
    "freehand",
    "text",
    "mosaic",
    "blur",
]

# Freehand brush presets — each one renders the same points list differently
# so the user can pick a look (pen / marker / pencil / highlighter / spray).
# Default is ``pen`` so existing annotations keep their previous appearance.
BrushType = Literal[
    "pen", "marker", "pencil", "highlighter", "spray",
    "calligraphy", "watercolor", "charcoal", "crayon",
]

ALL_BRUSHES: tuple[BrushType, ...] = (
    "pen", "marker", "pencil", "highlighter", "spray",
    "calligraphy", "watercolor", "charcoal", "crayon",
)

ALL_KINDS: tuple[AnnotationKind, ...] = (
    "rect", "ellipse", "line", "arrow",
    "freehand", "text", "mosaic", "blur",
)

# Kind, brush and canvas-tool names the annotation canvas compares against —
# named once so a typo surfaces as a NameError instead of a silent mismatch.
KIND_FREEHAND: AnnotationKind = "freehand"
KIND_TEXT: AnnotationKind = "text"
KIND_MOSAIC: AnnotationKind = "mosaic"
KIND_BLUR: AnnotationKind = "blur"
KIND_LINE: AnnotationKind = "line"
KIND_ARROW: AnnotationKind = "arrow"
TOOL_CROP = "crop"
TOOL_SELECT = "select"
TOOL_MOVE = "move"


@dataclass
class Annotation:
    kind: AnnotationKind
    points: list[tuple[int, int]] = field(default_factory=list)
    color: tuple[int, int, int, int] = (255, 0, 0, 255)
    stroke_width: int = 3
    filled: bool = False
    text: str = ""
    font_size: int = 24
    block_size: int = 16   # mosaic: block pixel size
    blur_radius: int = 10  # blur: gaussian radius
    # Freehand brush parameters. Ignored for non-freehand kinds. Defaults
    # match the original plain-pen behavior so pre-brush projects load
    # unchanged.
    brush_type: BrushType = "pen"
    opacity: int = 100       # 0..100 percent — multiplies color alpha
    spacing: int = 8         # px — only used by spray brush
    font_family: str = ""    # text: Qt font family name (empty = system default)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "points": [list(p) for p in self.points],
            "color": list(self.color),
            "stroke_width": self.stroke_width,
            "filled": self.filled,
            "text": self.text,
            "font_size": self.font_size,
            "block_size": self.block_size,
            "blur_radius": self.blur_radius,
            "brush_type": self.brush_type,
            "opacity": self.opacity,
            "spacing": self.spacing,
            "font_family": self.font_family,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Annotation:
        return cls(
            kind=d["kind"],
            points=[tuple(p) for p in d.get("points", [])],
            color=tuple(d.get("color", [255, 0, 0, 255])),
            stroke_width=int(d.get("stroke_width", 3)),
            filled=bool(d.get("filled", False)),
            text=d.get("text", ""),
            font_size=int(d.get("font_size", 24)),
            block_size=int(d.get("block_size", 16)),
            blur_radius=int(d.get("blur_radius", 10)),
            brush_type=d.get("brush_type", "pen"),
            opacity=int(d.get("opacity", 100)),
            spacing=int(d.get("spacing", 8)),
            font_family=d.get("font_family", ""),
            id=d.get("id") or uuid.uuid4().hex[:12],
        )

    def bounding_box(self) -> tuple[int, int, int, int]:
        """Return (x1, y1, x2, y2) covering all points (normalized so x1<=x2)."""
        if not self.points:
            return (0, 0, 0, 0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def normalized_rect(self) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) — positive width/height — from the bounding box."""
        x1, y1, x2, y2 = self.bounding_box()
        return (x1, y1, x2 - x1, y2 - y1)


@dataclass
class AnnotationProject:
    """Serializable project: source path + image size + annotation list.

    Written by "Save Project..." in the annotation dialog. The schema carries
    an explicit ``version`` so future loaders can detect older / newer files
    and decide how to handle unknown fields instead of crashing.
    """
    version: int = 1
    source_path: str = ""
    source_size: tuple[int, int] = (0, 0)
    annotations: list[Annotation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source_path": self.source_path,
            "source_size": list(self.source_size),
            "annotations": [a.to_dict() for a in self.annotations],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AnnotationProject:
        return cls(
            version=int(d.get("version", 1)),
            source_path=d.get("source_path", ""),
            source_size=tuple(d.get("source_size", [0, 0])),
            annotations=[Annotation.from_dict(a) for a in d.get("annotations", [])],
        )

    def save(self, path: str | Path) -> None:
        """Write the project to *path* in one step, so a failed save keeps the previous one."""
        write_text_atomically(path, json.dumps(self.to_dict(), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: str | Path) -> AnnotationProject:
        # utf-8-sig: a project file saved with a BOM by a text editor still loads.
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return cls.from_dict(data)
