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

import io
import json
from pathlib import Path

import numpy as np

from Imervue.system.atomic_write import replace_atomically
from Imervue.paint.document import (
    GROUP_BLEND_MODES,
    LayerGroup,
    PaintDocument,
)
# The encoder and the layer decoder live in sibling modules; FORMAT_VERSION
# and _document_to_arrays are re-exported so callers keep importing them here.
from Imervue.paint.document_io_layers import _read_layers
from Imervue.paint.document_io_write import FORMAT_VERSION, _document_to_arrays
from Imervue.paint.manga_panels import panel_layout_from_dict

FILE_EXTENSION = ".imervue"


def save_document(document: PaintDocument, path: str | Path) -> None:
    """Write ``document`` to a ``.imervue`` NPZ bundle; a failure keeps the old file whole."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    arrays = _document_to_arrays(document)

    def write(tmp: Path) -> None:
        # Pass a file object to bypass numpy's auto-".npz" suffix munging —
        # the project uses ``.imervue`` as the user-facing extension and
        # ``np.savez_compressed`` would otherwise append ``.npz`` silently.
        with open(tmp, "wb") as fh:
            np.savez_compressed(fh, **arrays)

    replace_atomically(target, write)


def save_document_to_buffer(document: PaintDocument) -> bytes:
    """Serialise ``document`` to an in-memory NPZ blob.

    Used by the project_io layer to pack each page into a parent
    archive without first writing it to disk. The byte format is
    identical to :func:`save_document`'s on-disk output.
    """
    arrays = _document_to_arrays(document)
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    return buffer.getvalue()


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
        return _document_from_npz(data)


def load_document_from_buffer(blob: bytes) -> PaintDocument:
    """Deserialise an in-memory NPZ blob produced by
    :func:`save_document_to_buffer` back into a PaintDocument.

    Used by project_io to unpack each page from the parent archive."""
    with io.BytesIO(blob) as fh, np.load(fh, allow_pickle=False) as data:
        return _document_from_npz(data)


def _document_from_npz(data) -> PaintDocument:
    """Normalize malformed bundle fields at the shared file/buffer boundary."""
    try:
        return _decode_document_npz(data)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError(f"invalid document metadata: {exc}") from exc


def _decode_document_npz(data) -> PaintDocument:
    """Turn validated metadata and arrays into a PaintDocument."""
    metadata = _read_metadata(data)
    layers, active_index = _read_layers(data, metadata)
    selection = _read_selection(data, metadata)
    groups = _read_groups(metadata)
    named_selections = _read_named_selections(data, metadata)
    document = PaintDocument()
    raw_ref = metadata.get("reference_layer")
    reference_index = (
        raw_ref
        if isinstance(raw_ref, int) and 0 <= raw_ref < len(layers)
        else None
    )
    document.replace_state(
        layers=layers,
        active_index=active_index,
        selection=selection,
        groups=groups,
        named_selections=named_selections,
        reference_layer_index=reference_index,
    )
    document.panel_layout = panel_layout_from_dict(metadata.get("panel_layout"))
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
    for key in ("width", "height"):
        value = metadata.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"document {key} must be a positive integer")
    return metadata


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
