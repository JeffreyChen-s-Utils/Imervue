"""PSD multi-layer → ``PuppetDocument`` import.

Live2D's authoring workflow is "draw the character in Photoshop with
each part on its own layer, drop into Cubism Editor, every layer
becomes an ArtMesh." This module is the puppet plugin's equivalent:
each visible layer in the PSD turns into one cropped :class:`Drawable`
positioned at its alpha bounding box.

Built on the project's pure-Python PSD reader in
:mod:`Imervue.paint.psd_io` so the puppet plugin doesn't pull in an
external PSD dep. Keeps the texture map tight by cropping each layer
to its alpha bbox — a 4k canvas with eight tiny eye-shaped layers
becomes eight tiny PNGs, not eight 4k-sized PNGs.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np

from Imervue.paint.psd_io import load_psd
from Imervue.puppet.auto_rig import auto_rig
from Imervue.puppet.document import Drawable, Part, PuppetDocument
from Imervue.puppet.standard_params import standard_parameters

_TEXTURE_PREFIX: str = "textures/"


def puppet_from_psd(
    path: str | Path,
    *,
    seed_standard_parameters: bool = True,
    enable_auto_rig: bool = True,
) -> PuppetDocument:
    """Load ``path`` as a PSD and build a multi-drawable
    :class:`PuppetDocument`.

    Hidden layers and layers whose alpha is fully zero are skipped.
    Layer order in the PSD becomes ``draw_order`` on the drawables —
    the bottom of the layer stack is drawn first (behind), the top
    drawn last (in front), matching Live2D's convention.

    Raises :class:`FileNotFoundError` when the file is missing,
    :class:`ValueError` when the PSD has no usable layer.
    """
    paint_doc = load_psd(path)
    layers = paint_doc.layers()
    if not layers:
        raise ValueError(f"PSD {path} has no layers")
    shape = paint_doc.shape
    if shape is None:
        raise ValueError(f"PSD {path} has no resolvable canvas size")
    h, w = shape

    doc = PuppetDocument(size=(w, h))
    used_ids: set[str] = set()
    used_textures: set[str] = set()
    # Track which Part each drawable falls under so we can reconstruct
    # the PSD's layer-group hierarchy as a Part tree afterwards.
    drawables_by_group: dict[str, list[str]] = {}
    for index, layer in enumerate(layers):
        if not layer.visible:
            continue
        bbox = _alpha_bbox(layer.image)
        if bbox is None:
            continue
        drawable = _drawable_from_layer(
            layer, bbox, draw_order=index,
            used_ids=used_ids, used_textures=used_textures,
        )
        doc.drawables.append(drawable)
        doc.textures[drawable.texture] = _crop_to_png_bytes(layer.image, bbox)
        group_name = getattr(layer, "group", None)
        if group_name:
            drawables_by_group.setdefault(str(group_name), []).append(drawable.id)
    if not doc.drawables:
        raise ValueError(f"PSD {path} had no visible non-empty layers")
    doc.parts = _build_parts(drawables_by_group)
    if seed_standard_parameters:
        doc.parameters = standard_parameters()
    if enable_auto_rig:
        auto_rig(doc)
    return doc


def _build_parts(drawables_by_group: dict[str, list[str]]) -> list[Part]:
    """Each PSD layer group becomes a flat Part whose ``drawables``
    are the layers inside it. PSDs can nest groups, but the v1 paint
    document flattens nested groups during PSD load, so a flat list
    here is the most faithful representation we can recover without
    re-parsing the original archive."""
    return [
        Part(id=_sanitize_id(name), drawables=list(ids))
        for name, ids in drawables_by_group.items()
    ]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _alpha_bbox(image: np.ndarray) -> tuple[int, int, int, int] | None:
    """Return ``(x0, y0, x1, y1)`` of the smallest box covering all
    pixels where ``alpha > 0``, or ``None`` for fully transparent
    images. ``x1`` / ``y1`` are exclusive so the slice
    ``image[y0:y1, x0:x1]`` returns exactly the cropped region."""
    if image.ndim != 3 or image.shape[2] != 4:
        return None
    alpha = image[..., 3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if not rows.any() or not cols.any():
        return None
    y0 = int(np.argmax(rows))
    y1 = int(len(rows) - np.argmax(rows[::-1]))
    x0 = int(np.argmax(cols))
    x1 = int(len(cols) - np.argmax(cols[::-1]))
    return x0, y0, x1, y1


def _drawable_from_layer(
    layer,
    bbox: tuple[int, int, int, int],
    *,
    draw_order: int,
    used_ids: set[str],
    used_textures: set[str],
) -> Drawable:
    drawable_id = _unique(_sanitize_id(layer.name), used_ids)
    texture_path = _unique(
        f"{_TEXTURE_PREFIX}{drawable_id}.png", used_textures,
    )
    x0, y0, x1, y1 = bbox
    return Drawable(
        id=drawable_id,
        texture=texture_path,
        vertices=[
            (float(x0), float(y0)),
            (float(x1), float(y0)),
            (float(x1), float(y1)),
            (float(x0), float(y1)),
        ],
        indices=[0, 1, 2, 0, 2, 3],
        uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        draw_order=draw_order,
        opacity=float(layer.opacity),
    )


def _crop_to_png_bytes(
    image: np.ndarray, bbox: tuple[int, int, int, int],
) -> bytes:
    from PIL import Image
    x0, y0, x1, y1 = bbox
    crop = image[y0:y1, x0:x1]
    buf = io.BytesIO()
    Image.fromarray(crop, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def _sanitize_id(name: str) -> str:
    """Map a PSD layer name to a safe drawable id. Strips characters
    that would confuse the manifest / texture-path layer (slashes,
    quotes, etc.) and falls back to ``layer`` when everything was
    stripped. PSDs let users name layers ``私の/絵🎨`` — we keep the
    intent without crashing the schema."""
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_")
    return safe or "layer"


def _unique(candidate: str, used: set[str]) -> str:
    """Suffix ``candidate`` with ``_2``, ``_3`` … until it's not in
    ``used``, then record the result."""
    if candidate not in used:
        used.add(candidate)
        return candidate
    i = 2
    while True:
        alt = f"{candidate}_{i}"
        if alt not in used:
            used.add(alt)
            return alt
        i += 1
