"""Normalize live brush and fill field values without changing snapshot identity."""
from __future__ import annotations

from dataclasses import replace
from functools import partial
from typing import Any

from Imervue.paint.tool_state_settings import (
    BRUSH_SIZE_MIN, BRUSH_SIZE_MAX, FILL_TOLERANCE_MIN, FILL_TOLERANCE_MAX,
    FILL_EXPAND_MIN, FILL_EXPAND_MAX, FILL_GAP_CLOSE_MIN, FILL_GAP_CLOSE_MAX,
)


def _clamp(value: Any, *, convert: type, minimum: float, maximum: float) -> Any:
    return max(minimum, min(maximum, convert(value)))


def _tip_path(value: Any) -> str | None:
    return str(value) if value else None


def _identity(value: Any) -> Any:
    return value


_UNIT_FLOAT = partial(_clamp, convert=float, minimum=0.0, maximum=1.0)
_BRUSH_CONVERTERS = dict.fromkeys(
    ("opacity", "hardness", "density", "stabilizer", "scatter", "color_jitter"),
    _UNIT_FLOAT,
)
_BRUSH_CONVERTERS.update({
    "size": partial(_clamp, convert=int, minimum=BRUSH_SIZE_MIN, maximum=BRUSH_SIZE_MAX),
    "follow_tilt": bool,
    "tip_path": _tip_path,
})
_FILL_CONVERTERS = {
    "tolerance": partial(
        _clamp, convert=int, minimum=FILL_TOLERANCE_MIN, maximum=FILL_TOLERANCE_MAX,
    ),
    "expand_px": partial(_clamp, convert=int, minimum=FILL_EXPAND_MIN, maximum=FILL_EXPAND_MAX),
    "gap_close_px": partial(
        _clamp, convert=int, minimum=FILL_GAP_CLOSE_MIN, maximum=FILL_GAP_CLOSE_MAX,
    ),
    "contiguous": bool,
    "sample_all_layers": bool,
    "use_reference_layer": bool,
}


def _clamp_brush_attr(key: str, value: Any) -> Any:
    return _BRUSH_CONVERTERS.get(key, _identity)(value)


def _clamp_fill_attr(key: str, value: Any) -> Any:
    return _FILL_CONVERTERS.get(key, _identity)(value)


def replace_settings(settings: Any, changes: dict, normalize: Any, label: str) -> Any:
    """Build a replacement atomically, retaining field validation and input order."""
    new = settings
    for key, value in changes.items():
        if not hasattr(settings, key):
            raise ValueError(f"unknown {label} attribute {key!r}")
        new = replace(new, **{key: normalize(key, value)})
    return new
