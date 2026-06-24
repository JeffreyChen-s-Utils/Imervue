"""Easing presets for motion authoring.

A ``cubic-bezier`` :class:`~Imervue.puppet.document.MotionSegment` carries two
control points in (time, value) space. Hand-tuning those handles to get a
familiar "ease-in-cubic" or "ease-out-back" feel is tedious, so this module
ships the standard easing curves three ways:

* :func:`ease_value` — closed-form (Penner) evaluation of any named easing on a
  normalised progress ``u`` in ``[0, 1]`` → eased ``[0, 1]`` (covers the
  oscillating elastic / bounce families a single bezier can't represent).
* :data:`EASING_BEZIER` / :func:`easing_bezier` — the normalised cubic-bezier
  handles ``(x1, y1, x2, y2)`` (the easing.net approximations) for the families
  a single cubic curve *can* represent.
* :func:`control_points_for_segment` — scale those handles onto a segment's
  start / end points, returning the ``(c0, c1)`` a cubic-bezier segment needs.

Pure Python — no Qt and no document mutation; the caller builds the
``MotionSegment`` from the returned control points.
"""
from __future__ import annotations

import math
from collections.abc import Callable

# Back-easing overshoot constants (the classic 1.70158 magic number).
_BACK_C1 = 1.70158
_BACK_C3 = _BACK_C1 + 1.0
# Elastic / bounce shaping constants.
_ELASTIC_C4 = (2.0 * math.pi) / 3.0
_BOUNCE_N1 = 7.5625
_BOUNCE_D1 = 2.75


def _in_sine(u: float) -> float:
    return 1.0 - math.cos(u * math.pi / 2.0)


def _in_quad(u: float) -> float:
    return u * u


def _in_cubic(u: float) -> float:
    return u ** 3


def _in_quart(u: float) -> float:
    return u ** 4


def _in_quint(u: float) -> float:
    return u ** 5


def _in_expo(u: float) -> float:
    return 0.0 if u <= 0.0 else 2.0 ** (10.0 * u - 10.0)


def _in_circ(u: float) -> float:
    return 1.0 - math.sqrt(max(0.0, 1.0 - u * u))


def _in_back(u: float) -> float:
    return _BACK_C3 * u ** 3 - _BACK_C1 * u * u


def _in_elastic(u: float) -> float:
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    return -(2.0 ** (10.0 * u - 10.0)) * math.sin((u * 10.0 - 10.75) * _ELASTIC_C4)


def _out_bounce(u: float) -> float:
    if u < 1.0 / _BOUNCE_D1:
        return _BOUNCE_N1 * u * u
    if u < 2.0 / _BOUNCE_D1:
        u -= 1.5 / _BOUNCE_D1
        return _BOUNCE_N1 * u * u + 0.75
    if u < 2.5 / _BOUNCE_D1:
        u -= 2.25 / _BOUNCE_D1
        return _BOUNCE_N1 * u * u + 0.9375
    u -= 2.625 / _BOUNCE_D1
    return _BOUNCE_N1 * u * u + 0.984375


def _in_bounce(u: float) -> float:
    return 1.0 - _out_bounce(1.0 - u)


def _reflect_out(fn: Callable[[float], float]) -> Callable[[float], float]:
    """``ease-out`` is the point-reflection of the matching ``ease-in``."""
    return lambda u: 1.0 - fn(1.0 - u)


def _reflect_in_out(fn: Callable[[float], float]) -> Callable[[float], float]:
    """``ease-in-out`` runs the ``ease-in`` curve into its reflection."""
    def eased(u: float) -> float:
        if u < 0.5:
            return fn(2.0 * u) / 2.0
        return 1.0 - fn(2.0 - 2.0 * u) / 2.0
    return eased


# Per-family ``ease-in`` base curves; out / in-out are derived by reflection.
_IN_FAMILIES: dict[str, Callable[[float], float]] = {
    "sine": _in_sine, "quad": _in_quad, "cubic": _in_cubic,
    "quart": _in_quart, "quint": _in_quint, "expo": _in_expo,
    "circ": _in_circ, "back": _in_back, "elastic": _in_elastic,
    "bounce": _in_bounce,
}


