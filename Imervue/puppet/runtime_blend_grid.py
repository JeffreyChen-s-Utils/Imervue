"""Collect sparse blend-grid corners and reduce their form maps by axis."""
from __future__ import annotations

from typing import Any

from Imervue.puppet.document import BlendKey, ParameterBlend
from Imervue.puppet.runtime_forms import _blend_forms_dicts, _copy_forms


def _reduce_axis(
    corners: dict[tuple[int, ...], dict[str, dict[str, Any]]],
    axis: int,
    t: float,
) -> dict[tuple[int, ...], dict[str, dict[str, Any]]]:
    """One step of the cartesian-product reduction along ``axis``: pair
    each 0-side corner with its 1-side neighbour, blend them, and key
    the result by the remaining axis bits. 1-side entries whose paired
    0-side already lives in ``corners`` are dropped here so the merge
    runs exactly once per pair."""
    next_corners: dict[tuple[int, ...], dict[str, dict[str, Any]]] = {}
    for key, form_map in corners.items():
        head, tail = key[:axis], key[axis + 1:]
        sub_key = head + tail
        if key[axis] == 0:
            pair_form = corners.get(head + (1,) + tail)
            blended = (
                _blend_forms_dicts(form_map, pair_form, t)
                if pair_form is not None else form_map
            )
        else:
            # Already merged when we processed the 0-side key.
            if head + (0,) + tail in corners:
                continue
            blended = form_map
        next_corners[sub_key] = blended
    return next_corners


def _reduce_corners(
    blend: ParameterBlend,
    brackets: list[tuple[float, float, float]],
) -> dict[str, dict[str, Any]]:
    """Walk the ``2 ** N`` cartesian-product corners of the bracket box
    and N-D-linearly blend the deformer forms into a single override
    dict. Missing corners are skipped — their absence shows up as
    "no override for that deformer at that corner", which the rest of
    the pipeline already tolerates.
    """
    corners = _collect_corner_keys(blend, brackets)
    if not corners:
        return {}
    # Walk axes from last to first so the early reductions collapse the
    # innermost varying dimension first — the order of axis reduction
    # doesn't change the result for linear interpolation but doing
    # high-to-low keeps the integer-key arithmetic obvious.
    for axis in range(len(brackets) - 1, -1, -1):
        corners = _reduce_axis(corners, axis, brackets[axis][2])
    return next(iter(corners.values()))


def _collect_corner_keys(
    blend: ParameterBlend,
    brackets: list[tuple[float, float, float]],
) -> dict[tuple[int, ...], dict[str, dict[str, Any]]]:
    """Find the :class:`BlendKey` for every cartesian-product corner of
    the bracket. Returns ``{(0|1, 0|1, ...): forms}``.
    """
    coord_lookup: dict[tuple[float, ...], BlendKey] = {}
    for key in blend.keys:
        coord_lookup[tuple(float(c) for c in key.coords)] = key
    n_axes = len(brackets)
    out: dict[tuple[int, ...], dict[str, dict[str, Any]]] = {}
    for mask in range(1 << n_axes):
        coords = tuple(
            brackets[axis][1 if (mask >> axis) & 1 else 0]
            for axis in range(n_axes)
        )
        match = coord_lookup.get(coords)
        if match is None:
            continue
        bits = tuple((mask >> axis) & 1 for axis in range(n_axes))
        out[bits] = _copy_forms(match.forms)
    return out
