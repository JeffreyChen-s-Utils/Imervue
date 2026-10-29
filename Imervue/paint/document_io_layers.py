"""Layer decoder half of the native ``.imervue`` bundle loader.

Turns each per-layer metadata dict plus its ``layer_<i>_image`` /
``layer_<i>_mask`` arrays back into a :class:`Layer`, validating shapes
and dtypes and dropping damaged optional sub-features.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.adjustments import Adjustment
from Imervue.paint.compositing import LAYER_BLEND_MODES
from Imervue.paint.document import Layer
from Imervue.paint.layer_effects import LayerEffect


def _read_layers(data, metadata: dict) -> tuple[list[Layer], int]:
    width = int(metadata["width"])
    height = int(metadata["height"])
    layers: list[Layer] = []
    for i, lmeta in enumerate(metadata["layers"]):
        if not isinstance(lmeta, dict):
            raise ValueError(f"layer {i} metadata must be an object")
        layers.append(_read_layer(data, lmeta, i, width, height))
    active = int(metadata.get("active_layer", 0))
    active = max(0, min(active, len(layers) - 1))
    return layers, active


def _read_layer(
    data, lmeta: dict, index: int, width: int, height: int,
) -> Layer:
    """Materialise one ``Layer`` from a save-file metadata + array
    blob. Splits the steps into shape-validate, mask-load, and
    sub-feature decode helpers so the parent function stays under
    the cognitive-complexity ceiling."""
    image = _read_layer_image(data, index, width, height)
    mask = _read_layer_mask(data, lmeta, index, width, height)
    blend_mode = str(lmeta.get("blend_mode", "normal"))
    if blend_mode not in LAYER_BLEND_MODES:
        blend_mode = "normal"
    group_name = lmeta.get("group")
    from Imervue.paint.binary_layer import BinarySettings
    from Imervue.paint.halftone import ToneSettings
    return Layer(
        name=str(lmeta.get("name", f"Layer {index}")),
        image=image,
        opacity=float(lmeta.get("opacity", 1.0)),
        blend_mode=blend_mode,
        visible=bool(lmeta.get("visible", True)),
        locked=bool(lmeta.get("locked", False)),
        mask=mask,
        mask_enabled=bool(lmeta.get("mask_enabled", True)),
        clip=bool(lmeta.get("clip", False)),
        lock_alpha=bool(lmeta.get("lock_alpha", False)),
        group=str(group_name) if group_name else None,
        adjustment=_read_layer_adjustment(lmeta.get("adjustment")),
        effects=tuple(_read_layer_effects(lmeta.get("effects") or [])),
        tone=ToneSettings.from_dict(lmeta.get("tone")),
        binary=BinarySettings.from_dict(lmeta.get("binary")),
        blend_if=_read_layer_blend_if(lmeta.get("blend_if")),
        vector_data=_read_layer_vector_data(lmeta.get("vector_strokes")),
        color_label=_read_layer_color_label(lmeta.get("color_label")),
    )


def _read_layer_blend_if(raw: object):
    if not isinstance(raw, dict):
        return None
    from Imervue.paint.blend_if import BlendIf
    return BlendIf.from_dict(raw)


def _read_layer_vector_data(raw: object):
    """``None`` means a plain raster layer; a list (even empty) means
    the layer is a vector layer whose strokes re-rasterise on demand."""
    if not isinstance(raw, list):
        return None
    from Imervue.paint.vector_layer import VectorLayerData, VectorStroke
    strokes = [
        VectorStroke.from_dict(entry)
        for entry in raw if isinstance(entry, dict)
    ]
    return VectorLayerData(strokes=strokes)


def _read_layer_color_label(raw: object) -> str | None:
    from Imervue.paint.layer_model import LAYER_LABELS
    return raw if isinstance(raw, str) and raw in LAYER_LABELS else None


def _read_layer_image(
    data, index: int, width: int, height: int,
) -> np.ndarray:
    image_key = f"layer_{index}_image"
    if image_key not in data.files:
        raise ValueError(f"document is missing array {image_key!r}")
    image = np.ascontiguousarray(data[image_key])
    if image.shape != (height, width, 4):
        raise ValueError(
            f"layer {index} shape {image.shape} does not match "
            f"document {(height, width, 4)}",
        )
    if image.dtype != np.uint8:
        raise ValueError(
            f"layer {index} dtype {image.dtype} must be uint8",
        )
    return image


def _read_layer_mask(
    data, lmeta: dict, index: int, width: int, height: int,
) -> np.ndarray | None:
    if not lmeta.get("has_mask"):
        return None
    mask_key = f"layer_{index}_mask"
    if mask_key not in data.files:
        raise ValueError(f"document is missing array {mask_key!r}")
    mask = np.ascontiguousarray(data[mask_key])
    if mask.shape != (height, width):
        raise ValueError(
            f"layer {index} mask shape {mask.shape} does not match "
            f"document {(height, width)}",
        )
    return mask


def _read_layer_adjustment(raw):
    if not isinstance(raw, dict):
        return None
    try:
        return Adjustment.from_dict(raw)
    except (ValueError, TypeError):
        return None


def _read_layer_effects(raw_list) -> list[LayerEffect]:
    if not isinstance(raw_list, list):
        return []
    effects: list[LayerEffect] = []
    for eff_raw in raw_list:
        try:
            effects.append(LayerEffect.from_dict(eff_raw))
        except (ValueError, TypeError):
            continue
    return effects
