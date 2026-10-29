"""Rest-pose wiring for the native Cubism conversion.

Turns the textures, drawables and parameters a loaded ``.moc3`` reports
into their :mod:`puppet.document` counterparts, and owns the canvas
transform from Cubism's centred, Y-up units to puppet pixels. Split out
of :mod:`puppet.cubism_native_convert`, which re-exports every name.
"""
from __future__ import annotations

import logging
from pathlib import Path

from Imervue.puppet.cubism_native_bridge import DrawableInfo, ParameterInfo
from Imervue.puppet.document import Drawable, Parameter, PuppetDocument

# Same logger as the converter, so its records keep their source name.
logger = logging.getLogger("Imervue.plugin.puppet.cubism_native_convert")


class _CanvasTransform:
    """Cubism stores drawable vertex positions in canvas-normalized
    units with Y pointing up, origin at the canvas centre. Our puppet
    coordinate system is top-left origin pixels with Y pointing down.
    This helper does the conversion both ways."""

    __slots__ = ("pixels_per_unit", "origin_x", "origin_y")

    def __init__(self, pixels_per_unit: float, origin_x: float, origin_y: float):
        self.pixels_per_unit = float(pixels_per_unit) or 1.0
        self.origin_x = float(origin_x)
        self.origin_y = float(origin_y)

    @classmethod
    def from_canvas_info(cls, info: dict) -> _CanvasTransform:
        return cls(
            pixels_per_unit=info.get("pixels_per_unit", 1.0),
            origin_x=info.get("origin_x", 0.0),
            origin_y=info.get("origin_y", 0.0),
        )

    def position(self, x: float, y: float) -> tuple[float, float]:
        return (
            x * self.pixels_per_unit + self.origin_x,
            self.origin_y - y * self.pixels_per_unit,
        )

    def delta(self, dx: float, dy: float) -> tuple[float, float]:
        # Origin offset cancels for a delta; only the unit scale +
        # Y-axis flip apply.
        return (dx * self.pixels_per_unit, -dy * self.pixels_per_unit)


# ---------------------------------------------------------------------------
# Texture + drawable + parameter wiring
# ---------------------------------------------------------------------------


def _attach_textures(
    document: PuppetDocument, file_refs: dict, base_dir: Path,
) -> None:
    """Load every texture listed under ``FileReferences.Textures`` and
    register it under ``textures/texture_NN.png`` so the in-archive
    paths stay short."""
    textures = file_refs.get("Textures") or []
    for index, rel in enumerate(textures):
        src = base_dir / rel
        if not src.is_file():
            logger.warning("texture %s missing on disk", src)
            continue
        archive_path = f"textures/texture_{index:02d}.png"
        document.textures[archive_path] = src.read_bytes()


def _attach_drawables(
    document: PuppetDocument,
    drawables_rest: list[DrawableInfo],
    file_refs: dict,
    transform: _CanvasTransform,
) -> None:
    """Turn each Cubism drawable into a :class:`Drawable`. Vertex
    positions captured at the model's default parameter values give
    the rest pose.

    Drawables that Cubism marks as not-visible at the rest pose get
    ``visible=False`` so e.g. back-of-body fragments don't render on
    top of their front-of-body counterparts. The atlases pack both
    sides of every part — without the visibility filter the result
    is an unreadable mash of mixed-orientation pieces."""
    n_textures = len(file_refs.get("Textures") or [])
    id_by_index = {i: info.id for i, info in enumerate(drawables_rest)}
    for info in drawables_rest:
        vertices = [
            transform.position(info.positions[i], info.positions[i + 1])
            for i in range(0, len(info.positions), 2)
        ]
        # Cubism stores UV with V pointing up; our texture sampler is
        # V-down so we flip on import.
        uvs = [
            (info.uvs[i], 1.0 - info.uvs[i + 1])
            for i in range(0, len(info.uvs), 2)
        ]
        tex_index = info.texture_index
        texture = f"textures/texture_{tex_index:02d}.png" if 0 <= tex_index < n_textures else ""
        # Cubism allows multiple mask drawables per drawable but our
        # schema is single-mask. Take the first available — most rigs
        # only define one anyway.
        clip_mask = (
            id_by_index.get(info.mask_drawable_indices[0])
            if info.mask_drawable_indices else None
        )
        document.drawables.append(Drawable(
            id=info.id,
            texture=texture,
            vertices=vertices,
            indices=list(info.indices),
            uvs=uvs,
            # csmGetRenderOrders gives the actual per-frame paint
            # order; csmGetDrawableDrawOrders is the authoring-time
            # baseline that often comes back as a flat 500 for every
            # drawable. Use render order so the .puppet renders in
            # the same back-to-front sequence Cubism would.
            draw_order=info.render_order,
            blend_mode=_translate_blend_mode(info.blend_mode),
            opacity=info.opacity,
            visible=info.is_visible,
            clip_mask=clip_mask,
        ))


def _translate_blend_mode(cubism_mode: int) -> str:
    """Cubism blend modes: 0=normal, 1=additive, 2=multiplicative.
    Our schema uses the string names — translate directly."""
    return {0: "normal", 1: "additive", 2: "multiply"}.get(cubism_mode, "normal")


def _attach_parameters(
    document: PuppetDocument, parameters: list[ParameterInfo],
) -> None:
    """Register each Cubism parameter on the document. No keyforms
    needed — the deformation comes from per-drawable vertex morphs."""
    for info in parameters:
        document.parameters.append(Parameter(
            id=info.id,
            min=info.minimum,
            max=info.maximum,
            default=info.default,
        ))
