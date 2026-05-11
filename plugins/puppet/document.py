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
DEFORMER_TYPES: tuple[str, ...] = ("rotation", "warp", "bone_rotation")
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
    pixels and the texture's `[0, 1]` UV space respectively.

    ``bone_weights``, when present, drives skeletal LBS (linear blend
    skinning): it maps a bone id to one weight per vertex in ``[0, 1]``.
    Per vertex, weights across all bones should sum to ``1`` (the
    runtime renormalises if they don't, and a vertex with all-zero
    weights stays at its rest position). Drawables without
    ``bone_weights`` behave as before — every vertex follows any
    rotation / warp deformer rigidly."""

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
    bone_weights: dict[str, list[float]] | None = None
    opacity_keys: list[dict] | None = None
    """Parameter-driven opacity curves. Each entry has the form
    ``{"parameter": str, "stops": [{"value": float, "alpha": float}, ...]}``.
    Multiple entries multiply (so two curves both at ``0.5`` yield ``0.25``).
    Used for cross-fading between pose variants — e.g. an ``arm_drop``
    drawable can be transparent at neutral swing and opaque at full drop,
    while an ``arm_neutral`` drawable does the opposite, giving a smooth
    blend through the parameter's range."""
    multiply_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    """Static per-channel multiplier applied before any
    ``multiply_color_keys`` curves. ``(1, 1, 1)`` is the no-tint
    default; ``(1, 0.6, 0.6)`` tints the drawable rosy."""
    multiply_color_keys: list[dict] | None = None
    """Parameter-driven multiply-color curves. Each entry has the form
    ``{"parameter": str, "stops": [{"value": float, "color": [r, g, b]}, ...]}``.
    Multiple entries multiply channel-wise (so two curves each tinting
    by ``(1, 0.5, 0.5)`` yield ``(1, 0.25, 0.25)``). Used for
    parameter-driven blush (``ParamCheek``), skin flush, hover glow,
    etc."""


# ---------------------------------------------------------------------------
# Deformers
# ---------------------------------------------------------------------------

DeformerType = Literal["rotation", "warp", "bone_rotation"]


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
# Parameter blends (multi-axis keyforms)
# ---------------------------------------------------------------------------


@dataclass
class BlendKey:
    """One key inside a :class:`ParameterBlend`. ``coords`` lines up
    with the blend's ``parameters`` list: e.g. for a blend across
    ``(ParamAngleX, ParamAngleY)`` a key at ``coords=[-1.0, 1.0]``
    captures the deformer forms with the head fully tilted up-left.
    """

    coords: list[float]
    forms: dict[str, dict] = field(default_factory=dict)


@dataclass
class ParameterBlend:
    """Multi-axis keyform group — N-D linear interpolation across the
    cartesian product of ``parameters``.

    Live2D's "ParamAngleX × ParamAngleY → bilinear blend" feature lives
    here: pick N parameters, place keys on a regular grid in their
    cartesian product, and the runtime samples by finding the
    surrounding cell and N-D-linearly interpolating between its
    ``2 ** N`` corners. Most rigs use 2 axes; N is unrestricted in the
    schema.

    Keys whose grid is incomplete (missing a corner) still work — the
    sampler treats unfilled corners as identity (no override), so a
    sparse blend degrades gracefully instead of refusing to sample.
    """

    id: str
    parameters: list[str]
    keys: list[BlendKey] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Part tree (hierarchical drawable organization)
# ---------------------------------------------------------------------------


@dataclass
class Part:
    """One node in the Part tree.

    Live2D Cubism groups drawables into a tree of Parts (Photoshop
    folders, basically) where every Part has its own visibility +
    opacity and the values cascade to descendants — hiding a "hair"
    Part hides every hair drawable underneath regardless of their
    individual ``visible`` flag.

    Children can be drawable ids (leaves) or other Part ids (branches);
    the two id namespaces don't collide because the runtime resolver
    cross-checks against :attr:`PuppetDocument.parts` and
    :attr:`PuppetDocument.drawables` separately.
    """

    id: str
    drawables: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    visible: bool = True
    opacity: float = 1.0


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
    fade_in_duration: float = 0.0
    """Seconds to ease the previous parameter values into this motion's
    sampled values when this motion is bound to the player. ``0.0``
    keeps the legacy snap behaviour; Cubism imports populate this from
    the ``.motion3.json`` Meta block."""
    fade_out_duration: float = 0.0
    """Seconds to ease parameter values back toward their defaults
    when the player stops on this motion."""
    sound_path: str | None = None
    """Absolute path to a WAV file that plays in sync with this motion.
    Cubism ``.model3.json`` imports populate it from the motion entry's
    ``Sound`` field. The player loads it through ``QSoundEffect`` and
    degrades silently when ``PySide6.QtMultimedia`` isn't available."""
    group: str | None = None
    """Name of the motion group this belongs to (Cubism ``Idle`` /
    ``TapHead`` / ``Shake`` …). When a HitArea or idle ticker fires
    for a group, the workspace picks a random motion among those that
    share this tag — matches Cubism's "random idle / tap response"
    convention."""


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
# Hit areas
# ---------------------------------------------------------------------------


@dataclass
class HitArea:
    """A named clickable region on the puppet.

    The region is the axis-aligned bounding box of every drawable in
    ``drawables`` at its current (possibly deformed) vertex positions.
    Clicking inside the box fires whichever of ``motion`` /
    ``expression`` is set — motions play through the workspace's motion
    player, expressions toggle on/off through the canvas's expression
    stack.

    Both action fields are optional so a hit area can serve purely as a
    discoverability hint (the editor surfaces them in the UI) without
    necessarily triggering anything.
    """

    id: str
    drawables: list[str]
    motion: str | None = None
    expression: str | None = None


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
    hit_areas: list[HitArea] = field(default_factory=list)
    parameter_blends: list[ParameterBlend] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)
    display_names: dict[str, str] = field(default_factory=dict)
    """Friendly labels for parameters and parts, keyed by their id.
    Sourced from a Cubism ``.cdi3.json`` or authored by hand; the
    parameter dock prefers this over the raw id when present."""
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
