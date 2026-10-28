"""Apply parameter-driven vertex offsets and cache rest geometry."""
from __future__ import annotations

import numpy as np

from Imervue.puppet.document import Drawable, Parameter


def _resolve_morph_side(
    morph: dict, parameter: Parameter, value: float,
) -> tuple[np.ndarray, float] | None:
    """Return ``(deltas, t)`` for the side the parameter is currently
    pulling toward — min or max — or ``None`` if the parameter sits
    at its default (no morph contribution) or has a zero-span on
    that side (avoid div-by-zero)."""
    if value < parameter.default:
        span = parameter.default - parameter.min
        if span <= 0:
            return None
        t = max(0.0, min(1.0, (parameter.default - value) / span))
        deltas = _morph_delta_array(morph, "delta_at_min", "_np_delta_at_min")
    elif value > parameter.default:
        span = parameter.max - parameter.default
        if span <= 0:
            return None
        t = max(0.0, min(1.0, (value - parameter.default) / span))
        deltas = _morph_delta_array(morph, "delta_at_max", "_np_delta_at_max")
    else:
        return None
    if deltas is None or deltas.size == 0:
        return None
    return deltas, t


def apply_vertex_morphs(
    rest_vertices: np.ndarray,
    morphs: list[dict] | None,
    parameter_values: dict[str, float],
    parameters_by_id: dict[str, Parameter],
) -> np.ndarray:
    """Apply :attr:`Drawable.vertex_morphs` linearly between the
    parameter's default and its min / max extremes.

    For each morph: when the parameter sits at its default value the
    morph contributes zero; values between default and the relevant
    extreme blend linearly toward ``delta_at_min`` or ``delta_at_max``.
    Out-of-range values clamp to the corresponding extreme. Missing
    parameters (or morphs targeting unknown parameters) silently
    skip — keeps a partial document well-defined.

    Hot path for Cubism-converted rigs: a 307-drawable / 2965-morph
    imported model gets ~10000 calls per second through this. The
    deltas get cached as numpy arrays in private morph-dict keys so
    the first call pays the conversion cost and every subsequent
    call is a pure vector ``add`` — ~100× faster than the per-vertex
    Python loop that lived here before."""
    if not morphs:
        return rest_vertices
    out = rest_vertices.copy()
    for morph in morphs:
        param_id = morph.get("parameter")
        if not isinstance(param_id, str):
            continue
        parameter = parameters_by_id.get(param_id)
        if parameter is None:
            continue
        value = float(parameter_values.get(param_id, parameter.default))
        side = _resolve_morph_side(morph, parameter, value)
        if side is None:
            continue
        deltas, t = side
        n = min(deltas.shape[0], out.shape[0])
        # Vectorised add — replaces the per-vertex Python loop.
        out[:n] += deltas[:n] * t
    return out


def _morph_delta_array(
    morph: dict, raw_key: str, cache_key: str,
) -> np.ndarray | None:
    """Lazy-cache the numpy version of a morph's delta list on the
    morph dict itself. Keys prefixed ``_np_`` are stripped during
    serialisation so they never reach disk."""
    cached = morph.get(cache_key)
    if cached is not None:
        return cached
    raw = morph.get(raw_key)
    if not raw:
        return None
    arr = np.asarray(raw, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 2)
    morph[cache_key] = arr
    return arr


def _rest_vertices_array(drawable: Drawable) -> np.ndarray:
    """Lazy-cache the numpy float32 form of a drawable's rest vertices.

    ``Drawable.vertices`` is a list of ``(x, y)`` tuples — fine for
    serialisation but pricey to re-pack into a numpy array every frame.
    For a 307-drawable rig at 60 fps the conversion alone burned ~3 ms
    of every paint. Cache it as a private attribute so subsequent
    frames just return the array pointer."""
    cached = getattr(drawable, "_np_rest_vertices", None)
    if cached is not None:
        return cached
    arr = np.asarray(drawable.vertices, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 2)
    drawable._np_rest_vertices = arr   # noqa: SLF001 — private cache slot
    return arr
