"""Pure-Python data model for the ``.puppet`` v1 file format.

Qt-free dataclasses so unit tests don't need a ``qapp`` fixture and the
runtime / editor can share the same in-memory representation. See
``FORMAT.md`` for the on-disk schema this maps onto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION: int = 1
"""Bumped when the on-disk schema gains a breaking change."""

BLEND_MODES: tuple[str, ...] = ("normal", "additive", "multiply")
DEFORMER_TYPES: tuple[str, ...] = ("rotation", "warp")
SEGMENT_TYPES: tuple[str, ...] = (
    "linear", "stepped", "inverse-stepped", "cubic-bezier",
)
EXPRESSION_MODES: tuple[str, ...] = ("additive", "multiply", "overwrite")


# ---------------------------------------------------------------------------
# Drawables
# ---------------------------------------------------------------------------

BlendMode = Literal["normal", "additive", "multiply"]


@dataclass
class Drawable:
    """One textured mesh piece. Vertices and UVs are stored in canvas-space
    pixels and the texture's `[0, 1]` UV space respectively."""

    id: str
    texture: str
    vertices: list[tuple[float, float]]
    indices: list[int]
    uvs: list[tuple[float, float]]
    draw_order: int = 0
    blend_mode: BlendMode = "normal"
    clip_mask: str | None = None
    visible: bool = True
    opacity: float = 1.0


# ---------------------------------------------------------------------------
# Deformers
# ---------------------------------------------------------------------------

DeformerType = Literal["rotation", "warp"]


@dataclass
class Deformer:
    """One mesh-deformation node in the rig tree.

    ``form`` is a type-specific dict — kept as a free-form dict rather
    than a tagged union so writers / editors can extend incrementally
    without a new dataclass per deformer kind.
    """

    id: str
    type: DeformerType
    parent: str | None
    drawables: list[str]
    form: dict


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


@dataclass
class ParameterKey:
    """One key form on a parameter — pairs a parameter value with a partial
    snapshot of every deformer's form at that value. Runtime interpolates
    between adjacent keys per-field."""

    value: float
    forms: dict[str, dict] = field(default_factory=dict)
    """Maps deformer id → partial form (e.g. ``{"angle": 0.5}``)."""


@dataclass
class Parameter:
    id: str
    min: float
    max: float
    default: float
    keys: list[ParameterKey] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pose
# ---------------------------------------------------------------------------


@dataclass
class PoseGroup:
    """Mutually-exclusive drawable visibility group."""

    id: str
    drawables: list[str]


# ---------------------------------------------------------------------------
# Motion
# ---------------------------------------------------------------------------

SegmentType = Literal["linear", "stepped", "inverse-stepped", "cubic-bezier"]


@dataclass
class MotionSegment:
    """One curve segment between two key points along a motion track.

    The ``cubic-bezier`` variant carries two extra control points
    (``c0`` / ``c1``); other types leave them ``None``.
    """

    type: SegmentType
    p0: tuple[float, float]
    p1: tuple[float, float]
    c0: tuple[float, float] | None = None
    c1: tuple[float, float] | None = None


@dataclass
class MotionTrack:
    param_id: str
    segments: list[MotionSegment]


@dataclass
class Motion:
    name: str
    duration: float
    loop: bool = False
    tracks: list[MotionTrack] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Expression
# ---------------------------------------------------------------------------

ExpressionMode = Literal["additive", "multiply", "overwrite"]


@dataclass
class ExpressionParam:
    id: str
    value: float
    mode: ExpressionMode = "additive"


@dataclass
class Expression:
    name: str
    params: list[ExpressionParam] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------


@dataclass
class PhysicsParticle:
    mass: float = 1.0
    damping: float = 0.7
    spring: float = 12.0


@dataclass
class PhysicsRig:
    id: str
    input_param: str
    output_param: str
    chain: list[PhysicsParticle] = field(default_factory=list)
    gravity: tuple[float, float] = (0.0, -9.8)


# ---------------------------------------------------------------------------
# Top-level document
# ---------------------------------------------------------------------------


@dataclass
class PuppetDocument:
    """Aggregate root for one ``.puppet`` file.

    Texture image bytes (PNG-encoded) are kept off the dataclass; the IO
    layer reads / writes them alongside the JSON manifest. ``textures``
    is a `{path_in_zip → png_bytes}` map so save / load can round-trip
    the entire archive without an editor having to re-read disk.
    """

    size: tuple[int, int] = (1024, 1024)
    drawables: list[Drawable] = field(default_factory=list)
    deformers: list[Deformer] = field(default_factory=list)
    parameters: list[Parameter] = field(default_factory=list)
    pose_groups: list[PoseGroup] = field(default_factory=list)
    motions: list[Motion] = field(default_factory=list)
    expressions: list[Expression] = field(default_factory=list)
    physics_rigs: list[PhysicsRig] = field(default_factory=list)
    textures: dict[str, bytes] = field(default_factory=dict)

    # ---- helpers ---------------------------------------------------------

    def drawable(self, id_: str) -> Drawable | None:
        for d in self.drawables:
            if d.id == id_:
                return d
        return None

    def deformer(self, id_: str) -> Deformer | None:
        for d in self.deformers:
            if d.id == id_:
                return d
        return None

    def parameter(self, id_: str) -> Parameter | None:
        for p in self.parameters:
            if p.id == id_:
                return p
        return None
