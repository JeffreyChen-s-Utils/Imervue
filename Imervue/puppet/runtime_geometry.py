"""Compose morphs, bone skinning, and ordered rigid deformations."""
from __future__ import annotations

from typing import Any

import numpy as np

from Imervue.puppet.deformers import apply_rotation, apply_warp
from Imervue.puppet.document import Deformer, Drawable, Parameter
from Imervue.puppet.runtime_deformer_order import topologically_sorted_deformers
from Imervue.puppet.runtime_morphs import _rest_vertices_array, apply_vertex_morphs
from Imervue.puppet.runtime_skinning import _compose_bone_lbs, _form_for

_DEFORMER_FUNCS = {"rotation": apply_rotation, "warp": apply_warp}


def _apply_deformer(
    type_: str, vertices: np.ndarray, form: dict[str, Any],
) -> np.ndarray:
    fn = _DEFORMER_FUNCS.get(type_)
    if fn is None:
        return vertices
    return fn(vertices, form)


def compose_drawable_vertices(
    drawable: Drawable,
    deformers: list[Deformer],
    overrides: dict[str, dict[str, Any]],
    *,
    parameter_values: dict[str, float] | None = None,
    parameters_by_id: dict[str, Parameter] | None = None,
    sorted_deformers: list[Deformer] | None = None,
) -> np.ndarray:
    """Apply every deformer that targets ``drawable`` to its neutral
    vertices and return the deformed Nx2 array.

    ``overrides`` is the merged-parameter output from
    :func:`merge_parameter_samples`. A deformer not present in
    ``overrides`` runs with its authored neutral form (= identity in
    practice, since neutral forms produce identity transforms).

    All ``bone_rotation`` deformers targeting this drawable are
    aggregated into a single LBS pass that runs against the rest
    vertices — that's what makes opposing-bone weights cancel correctly
    instead of stacking sequentially. Other deformer types are then
    applied in FK order: a topological sort by ``Deformer.parent``
    ensures a parent rotation/warp always runs before its children,
    even when the document lists them in a different order.

    Performance note: ``sorted_deformers`` lets a batch caller pass
    in the topologically-sorted deformer list once instead of
    recomputing it per drawable. ``compose_all_drawables`` already
    does this — only direct callers need to pass it.
    """
    rest = _rest_vertices_array(drawable)
    # Cubism-style vertex morphs run *before* any deformer pipeline —
    # they replace the rest pose with the parameter-deformed pose
    # that .moc3 conversion captured, then deformers (if any) layer on
    # top.
    if drawable.vertex_morphs and parameter_values is not None and parameters_by_id is not None:
        rest = apply_vertex_morphs(rest, drawable.vertex_morphs, parameter_values, parameters_by_id)
    if sorted_deformers is None:
        sorted_deformers = topologically_sorted_deformers(deformers)
    bone_deformers: list[Deformer] = []
    other_deformers: list[Deformer] = []
    for deformer in sorted_deformers:
        if drawable.id not in deformer.drawables:
            continue
        if deformer.type == "bone_rotation":
            bone_deformers.append(deformer)
        else:
            other_deformers.append(deformer)
    if not bone_deformers and not other_deformers:
        # Fast path: morphs already produced the final vertex set,
        # no deformer chain to layer on top. Skips the redundant
        # bone-LBS branch + the float32 cast since rest is already
        # float32 from ``_rest_vertices_array``.
        return rest
    verts = _compose_bone_lbs(rest, drawable, bone_deformers, overrides)
    for deformer in other_deformers:
        form = _form_for(deformer, overrides)
        verts = _apply_deformer(deformer.type, verts, form)
    return verts.astype(np.float32, copy=False)
