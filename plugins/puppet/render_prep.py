"""Pure-Python preparation of GL-ready draw lists from a ``PuppetDocument``.

Qt-free / GL-free so unit tests can verify ordering, deduplication and
the conversion to numpy arrays without spinning up a context. The
``canvas`` module just consumes the output of :func:`build_draw_list`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from puppet.document import Drawable, PuppetDocument


@dataclass(frozen=True)
class DrawCommand:
    """One GL draw call's worth of data, ready for ``glDrawElements``.

    Vertices, uvs and indices are numpy arrays of the right dtypes; the
    consumer uploads vertex/uv buffers per-drawable but textures are
    cached at the document level (``texture`` is the path inside the zip
    so the canvas can map it to a GL texture id).
    """

    drawable_id: str
    texture: str
    vertices: np.ndarray   # shape (N, 2) float32
    uvs: np.ndarray        # shape (N, 2) float32
    indices: np.ndarray    # shape (M,) uint32
    blend_mode: str
    clip_mask: str | None
    visible: bool
    opacity: float


def build_draw_list(document: PuppetDocument) -> list[DrawCommand]:
    """Return drawables sorted by draw_order (ascending), each turned
    into a :class:`DrawCommand`. Invisible drawables are emitted too so
    the consumer can decide per-frame whether to skip them — the
    visibility flag isn't baked into the list.
    """
    sorted_drawables = sorted(
        document.drawables,
        key=lambda d: (d.draw_order, document.drawables.index(d)),
    )
    return [_to_command(d) for d in sorted_drawables]


def _to_command(d: Drawable) -> DrawCommand:
    return DrawCommand(
        drawable_id=d.id,
        texture=d.texture,
        vertices=np.asarray(d.vertices, dtype=np.float32),
        uvs=np.asarray(d.uvs, dtype=np.float32),
        indices=np.asarray(d.indices, dtype=np.uint32),
        blend_mode=d.blend_mode,
        clip_mask=d.clip_mask,
        visible=d.visible,
        opacity=float(d.opacity),
    )


def collect_required_textures(document: PuppetDocument) -> set[str]:
    """Return the set of texture paths the canvas needs to upload.

    Only paths actually referenced by drawables are returned — the
    document may carry stray texture bytes (e.g. mid-edit) that aren't
    bound yet; the renderer doesn't need those.
    """
    return {d.texture for d in document.drawables}


def fit_view(
    canvas_size: tuple[int, int], puppet_size: tuple[int, int],
) -> tuple[float, float, float]:
    """Compute (zoom, pan_x, pan_y) so the puppet fits centred in a
    canvas of size ``canvas_size``. Margin of 5 % so the puppet doesn't
    sit flush against the window edge.

    ``canvas_size`` is the QOpenGLWidget's drawable size in physical
    pixels (after devicePixelRatio scaling); ``puppet_size`` is the
    document's authoring resolution.
    """
    cw, ch = canvas_size
    pw, ph = puppet_size
    if pw <= 0 or ph <= 0 or cw <= 0 or ch <= 0:
        return 1.0, 0.0, 0.0
    margin = 0.95
    zoom = min(cw / pw, ch / ph) * margin
    pan_x = (cw - pw * zoom) * 0.5
    pan_y = (ch - ph * zoom) * 0.5
    return zoom, pan_x, pan_y


def screen_to_image(
    sx: float, sy: float, zoom: float, pan_x: float, pan_y: float,
) -> tuple[float, float]:
    """Inverse of the canvas's ``glTranslate`` + ``glScale`` so the
    workspace can map mouse positions onto puppet-canvas-space pixels."""
    if zoom == 0:
        return 0.0, 0.0
    return (sx - pan_x) / zoom, (sy - pan_y) / zoom
