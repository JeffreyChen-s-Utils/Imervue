"""Multi-stop gradient editor.

The Phase 3c gradient tool only handled two-colour gradients (foreground
→ background). raster paint apps' gradient editor lets the user place multiple
colour stops along the gradient and tune each one's position and
alpha — much more useful for sky gradients, neon glows, etc.

This module adds:

* :class:`GradientStop` — frozen ``(position, color)`` pair, where
  ``position`` is in ``[0, 1]`` and ``color`` is RGBA uint8.
* :class:`MultiStopGradient` — frozen list of stops sorted by
  position; validates that there are at least two stops and that
  the position range covers the whole ``[0, 1]`` interval.
* :func:`interpolate_at` — sample a gradient at a single ``t``.
* :func:`build_lut` — render a gradient into an Nx4 LUT for fast
  channel lookups.
* :func:`render_multistop_gradient` — full canvas raster, mirroring
  the existing ``render_gradient`` API but with a multi-stop
  parameter object instead of fg / bg colours.

JSON-friendly: both dataclasses round-trip through to_dict /
from_dict so user-defined gradients can persist alongside brush
presets and palettes.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from Imervue.paint.gradient import _T_FIELD_BUILDERS, GRADIENT_KINDS
from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

_USER_SETTING_KEY = "paint_multistop_gradients"


@dataclass(frozen=True)
class GradientStop:
    """One colour stop in a multi-stop gradient."""

    position: float
    color: tuple[int, int, int, int]

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.position) <= 1.0:
            raise ValueError(
                f"stop position must be in [0, 1], got {self.position!r}",
            )
        if not isinstance(self.color, tuple) or len(self.color) != 4:
            raise ValueError(
                f"color must be a 4-tuple (R, G, B, A), got {self.color!r}",
            )
        for c in self.color:
            if not 0 <= int(c) <= 255:
                raise ValueError(
                    f"color components must be in [0, 255], got {self.color!r}",
                )

    def to_dict(self) -> dict:
        return {"position": float(self.position), "color": list(self.color)}

    @classmethod
    def from_dict(cls, raw: dict) -> GradientStop:
        if not isinstance(raw, dict):
            raise ValueError(f"stop payload must be a dict, got {type(raw).__name__}")
        color = raw.get("color")
        if isinstance(color, list | tuple) and len(color) == 4:
            color_tuple = tuple(max(0, min(255, int(c))) for c in color)
        elif isinstance(color, list | tuple) and len(color) == 3:
            color_tuple = (*tuple(max(0, min(255, int(c))) for c in color), 255)
        else:
            color_tuple = (0, 0, 0, 255)
        return cls(
            position=max(0.0, min(1.0, float(raw.get("position", 0.0)))),
            color=color_tuple,   # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class MultiStopGradient:
    """Ordered list of GradientStops covering the ``[0, 1]`` interval."""

    name: str
    stops: tuple[GradientStop, ...]

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("gradient name must be non-empty")
        if len(self.stops) < 2:
            raise ValueError(
                f"gradient must have >= 2 stops, got {len(self.stops)}",
            )
        positions = [s.position for s in self.stops]
        if positions != sorted(positions):
            raise ValueError(
                "gradient stops must be supplied in non-decreasing position order",
            )
        if positions[0] > 0.0 + 1e-9 or positions[-1] < 1.0 - 1e-9:
            raise ValueError(
                "gradient must cover the full [0, 1] range — first stop "
                "should be at 0.0 and last at 1.0",
            )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "stops": [stop.to_dict() for stop in self.stops],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> MultiStopGradient:
        if not isinstance(raw, dict):
            raise ValueError(
                f"gradient payload must be a dict, got {type(raw).__name__}",
            )
        stops_raw = raw.get("stops") or []
        if not isinstance(stops_raw, list):
            raise ValueError("stops must be a list")
        stops = []
        for s in stops_raw:
            try:
                stops.append(GradientStop.from_dict(s))
            except (ValueError, TypeError):
                continue
        stops.sort(key=lambda stop: stop.position)
        # Ensure full coverage by clamping endpoints; corrupt persists
        # otherwise crash construction.
        if stops:
            if stops[0].position > 0.0:
                stops.insert(0, GradientStop(position=0.0, color=stops[0].color))
            if stops[-1].position < 1.0:
                stops.append(GradientStop(position=1.0, color=stops[-1].color))
        return cls(
            name=str(raw.get("name", "")).strip() or "gradient",
            stops=tuple(stops),
        )


# ---------------------------------------------------------------------------
# Editing — each returns a new gradient, the input is never changed
# ---------------------------------------------------------------------------


def default_gradient(
    name: str,
    start: tuple[int, int, int, int] = (0, 0, 0, 255),
    end: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> MultiStopGradient:
    """A two-stop gradient from *start* to *end*, the starting point for a new one."""
    return MultiStopGradient(name=name, stops=(GradientStop(0.0, start), GradientStop(1.0, end)))


def add_stop(gradient: MultiStopGradient) -> tuple[MultiStopGradient, int]:
    """Add a stop in the middle of the widest gap, coloured as the gradient is there.

    Returns the new gradient and the new stop's index.
    """
    stops = gradient.stops
    gap = max(range(1, len(stops)), key=lambda i: stops[i].position - stops[i - 1].position)
    position = (stops[gap - 1].position + stops[gap].position) / 2
    new = GradientStop(position, interpolate_at(gradient, position))
    return replace(gradient, stops=(*stops[:gap], new, *stops[gap:])), gap


def remove_stop(gradient: MultiStopGradient, index: int) -> MultiStopGradient:
    """Drop the stop at *index*; the two end stops stay, so a gradient keeps both ends."""
    if not 0 < index < len(gradient.stops) - 1:
        return gradient
    return replace(gradient, stops=gradient.stops[:index] + gradient.stops[index + 1:])


def move_stop(gradient: MultiStopGradient, index: int, position: float) -> MultiStopGradient:
    """Move an inner stop to *position*, kept between its neighbours; the ends stay at 0 and 1."""
    stops = gradient.stops
    if not 0 < index < len(stops) - 1:
        return gradient
    position = max(stops[index - 1].position, min(stops[index + 1].position, float(position)))
    moved = GradientStop(position, stops[index].color)
    return replace(gradient, stops=(*stops[:index], moved, *stops[index + 1:]))


def recolour_stop(
    gradient: MultiStopGradient, index: int, color: tuple[int, int, int, int],
) -> MultiStopGradient:
    """Give the stop at *index* the RGBA *color*."""
    stops = gradient.stops
    changed = GradientStop(stops[index].position, tuple(int(c) for c in color))  # type: ignore[arg-type]
    return replace(gradient, stops=(*stops[:index], changed, *stops[index + 1:]))


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------


def interpolate_at(
    gradient: MultiStopGradient, t: float,
) -> tuple[int, int, int, int]:
    """Sample a gradient at parameter ``t`` ∈ ``[0, 1]``."""
    t = max(0.0, min(1.0, float(t)))
    stops = gradient.stops
    # Linear search — gradient stop counts are small (typically ≤ 8).
    for i in range(1, len(stops)):
        prev_stop = stops[i - 1]
        next_stop = stops[i]
        if t <= next_stop.position:
            span = next_stop.position - prev_stop.position
            if span <= 1e-12:
                return next_stop.color
            local = (t - prev_stop.position) / span
            return _interp_color(prev_stop.color, next_stop.color, local)
    return stops[-1].color


def build_lut(gradient: MultiStopGradient, steps: int = 256) -> np.ndarray:
    """Render a gradient into an Nx4 uint8 RGBA LUT."""
    if steps <= 0:
        raise ValueError(f"steps must be > 0, got {steps}")
    out = np.zeros((steps, 4), dtype=np.uint8)
    for i in range(steps):
        t = i / max(1, steps - 1)
        out[i] = interpolate_at(gradient, t)
    return out


def _interp_color(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
    t: float,
) -> tuple[int, int, int, int]:
    return tuple(
        int(round(max(0.0, min(255.0,
            a[k] * (1.0 - t) + b[k] * t,
        ))))
        for k in range(4)
    )   # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Canvas raster
# ---------------------------------------------------------------------------


def render_multistop_gradient(
    canvas: np.ndarray,
    p0: tuple[float, float],
    p1: tuple[float, float],
    gradient: MultiStopGradient,
    *,
    kind: str = "linear",
    reverse: bool = False,
    repeat: int = 1,
    selection: np.ndarray | None = None,
) -> bool:
    """Fill ``canvas`` with a multi-stop gradient between ``p0`` and ``p1``.

    Mirrors :func:`Imervue.paint.gradient.render_gradient` for the
    geometry side, *repeat* included; the colour interpolation is done
    via the gradient LUT instead of a single FG↔BG mix, so any number of
    stops appears in the result.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
    if kind not in GRADIENT_KINDS:
        raise ValueError(
            f"unknown gradient kind {kind!r}; expected one of {GRADIENT_KINDS}",
        )
    h, w = canvas.shape[:2]
    if selection is not None and selection.shape != (h, w):
        raise ValueError(
            f"selection shape {selection.shape} does not match canvas {(h, w)}",
        )

    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    if x0 == x1 and y0 == y1:
        return False

    yy, xx = np.indices((h, w), dtype=np.float32)
    t = np.clip(_T_FIELD_BUILDERS[kind](xx, yy, x0, y0, x1, y1), 0.0, 1.0)
    if reverse:
        t = 1.0 - t
    repeat = max(1, int(repeat))
    if repeat > 1:
        t = np.mod(t * repeat, 1.0)       # tiled along the span, as render_gradient does

    lut = build_lut(gradient, steps=256)
    indices = np.clip((t * 255.0 + 0.5).astype(np.int32), 0, 255)
    sampled = lut[indices]

    mask = selection if selection is not None else np.ones((h, w), dtype=np.bool_)
    canvas[mask] = sampled[mask]
    return True


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_gradients(gradients: list[MultiStopGradient]) -> None:
    """Persist user-defined gradients to user_setting_dict."""
    user_setting_dict[_USER_SETTING_KEY] = [g.to_dict() for g in gradients]
    schedule_save()


def load_gradients() -> list[MultiStopGradient]:
    """Return the persisted user gradients; corrupt entries skipped."""
    raw = user_setting_dict.get(_USER_SETTING_KEY)
    if not isinstance(raw, list):
        return []
    out: list[MultiStopGradient] = []
    for entry in raw:
        try:
            out.append(MultiStopGradient.from_dict(entry))
        except (ValueError, TypeError):
            continue
    return out
