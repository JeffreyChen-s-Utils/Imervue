"""Native PaintDocument save / load — `.imervue` NPZ bundle.

The format is a single NPZ archive containing:

* ``_metadata`` — a 0-D numpy array holding a JSON string with
  ``format_version`` (int), ``width``, ``height``, ``active_layer``,
  and a ``layers`` list — one dict per layer carrying every flag
  (name, opacity, blend_mode, visible, locked, lock_alpha,
  mask_enabled, clip, has_mask).
* ``layer_<i>_image`` — HxWx4 uint8 RGBA array per layer.
* ``layer_<i>_mask`` — HxW uint8 mask per layer (only present when
  ``has_mask`` is true in the metadata).
* ``selection`` — HxW bool array (only present when the document
  has an active selection).

Why NPZ rather than a custom binary or a PSD-lite format:

* No bespoke parsing — ``np.savez_compressed`` / ``np.load`` cover
  read and write end-to-end. Less surface for off-by-one bugs.
* ``allow_pickle=False`` on load defends against a malicious file
  trying to execute pickled code. The format intentionally does
  not store any Python objects — only arrays + a JSON metadata
  string — so the loader is safe even on hostile input.
* Compression is on by default so a 50-layer 4K painting still
  fits in a single distributable file.

The format version is bumped only on breaking changes; loaders
should reject unknown versions rather than guessing.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from Imervue.paint.adjustments import Adjustment
from Imervue.paint.compositing import LAYER_BLEND_MODES
from Imervue.paint.document import (
    GROUP_BLEND_MODES,
    Layer,
    LayerGroup,
    PaintDocument,
)

FORMAT_VERSION = 1
FILE_EXTENSION = ".imervue"


def save_document(document: PaintDocument, path: str | Path) -> None:
    """Write ``document`` to a ``.imervue`` NPZ bundle.

    The path is created or overwritten. Empty documents (no layers)
    raise ``ValueError`` — saving a document with nothing in it makes
    no sense and trips up the loader.
    """
    layers = document.layers()
    if not layers:
        raise ValueError("cannot save an empty document — no layers to write")
    shape = document.shape
    if shape is None:
        raise ValueError("cannot save document with unknown shape")
    h, w = shape

    layers_meta: list[dict] = []
    arrays: dict[str, np.ndarray] = {}
    for i, layer in enumerate(layers):
        layers_meta.append({
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
        })
        arrays[f"layer_{i}_image"] = layer.image
        if layer.mask is not None:
            arrays[f"layer_{i}_mask"] = layer.mask

    groups_meta = [
        {
            "name": grp.name,
            "visible": bool(grp.visible),
            "opacity": float(grp.opacity),
            "blend_mode": str(grp.blend_mode),
            "locked": bool(grp.locked),
            "expanded": bool(grp.expanded),
        }
        for grp in document.groups()
    ]

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
        "groups": groups_meta,
        "named_selections": named_selection_names,
    }
    arrays["_metadata"] = np.array(json.dumps(metadata))
    selection = document.selection()
    if selection is not None:
        arrays["selection"] = selection

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Pass a file object to bypass numpy's auto-".npz" suffix munging —
    # the project uses ``.imervue`` as the user-facing extension and
    # ``np.savez_compressed`` would otherwise append ``.npz`` silently.
    with open(target, "wb") as fh:
        np.savez_compressed(fh, **arrays)


def load_document(path: str | Path) -> PaintDocument:
    """Load a ``.imervue`` bundle and return a fresh PaintDocument.

    Raises ``ValueError`` for unknown format versions, missing
    arrays, or shape mismatches between layers. Always loads with
    ``allow_pickle=False`` so a malicious file cannot execute
    arbitrary code via the numpy loader.
    """
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"document {target!s} does not exist")
    with open(target, "rb") as fh, np.load(fh, allow_pickle=False) as data:
        metadata = _read_metadata(data)
        layers, active_index = _read_layers(data, metadata)
        selection = _read_selection(data, metadata)
        groups = _read_groups(metadata)
        named_selections = _read_named_selections(data, metadata)
    document = PaintDocument()
    document.replace_state(
        layers=layers,
        active_index=active_index,
        selection=selection,
        groups=groups,
        named_selections=named_selections,
    )
    return document


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _read_metadata(data) -> dict:
    if "_metadata" not in data.files:
        raise ValueError("document is missing the _metadata entry")
    raw = str(data["_metadata"].item()) if data["_metadata"].ndim == 0 else str(data["_metadata"])
    try:
        metadata = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"document metadata is not valid JSON: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError(f"metadata must be an object, got {type(metadata).__name__}")
    version = metadata.get("format_version")
    if version != FORMAT_VERSION:
        raise ValueError(
            f"unsupported document format version {version!r}; "
            f"this build understands {FORMAT_VERSION}",
        )
    if not isinstance(metadata.get("layers"), list) or not metadata["layers"]:
        raise ValueError("document metadata has no layers")
    return metadata


def _read_layers(data, metadata: dict) -> tuple[list[Layer], int]:
    width = int(metadata["width"])
    height = int(metadata["height"])
    layers: list[Layer] = []
    for i, lmeta in enumerate(metadata["layers"]):
        if not isinstance(lmeta, dict):
            raise ValueError(f"layer {i} metadata must be an object")
        image_key = f"layer_{i}_image"
        if image_key not in data.files:
            raise ValueError(f"document is missing array {image_key!r}")
        image = np.ascontiguousarray(data[image_key])
        if image.shape != (height, width, 4):
            raise ValueError(
                f"layer {i} shape {image.shape} does not match "
                f"document {(height, width, 4)}",
            )
        if image.dtype != np.uint8:
            raise ValueError(
                f"layer {i} dtype {image.dtype} must be uint8",
            )
        blend_mode = str(lmeta.get("blend_mode", "normal"))
        if blend_mode not in LAYER_BLEND_MODES:
            blend_mode = "normal"
        mask = None
        if lmeta.get("has_mask"):
            mask_key = f"layer_{i}_mask"
            if mask_key not in data.files:
                raise ValueError(f"document is missing array {mask_key!r}")
            mask = np.ascontiguousarray(data[mask_key])
            if mask.shape != (height, width):
                raise ValueError(
                    f"layer {i} mask shape {mask.shape} does not match "
                    f"document {(height, width)}",
                )
        group_name = lmeta.get("group")
        adjustment_raw = lmeta.get("adjustment")
        adjustment = None
        if isinstance(adjustment_raw, dict):
            try:
                adjustment = Adjustment.from_dict(adjustment_raw)
            except (ValueError, TypeError):
                adjustment = None
        layers.append(Layer(
            name=str(lmeta.get("name", f"Layer {i}")),
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
            adjustment=adjustment,
        ))
    active = int(metadata.get("active_layer", 0))
    active = max(0, min(active, len(layers) - 1))
    return layers, active


def _read_groups(metadata: dict) -> dict[str, LayerGroup]:
    """Rebuild the group registry from metadata. Older saves without
    a ``groups`` key produce an empty registry — Layer.group references
    that don't resolve are tolerated by the compositor (treated as
    top-level layers)."""
    raw = metadata.get("groups")
    if not isinstance(raw, list):
        return {}
    out: dict[str, LayerGroup] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        blend = str(entry.get("blend_mode", "pass_through"))
        if blend not in GROUP_BLEND_MODES:
            blend = "pass_through"
        try:
            out[name] = LayerGroup(
                name=name,
                visible=bool(entry.get("visible", True)),
                opacity=float(entry.get("opacity", 1.0)),
                blend_mode=blend,
                locked=bool(entry.get("locked", False)),
                expanded=bool(entry.get("expanded", True)),
            )
        except (ValueError, TypeError):
            continue
    return out


def _read_named_selections(
    data, metadata: dict,
) -> dict[str, np.ndarray]:
    """Reconstruct the named-selection registry from the save bundle.

    Older saves without the metadata key produce an empty dict so the
    document still loads cleanly."""
    names = metadata.get("named_selections")
    if not isinstance(names, list):
        return {}
    out: dict[str, np.ndarray] = {}
    expected_shape = (int(metadata["height"]), int(metadata["width"]))
    for i, name in enumerate(names):
        key = f"named_selection_{i}"
        if key not in data.files:
            continue
        mask = np.ascontiguousarray(data[key])
        if mask.dtype != np.bool_ or mask.shape != expected_shape:
            continue
        out[str(name)] = mask
    return out


def _read_selection(data, metadata: dict) -> np.ndarray | None:
    if "selection" not in data.files:
        return None
    sel = np.ascontiguousarray(data["selection"])
    if sel.dtype != np.bool_:
        raise ValueError(
            f"selection dtype {sel.dtype} must be bool",
        )
    if sel.shape != (int(metadata["height"]), int(metadata["width"])):
        raise ValueError(
            f"selection shape {sel.shape} does not match document",
        )
    return sel
