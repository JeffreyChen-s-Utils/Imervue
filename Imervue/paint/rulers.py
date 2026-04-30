"""Pure-math ruler / drawing-aid helpers for the brush tool.

A ruler constrains the brush cursor to a geometric track — line,
ellipse, concentric ring, or parallel grid — so the user can lay down
a perfectly straight or curved stroke without a steady hand. MediBang
exposes this as the "Snap" panel; Imervue mirrors the same five
common modes plus an explicit ``off`` no-op.

Modes
-----

* ``off`` — identity; ``snap_to_ruler`` returns the input point.
* ``linear`` — snap to the infinite line through ``anchor`` at
  ``angle_deg``. The snapped point is the perpendicular foot of the
  cursor on the line.
* ``cross`` — snap to the nearer of two perpendicular lines through
  ``anchor`` (the second line is rotated 90° from ``angle_deg``).
* ``ellipse`` — snap to the perimeter of an ellipse centred at
  ``anchor`` with semi-axes (``rx``, ``ry``) rotated by
  ``angle_deg``. Uses radial projection — the snapped point lies on
  the ray from the centre through the cursor.
* ``concentric`` — snap to the nearest concentric circle around
  ``anchor``; the rings are spaced ``spacing`` pixels apart.
* ``parallel`` — snap to the nearest of an infinite family of
  parallel lines through ``anchor`` at ``angle_deg``, spaced
  ``spacing`` pixels apart perpendicular to the line direction.

The module is Qt-free and numpy-light — only stdlib ``math`` is used
so the helpers can run without a display server in unit tests. The
:class:`Ruler` dataclass is JSON-friendly; :class:`ToolState`
serialises one across runs via ``to_dict`` / ``from_dict``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

RULER_MODES = (
    "off",
    "linear",
    "cross",
    "ellipse",
    "concentric",
    "parallel",
)
DEFAULT_RULER_MODE = "off"

# Floats below this magnitude are treated as zero — protects against
# divide-by-zero when the cursor coincides with the ruler centre.
_EPSILON = 1e-9


@dataclass(frozen=True)
class Ruler:
    """Active ruler definition. Fields not used by ``mode`` are ignored.

    Default values produce an ``off`` ruler (no snapping). Callers that
    need a constrained ruler should always supply ``mode`` plus the
    fields the mode needs:

    * ``linear`` / ``cross`` — ``anchor`` + ``angle_deg``
    * ``ellipse`` — ``anchor`` + ``rx`` + ``ry`` (+ optional
      ``angle_deg`` for rotation)
    * ``concentric`` — ``anchor`` + ``spacing``
    * ``parallel`` — ``anchor`` + ``angle_deg`` + ``spacing``
    """

    mode: str = DEFAULT_RULER_MODE
    anchor: tuple[float, float] = (0.0, 0.0)
    angle_deg: float = 0.0
    rx: float = 50.0
    ry: float = 50.0
    spacing: float = 20.0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "anchor": list(self.anchor),
            "angle_deg": float(self.angle_deg),
            "rx": float(self.rx),
            "ry": float(self.ry),
            "spacing": float(self.spacing),
        }

    @classmethod
    def from_dict(cls, raw: dict | None) -> Ruler:
        """Build a Ruler from a possibly-incomplete on-disk dict.

        Unknown / corrupt fields fall back to the dataclass default so
        a hand-edited settings file can never crash workspace boot.
        """
        if not isinstance(raw, dict):
            return cls()
        mode = raw.get("mode")
        if mode not in RULER_MODES:
            mode = DEFAULT_RULER_MODE
        return cls(
            mode=mode,
            anchor=_safe_anchor(raw.get("anchor")),
            angle_deg=_safe_float(raw.get("angle_deg"), 0.0),
            rx=_safe_positive(raw.get("rx"), 50.0),
            ry=_safe_positive(raw.get("ry"), 50.0),
            spacing=_safe_positive(raw.get("spacing"), 20.0),
        )


# Module-level singleton so callers that want "no ruler" don't have to
# re-instantiate. Frozen, so safe to share.
OFF_RULER = Ruler()


def snap_to_ruler(
    point: tuple[float, float], ruler: Ruler,
) -> tuple[float, float]:
    """Project ``point`` onto the geometry described by ``ruler``.

    Pure function: never mutates the ruler or the point. Returns a
    fresh ``(x, y)`` tuple. Off-mode rulers short-circuit to the input
    so the no-snap path pays only a dict lookup.
    """
    mode = ruler.mode
    if mode == "off":
        return (float(point[0]), float(point[1]))
    if mode == "linear":
        return _snap_linear(point, ruler.anchor, ruler.angle_deg)
    if mode == "cross":
        return _snap_cross(point, ruler.anchor, ruler.angle_deg)
    if mode == "ellipse":
        return _snap_ellipse(
            point, ruler.anchor, ruler.rx, ruler.ry, ruler.angle_deg,
        )
    if mode == "concentric":
        return _snap_concentric(point, ruler.anchor, ruler.spacing)
    if mode == "parallel":
        return _snap_parallel(
            point, ruler.anchor, ruler.angle_deg, ruler.spacing,
        )
    raise ValueError(
        f"unknown ruler mode {mode!r}; expected one of {RULER_MODES}",
    )


# ---------------------------------------------------------------------------
# Per-mode snap implementations
# ---------------------------------------------------------------------------


def _snap_linear(
    point: tuple[float, float],
    anchor: tuple[float, float],
    angle_deg: float,
) -> tuple[float, float]:
    """Perpendicular foot of ``point`` on the line through ``anchor``."""
    px, py = float(point[0]), float(point[1])
    ax, ay = float(anchor[0]), float(anchor[1])
    rad = math.radians(angle_deg)
    dx = math.cos(rad)
    dy = math.sin(rad)
    rel_x = px - ax
    rel_y = py - ay
    t = rel_x * dx + rel_y * dy
    return (ax + t * dx, ay + t * dy)


def _snap_cross(
    point: tuple[float, float],
    anchor: tuple[float, float],
    angle_deg: float,
) -> tuple[float, float]:
    """Snap to the closer of two perpendicular lines through ``anchor``."""
    p1 = _snap_linear(point, anchor, angle_deg)
    p2 = _snap_linear(point, anchor, angle_deg + 90.0)
    if _dist_sq(point, p1) <= _dist_sq(point, p2):
        return p1
    return p2


def _snap_ellipse(
    point: tuple[float, float],
    anchor: tuple[float, float],
    rx: float,
    ry: float,
    angle_deg: float,
) -> tuple[float, float]:
    """Radial projection of ``point`` onto an ellipse perimeter.

    The snap is the intersection of the ellipse with the ray from the
    centre through the cursor — not the perpendicular foot. For brush
    snapping that's the natural mapping (the user expects the cursor
    angle to be preserved, not minimised distance) and it has a
    closed-form solution that's cheap to compute.
    """
    if rx <= _EPSILON or ry <= _EPSILON:
        raise ValueError(
            f"ellipse semi-axes must be positive, got rx={rx!r} ry={ry!r}",
        )
    ax, ay = float(anchor[0]), float(anchor[1])
    rel_x = float(point[0]) - ax
    rel_y = float(point[1]) - ay
    # Rotate the relative vector into the ellipse's local frame.
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    local_x = rel_x * cos_a + rel_y * sin_a
    local_y = -rel_x * sin_a + rel_y * cos_a
    # Cursor at the centre — pick a deterministic point on the ellipse.
    if abs(local_x) < _EPSILON and abs(local_y) < _EPSILON:
        snap_local = (rx, 0.0)
    else:
        # Scale into unit-circle space, normalise, scale back.
        sx = local_x / rx
        sy = local_y / ry
        norm = math.hypot(sx, sy)
        snap_local = (rx * (sx / norm), ry * (sy / norm))
    # Rotate snap point back into world frame.
    snap_x = snap_local[0] * cos_a - snap_local[1] * sin_a
    snap_y = snap_local[0] * sin_a + snap_local[1] * cos_a
    return (ax + snap_x, ay + snap_y)


def _snap_concentric(
    point: tuple[float, float],
    anchor: tuple[float, float],
    spacing: float,
) -> tuple[float, float]:
    """Snap to the nearest concentric ring around ``anchor``."""
    if spacing <= _EPSILON:
        raise ValueError(f"concentric spacing must be positive, got {spacing!r}")
    ax, ay = float(anchor[0]), float(anchor[1])
    rel_x = float(point[0]) - ax
    rel_y = float(point[1]) - ay
    distance = math.hypot(rel_x, rel_y)
    # Cursor on the centre — the centre is itself a valid ring (r=0).
    if distance < _EPSILON:
        return (ax, ay)
    snap_radius = round(distance / spacing) * spacing
    if snap_radius < _EPSILON:
        return (ax, ay)
    scale = snap_radius / distance
    return (ax + rel_x * scale, ay + rel_y * scale)


def _snap_parallel(
    point: tuple[float, float],
    anchor: tuple[float, float],
    angle_deg: float,
    spacing: float,
) -> tuple[float, float]:
    """Snap to the nearest line in a parallel-line grid."""
    if spacing <= _EPSILON:
        raise ValueError(f"parallel spacing must be positive, got {spacing!r}")
    ax, ay = float(anchor[0]), float(anchor[1])
    rad = math.radians(angle_deg)
    dx = math.cos(rad)
    dy = math.sin(rad)
    # Perpendicular unit vector to the line direction.
    nx = -dy
    ny = dx
    rel_x = float(point[0]) - ax
    rel_y = float(point[1]) - ay
    along = rel_x * dx + rel_y * dy
    across = rel_x * nx + rel_y * ny
    snap_across = round(across / spacing) * spacing
    return (ax + along * dx + snap_across * nx,
            ay + along * dy + snap_across * ny)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dist_sq(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _safe_anchor(value: object) -> tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return (float(value[0]), float(value[1]))
        except (TypeError, ValueError):
            return (0.0, 0.0)
    return (0.0, 0.0)


def _safe_float(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _safe_positive(value: object, default: float) -> float:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return f if f > _EPSILON else default
