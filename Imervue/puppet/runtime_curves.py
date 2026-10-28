"""Sample valid parameter-driven scalar and RGB multiplier curves."""
from __future__ import annotations

from collections.abc import Iterator

from Imervue.puppet.runtime_interpolation import bracket


def curve_samples(
    entries: list[dict], values: dict[str, float],
) -> Iterator[tuple[list[dict], float]]:
    """Yield authored stops and parameter values for usable curve entries."""
    for entry in entries:
        param = entry.get("parameter")
        stops = entry.get("stops") or []
        if isinstance(param, str) and param and stops:
            yield stops, float(values.get(param, 0.0))


def _sample_stops(stops: list[dict], value: float) -> tuple[dict, dict, float]:
    ordered = sorted(stops, key=lambda stop: float(stop["value"]))
    lo, hi, t = bracket([float(stop["value"]) for stop in ordered], value)
    return ordered[lo], ordered[hi], t


def _sample_color_stops(stops: list[dict], value: float) -> tuple[float, float, float]:
    a, b, t = _sample_stops(stops, value)
    if a is b or float(a["value"]) == float(b["value"]):
        return tuple(float(c) for c in a["color"])
    ac = [float(c) for c in a["color"]]
    bc = [float(c) for c in b["color"]]
    return tuple(ac[i] * (1.0 - t) + bc[i] * t for i in range(3))


def _sample_opacity_stops(stops: list[dict], value: float) -> float:
    a, b, t = _sample_stops(stops, value)
    if a is b or float(a["value"]) == float(b["value"]):
        return float(a["alpha"])
    return float(a["alpha"]) * (1.0 - t) + float(b["alpha"]) * t
