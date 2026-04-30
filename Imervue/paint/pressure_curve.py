"""Pen-pressure response curves.

The 4a brush dynamics maps pressure linearly to size + opacity. That
works for "harder press = bigger dab", but professional users want a
custom response: an S-curve makes light strokes very feathery while
keeping medium-pressure work consistent, a hockey-stick lifts the
floor so even the lightest tap leaves visible ink, etc.

This module ships the response-curve data type:

* :class:`PressureCurve` — frozen list of ``(input, output)`` control
  points in ``[0, 1] × [0, 1]``, with linear interpolation between
  points. Defaults to identity (input = output).
* :func:`apply_curve` — sample the curve at a single pressure value.

The brush rasteriser consults a :class:`PressureCurve` per stroke;
applying the curve before pressure scales size / opacity gives the
user complete control over the response shape without touching the
brush kernel.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PressureCurve:
    """Pressure response curve — list of control points 0..1."""

    points: tuple[tuple[float, float], ...] = (
        (0.0, 0.0), (1.0, 1.0),
    )

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError(
                f"pressure curve needs at least 2 points, got {len(self.points)}",
            )
        for pt in self.points:
            if not (isinstance(pt, tuple) and len(pt) == 2):
                raise ValueError(f"each point must be a 2-tuple, got {pt!r}")
            for value in pt:
                if not 0.0 <= float(value) <= 1.0:
                    raise ValueError(
                        f"points must lie in [0, 1], got {pt!r}",
                    )
        positions = [pt[0] for pt in self.points]
        if positions != sorted(positions):
            raise ValueError(
                "points must be supplied in non-decreasing input order",
            )
        if positions[0] > 0.0 + 1e-9 or positions[-1] < 1.0 - 1e-9:
            raise ValueError(
                "curve must cover the full [0, 1] input range — "
                "first point at 0.0, last at 1.0",
            )

    def apply(self, pressure: float) -> float:
        """Sample the curve at ``pressure`` ∈ ``[0, 1]``.

        Out-of-range input is clamped. Linear interpolation between
        control points; the same input never produces two outputs."""
        p = max(0.0, min(1.0, float(pressure)))
        for i in range(1, len(self.points)):
            lo = self.points[i - 1]
            hi = self.points[i]
            if p <= hi[0]:
                span = hi[0] - lo[0]
                if span < 1e-9:
                    return float(hi[1])
                t = (p - lo[0]) / span
                return float(lo[1] + (hi[1] - lo[1]) * t)
        return float(self.points[-1][1])

    def to_dict(self) -> dict:
        return {"points": [list(pt) for pt in self.points]}

    @classmethod
    def from_dict(cls, raw: dict) -> PressureCurve:
        if not isinstance(raw, dict):
            raise ValueError(
                f"curve payload must be a dict, got {type(raw).__name__}",
            )
        raw_points = raw.get("points") or []
        if not isinstance(raw_points, list):
            raise ValueError("points must be a list")
        cleaned: list[tuple[float, float]] = []
        for entry in raw_points:
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                continue
            try:
                x = max(0.0, min(1.0, float(entry[0])))
                y = max(0.0, min(1.0, float(entry[1])))
            except (TypeError, ValueError):
                continue
            cleaned.append((x, y))
        cleaned.sort(key=lambda pt: pt[0])
        # Empty payload means "user gave no curve" — fall back to a
        # full identity rather than a flat-zero curve.
        if not cleaned:
            return cls(points=((0.0, 0.0), (1.0, 1.0)))
        if cleaned[0][0] > 0.0:
            cleaned.insert(0, (0.0, cleaned[0][1]))
        if cleaned[-1][0] < 1.0:
            cleaned.append((1.0, cleaned[-1][1]))
        return cls(points=tuple(cleaned))


def apply_curve(curve: PressureCurve | None, pressure: float) -> float:
    """Sample a curve, treating ``None`` as the identity transform."""
    if curve is None:
        return max(0.0, min(1.0, float(pressure)))
    return curve.apply(pressure)


# ---------------------------------------------------------------------------
# Built-in presets
# ---------------------------------------------------------------------------


IDENTITY = PressureCurve()
"""Default curve — output = input."""

SOFT_TAPER = PressureCurve(points=(
    (0.0, 0.0), (0.3, 0.1), (0.7, 0.6), (1.0, 1.0),
))
"""S-curve that softens light strokes and lifts mid-pressure response."""

HARD_FLOOR = PressureCurve(points=(
    (0.0, 0.4), (0.2, 0.5), (0.7, 0.8), (1.0, 1.0),
))
"""Lifts the floor so even the lightest tap leaves significant ink."""

LIGHT_TOUCH = PressureCurve(points=(
    (0.0, 0.0), (0.3, 0.4), (0.7, 0.7), (1.0, 0.85),
))
"""Boosts low pressure response and caps the maximum so a hard
press doesn't overshoot — useful for sketchers who like a wide
mid-range."""

BUILT_IN_CURVES: tuple[tuple[str, PressureCurve], ...] = (
    ("Identity", IDENTITY),
    ("Soft Taper", SOFT_TAPER),
    ("Hard Floor", HARD_FLOOR),
    ("Light Touch", LIGHT_TOUCH),
)