def _build_registry() -> dict[str, Callable[[float], float]]:
    registry: dict[str, Callable[[float], float]] = {"linear": lambda u: u}
    for family, fn in _IN_FAMILIES.items():
        registry[f"ease-in-{family}"] = fn
        registry[f"ease-out-{family}"] = _reflect_out(fn)
        registry[f"ease-in-out-{family}"] = _reflect_in_out(fn)
    return registry


_EASINGS = _build_registry()
EASING_NAMES: tuple[str, ...] = tuple(sorted(_EASINGS))


def ease_value(name: str, u: float) -> float:
    """Return the eased value at progress ``u`` (clamped to ``[0, 1]``).

    Raises ``ValueError`` for an unknown easing name.
    """
    fn = _EASINGS.get(name)
    if fn is None:
        raise ValueError(f"unknown easing {name!r}; see EASING_NAMES")
    return float(fn(max(0.0, min(1.0, float(u)))))


# Normalised cubic-bezier handles (x1, y1, x2, y2) per the easing.net curves.
# Elastic / bounce are omitted: their oscillation cannot be a single cubic
# bezier — use :func:`ease_value` for those.
EASING_BEZIER: dict[str, tuple[float, float, float, float]] = {
    "linear": (0.0, 0.0, 1.0, 1.0),
    "ease-in-sine": (0.12, 0.0, 0.39, 0.0),
    "ease-out-sine": (0.61, 1.0, 0.88, 1.0),
    "ease-in-out-sine": (0.37, 0.0, 0.63, 1.0),
    "ease-in-quad": (0.11, 0.0, 0.5, 0.0),
    "ease-out-quad": (0.5, 1.0, 0.89, 1.0),
    "ease-in-out-quad": (0.45, 0.0, 0.55, 1.0),
    "ease-in-cubic": (0.32, 0.0, 0.67, 0.0),
    "ease-out-cubic": (0.33, 1.0, 0.68, 1.0),
    "ease-in-out-cubic": (0.65, 0.0, 0.35, 1.0),
    "ease-in-quart": (0.5, 0.0, 0.75, 0.0),
    "ease-out-quart": (0.25, 1.0, 0.5, 1.0),
    "ease-in-out-quart": (0.76, 0.0, 0.24, 1.0),
    "ease-in-quint": (0.64, 0.0, 0.78, 0.0),
    "ease-out-quint": (0.22, 1.0, 0.36, 1.0),
    "ease-in-out-quint": (0.83, 0.0, 0.17, 1.0),
    "ease-in-expo": (0.7, 0.0, 0.84, 0.0),
    "ease-out-expo": (0.16, 1.0, 0.3, 1.0),
    "ease-in-out-expo": (0.87, 0.0, 0.13, 1.0),
    "ease-in-circ": (0.55, 0.0, 1.0, 0.45),
    "ease-out-circ": (0.0, 0.55, 0.45, 1.0),
    "ease-in-out-circ": (0.85, 0.0, 0.15, 1.0),
    "ease-in-back": (0.36, 0.0, 0.66, -0.56),
    "ease-out-back": (0.34, 1.56, 0.64, 1.0),
    "ease-in-out-back": (0.68, -0.6, 0.32, 1.6),
}


def easing_bezier(name: str) -> tuple[float, float, float, float]:
    """Return the normalised ``(x1, y1, x2, y2)`` handles for *name*.

    Raises ``ValueError`` for an easing with no single cubic-bezier form
    (e.g. elastic / bounce) — sample those with :func:`ease_value` instead.
    """
    handles = EASING_BEZIER.get(name)
    if handles is None:
        raise ValueError(
            f"{name!r} has no single cubic-bezier form; "
            f"use ease_value (see EASING_BEZIER for representable curves)",
        )
    return handles


def control_points_for_segment(
    name: str,
    p0: tuple[float, float],
    p1: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Scale *name*'s normalised handles onto a segment ``p0`` → ``p1``.

    ``p0`` / ``p1`` are ``(time, value)`` endpoints; returns the two
    ``(time, value)`` control points ``(c0, c1)`` for a cubic-bezier
    ``MotionSegment`` that follows the named easing.
    """
    x1, y1, x2, y2 = easing_bezier(name)
    t0, v0 = p0
    t1, v1 = p1
    dt = t1 - t0
    dv = v1 - v0
    c0 = (t0 + x1 * dt, v0 + y1 * dv)
    c1 = (t0 + x2 * dt, v0 + y2 * dv)
    return c0, c1
