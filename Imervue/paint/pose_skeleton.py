"""2D stick-figure pose reference.

A simplified stand-in for MediBang's 3D pose model: a fixed set of
twelve joints connected by named bones, posed in normalised image
coordinates so the same skeleton renders cleanly at any canvas
size. Joints carry an optional radius so the head reads as a disc
and the torso pivots feel more anatomical than a uniform dot grid.

The dataclasses are pure data + a render helper; the dock and
workspace wiring live in :mod:`Imervue.paint.pose_dock`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from collections.abc import Iterable

import numpy as np
from PIL import Image, ImageDraw

# Default skeleton geometry — a generic standing front-view figure.
# Coordinates are normalised: (0, 0) top-left, (1, 1) bottom-right of
# whatever canvas the skeleton is rendered onto. Tuned to leave a
# small margin top + bottom so the head and feet aren't clipped.

DEFAULT_LINE_PX = 4
DEFAULT_COLOR = (40, 40, 40, 255)
DEFAULT_JOINT_RGBA = (200, 60, 60, 255)


@dataclass(frozen=True)
class Joint:
    """One articulation point of the skeleton.

    Coordinates are fractional (0..1). ``radius_px`` is the rendered
    dot radius — the head joint is fatter than the others so the
    figure reads as a person rather than a starfish.
    """

    name: str
    x: float
    y: float
    radius_px: int = 5

    def with_xy(self, x: float, y: float) -> Joint:
        """Return a copy with the position updated."""
        return replace(self, x=float(x), y=float(y))


@dataclass(frozen=True)
class Bone:
    """A line segment between two joints (referenced by name)."""

    a: str
    b: str


@dataclass
class PoseSkeleton:
    """Mutable container so the dock can drag joints in place.

    Stored as a name → Joint dict for O(1) lookup; bones reference
    joints by name so renaming or replacing a joint does not break
    the connection graph as long as the name survives.
    """

    joints: dict[str, Joint] = field(default_factory=dict)
    bones: tuple[Bone, ...] = field(default_factory=tuple)

    def joint(self, name: str) -> Joint:
        return self.joints[name]

    def move_joint(self, name: str, x: float, y: float) -> None:
        joint = self.joints[name]
        # Clamp into the unit square so a stray drag can't fling a
        # limb off-canvas — anything outside (0, 1) is invisible.
        x = max(0.0, min(1.0, float(x)))
        y = max(0.0, min(1.0, float(y)))
        self.joints[name] = joint.with_xy(x, y)

    def to_dict(self) -> dict:
        return {
            "joints": {
                name: {"x": j.x, "y": j.y, "radius_px": j.radius_px}
                for name, j in self.joints.items()
            },
            "bones": [{"a": b.a, "b": b.b} for b in self.bones],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> PoseSkeleton:
        joints = {
            str(name): Joint(
                name=str(name),
                x=float(data.get("x", 0.5)),
                y=float(data.get("y", 0.5)),
                radius_px=int(data.get("radius_px", 5)),
            )
            for name, data in (raw.get("joints") or {}).items()
        }
        bones = tuple(
            Bone(a=str(b["a"]), b=str(b["b"]))
            for b in (raw.get("bones") or [])
        )
        return cls(joints=joints, bones=bones)


# ---------------------------------------------------------------------------
# Default factory
# ---------------------------------------------------------------------------


_DEFAULT_JOINT_TABLE: tuple[tuple[str, float, float, int], ...] = (
    # (name, x, y, radius_px)
    ("head", 0.50, 0.10, 22),
    ("neck", 0.50, 0.20, 6),
    ("chest", 0.50, 0.30, 6),
    ("hips", 0.50, 0.55, 6),
    ("l_shoulder", 0.42, 0.22, 6),
    ("r_shoulder", 0.58, 0.22, 6),
    ("l_elbow", 0.36, 0.40, 5),
    ("r_elbow", 0.64, 0.40, 5),
    ("l_wrist", 0.32, 0.55, 5),
    ("r_wrist", 0.68, 0.55, 5),
    ("l_hip", 0.46, 0.55, 5),
    ("r_hip", 0.54, 0.55, 5),
    ("l_knee", 0.45, 0.75, 5),
    ("r_knee", 0.55, 0.75, 5),
    ("l_ankle", 0.45, 0.95, 5),
    ("r_ankle", 0.55, 0.95, 5),
)

_DEFAULT_BONES: tuple[Bone, ...] = (
    Bone("head", "neck"),
    Bone("neck", "chest"),
    Bone("chest", "hips"),
    Bone("neck", "l_shoulder"),
    Bone("neck", "r_shoulder"),
    Bone("l_shoulder", "l_elbow"),
    Bone("l_elbow", "l_wrist"),
    Bone("r_shoulder", "r_elbow"),
    Bone("r_elbow", "r_wrist"),
    Bone("hips", "l_hip"),
    Bone("hips", "r_hip"),
    Bone("l_hip", "l_knee"),
    Bone("l_knee", "l_ankle"),
    Bone("r_hip", "r_knee"),
    Bone("r_knee", "r_ankle"),
)


def default_skeleton() -> PoseSkeleton:
    """Return a fresh standing-figure skeleton at default proportions."""
    joints = {
        name: Joint(name=name, x=x, y=y, radius_px=r)
        for (name, x, y, r) in _DEFAULT_JOINT_TABLE
    }
    return PoseSkeleton(joints=joints, bones=_DEFAULT_BONES)


# ---------------------------------------------------------------------------
# Rasterisation
# ---------------------------------------------------------------------------


def render_skeleton(
    skeleton: PoseSkeleton, height: int, width: int, *,
    line_px: int = DEFAULT_LINE_PX,
    bone_color: tuple[int, int, int, int] = DEFAULT_COLOR,
    joint_color: tuple[int, int, int, int] = DEFAULT_JOINT_RGBA,
) -> np.ndarray:
    """Draw ``skeleton`` into an HxWx4 RGBA buffer.

    Bones are drawn first (so joint discs overlay the line ends),
    then joint discs at their per-joint radius.
    """
    if int(height) <= 0 or int(width) <= 0:
        raise ValueError(
            f"skeleton canvas must be positive, got {(height, width)}",
        )
    img = Image.new("RGBA", (int(width), int(height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for bone in skeleton.bones:
        a = skeleton.joints.get(bone.a)
        b = skeleton.joints.get(bone.b)
        if a is None or b is None:
            continue
        draw.line(
            [
                (a.x * width, a.y * height),
                (b.x * width, b.y * height),
            ],
            fill=bone_color, width=int(line_px),
        )

    for joint in skeleton.joints.values():
        cx = joint.x * width
        cy = joint.y * height
        r = max(1, int(joint.radius_px))
        draw.ellipse(
            (cx - r, cy - r, cx + r, cy + r),
            fill=joint_color, outline=bone_color, width=max(1, int(line_px) // 2),
        )

    return np.asarray(img, dtype=np.uint8).copy()


def joint_iter(skeleton: PoseSkeleton) -> Iterable[Joint]:
    """Stable-order iterator over the skeleton's joints."""
    return skeleton.joints.values()
