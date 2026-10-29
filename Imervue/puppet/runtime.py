"""Public per-frame puppet evaluation and batch composition."""
from __future__ import annotations

import numpy as np

from Imervue.puppet.document import PuppetDocument
from Imervue.puppet.runtime_parameters import (
    sample_parameter_forms,
    merge_parameter_samples,
    default_parameter_values,
)
from Imervue.puppet.runtime_blends import (
    sample_blend_forms,
)
from Imervue.puppet.runtime_morphs import (
    apply_vertex_morphs,
    _rest_vertices_array,
)
from Imervue.puppet.runtime_geometry import (
    compose_drawable_vertices,
)
from Imervue.puppet.runtime_deformer_order import (
    topologically_sorted_deformers,
)
from Imervue.puppet.runtime_appearance import (
    resolve_drawable_opacity,
    resolve_drawable_color,
)
from Imervue.puppet.runtime_overlays import (
    apply_expression,
    apply_expressions,
    resolve_pose_visibility,
)
from Imervue.puppet.runtime_parts import (
    resolve_part_state,
)


__all__ = [
    "sample_parameter_forms",
    "merge_parameter_samples",
    "default_parameter_values",
    "sample_blend_forms",
    "apply_vertex_morphs",
    "_rest_vertices_array",
    "compose_drawable_vertices",
    "topologically_sorted_deformers",
    "resolve_drawable_opacity",
    "resolve_drawable_color",
    "apply_expression",
    "apply_expressions",
    "resolve_pose_visibility",
    "resolve_part_state",
    "compose_all_drawables",
]


def compose_all_drawables(
    document: PuppetDocument, values: dict[str, float],
) -> dict[str, np.ndarray]:
    """Convenience: run :func:`compose_drawable_vertices` for every
    drawable in ``document``, returning a ``{drawable_id: verts}`` map.
    Caller is the canvas's per-frame paint."""
    overrides = merge_parameter_samples(document, values)
    parameters_by_id = {p.id: p for p in document.parameters}
    sorted_deformers = topologically_sorted_deformers(document.deformers)
    return {
        d.id: compose_drawable_vertices(
            d, document.deformers, overrides,
            parameter_values=values, parameters_by_id=parameters_by_id,
            sorted_deformers=sorted_deformers,
        )
        for d in document.drawables
    }
