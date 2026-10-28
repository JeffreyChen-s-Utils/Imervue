"""Locate a clamped linear interval in sorted authored coordinates."""
from __future__ import annotations


def bracket(
    coords: list[float], value: float, *, fallback_to_span: bool = False,
) -> tuple[int, int, float]:
    """Return endpoint indices and weight, keeping the first matching interval."""
    if value <= coords[0]:
        return 0, 0, 0.0
    last = len(coords) - 1
    if value >= coords[-1]:
        return last, last, 1.0
    for i, (lo, hi) in enumerate(zip(coords, coords[1:], strict=False)):
        if lo <= value <= hi:
            return i, i + 1, 0.0 if hi == lo else (value - lo) / (hi - lo)
    # Blend axes retain their full span when NaN prevents every comparison;
    # parameter keys and appearance curves instead select their final key.
    if fallback_to_span:
        span = coords[-1] - coords[0]
        return 0, last, 0.0 if span == 0 else (value - coords[0]) / span
    return last, last, 0.0
