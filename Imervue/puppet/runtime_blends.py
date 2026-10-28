"""Bracket each parameter axis for multi-axis form sampling."""
from __future__ import annotations

from typing import Any

from Imervue.puppet.document import ParameterBlend
from Imervue.puppet.runtime_blend_grid import _reduce_corners
from Imervue.puppet.runtime_interpolation import bracket


def sample_blend_forms(
    blend: ParameterBlend, values: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """N-D linear sample of ``blend`` at the current parameter values.

    Returns ``{deformer_id: form_override}``. Empty when the blend has
    no keys or no parameters. Missing parameter values use the lowest
    coordinate on their axis; an axis with a single finite coordinate
    samples that coordinate without interpolation.

    Algorithm: for each axis, find the bracketing pair of distinct key
    coords around the current parameter value (clamping to the edge
    coord when out of range). Build the ``2 ** N`` corner keys at the
    cartesian product of those brackets, then progressively reduce
    along each axis using :func:`blend_forms`.
    """
    if not blend.parameters or not blend.keys:
        return {}
    coords_by_axis = [sorted({k.coords[i] for k in blend.keys})
                      for i in range(len(blend.parameters))]
    brackets = []
    for param_id, coords in zip(blend.parameters, coords_by_axis, strict=True):
        value = float(values.get(param_id, coords[0]))
        lo, hi, t = bracket(coords, value, fallback_to_span=True)
        brackets.append((coords[lo], coords[hi], t))
    return _reduce_corners(blend, brackets)
