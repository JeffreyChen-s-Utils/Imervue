"""Validate RGB input and decode stored colors and recent history."""
from __future__ import annotations

from typing import Any


def _clamp_rgb(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    if not isinstance(rgb, tuple) or len(rgb) != 3:
        raise ValueError(f"rgb must be a 3-tuple, got {rgb!r}")
    return tuple(max(0, min(255, int(c))) for c in rgb)


def _clamp_color(
    color: tuple[int, int, int] | None,
) -> tuple[int, int, int] | None:
    """Like :func:`_clamp_rgb` but lets ``None`` pass through unchanged.

    The setters use this so callers can pass ``None`` to mean
    "transparent" without raising on the 3-tuple check.
    """
    if color is None:
        return None
    return _clamp_rgb(color)


def _safe_rgb(
    value: Any, default: tuple[int, int, int] | None,
) -> tuple[int, int, int] | None:
    if isinstance(value, list | tuple) and len(value) == 3:
        try:
            return _clamp_rgb(tuple(int(c) for c in value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
    return default


def _safe_color(
    value: Any,
    default: tuple[int, int, int] | None,
) -> tuple[int, int, int] | None:
    """Same as :func:`_safe_rgb` but ``None`` round-trips through the
    on-disk JSON representation.

    Stored as ``null`` in the user-settings dict; reading back ``None``
    or a missing key both yield the supplied ``default`` (which itself
    may be ``None``). Anything else is forwarded to ``_safe_rgb``.
    """
    if value is None:
        return _clamp_color(default)
    return _safe_rgb(value, default)
