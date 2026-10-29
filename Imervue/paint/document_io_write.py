"""Encoder half of the native ``.imervue`` bundle: PaintDocument -> NPZ arrays.

Owns the format version the bundle is written with; :mod:`document_io`
re-exports it and the loader rejects any other version.
"""
from __future__ import annotations

import json

import numpy as np

from Imervue.paint.document import PaintDocument
from Imervue.paint.manga_panels import panel_layout_to_dict

FORMAT_VERSION = 1


def _document_to_arrays(document: PaintDocument) -> dict[str, np.ndarray]:
    """Build the NPZ-array dict that represents one PaintDocument."""
    layers = document.layers()
    if not layers:
        raise ValueError("cannot save an empty document — no layers to write")
    shape = document.shape
    if shape is None:
        raise ValueError("cannot save document with unknown shape")
    h, w = shape

    arrays: dict[str, np.ndarray] = {}
    layers_meta = [_layer_meta(layer) for layer in layers]
    for i, layer in enumerate(layers):
        arrays[f"layer_{i}_image"] = layer.image
        if layer.mask is not None:
            arrays[f"layer_{i}_mask"] = layer.mask

    named_selection_names = list(document.list_named_selections())
    for i, name in enumerate(named_selection_names):
        mask = document.named_selection(name)
        if mask is not None:
            arrays[f"named_selection_{i}"] = mask

    metadata = {
        "format_version": FORMAT_VERSION,
        "width": int(w),
        "height": int(h),
        "active_layer": int(document.active_layer_index()),
        "layers": layers_meta,
        "groups": [_group_meta(grp) for grp in document.groups()],
        "named_selections": named_selection_names,
        "panel_layout": panel_layout_to_dict(document.panel_layout),
        "reference_layer": (
            None
            if document.reference_layer_index() is None
            else int(document.reference_layer_index())
        ),
    }
    arrays["_metadata"] = np.array(json.dumps(metadata))
    selection = document.selection()
    if selection is not None:
        arrays["selection"] = selection
    return arrays


def _layer_meta(layer) -> dict:
    """Per-layer JSON-friendly metadata block."""
    return {
        "name": str(layer.name),
        "opacity": float(layer.opacity),
        "blend_mode": str(layer.blend_mode),
        "visible": bool(layer.visible),
        "locked": bool(layer.locked),
        "lock_alpha": bool(layer.lock_alpha),
        "mask_enabled": bool(layer.mask_enabled),
        "clip": bool(layer.clip),
        "has_mask": layer.mask is not None,
        "group": layer.group,
        "adjustment": (
            layer.adjustment.to_dict()
            if layer.adjustment is not None else None
        ),
        "effects": [eff.to_dict() for eff in (layer.effects or ())],
        "tone": (
            layer.tone.to_dict() if layer.tone is not None else None
        ),
        "binary": (
            layer.binary.to_dict() if layer.binary is not None else None
        ),
        "blend_if": (
            layer.blend_if.to_dict() if layer.blend_if is not None else None
        ),
        # The strokes are the vector layer's canonical state; the image
        # is only a rasterisation cache. Dropping them silently degrades
        # the layer to a raster layer on reload.
        "vector_strokes": (
            [stroke.to_dict() for stroke in layer.vector_data.strokes]
            if layer.vector_data is not None else None
        ),
        "color_label": layer.color_label,
    }


def _group_meta(grp) -> dict:
    """Per-group JSON-friendly metadata block."""
    return {
        "name": grp.name,
        "visible": bool(grp.visible),
        "opacity": float(grp.opacity),
        "blend_mode": str(grp.blend_mode),
        "locked": bool(grp.locked),
        "expanded": bool(grp.expanded),
    }
