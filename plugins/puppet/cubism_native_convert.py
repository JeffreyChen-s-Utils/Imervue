"""Convert a Cubism ``.moc3`` into a :class:`PuppetDocument`.

Uses :mod:`puppet.cubism_native_bridge` (ctypes → Live2DCubismCore.dll)
to load the binary mesh and runtime-deform it. We can't read keyforms
out of the .moc3 directly — Cubism compiles them into a deformation
pipeline that the public API doesn't expose — so the conversion is
**sample-and-reconstruct**:

1. Reset every parameter to its default; capture the rest mesh.
2. For each parameter, sweep to min and max, recording each
   drawable's deformed vertex positions.
3. Subtract rest to get per-vertex deltas. Filter morphs whose
   maximum delta is below a small epsilon — they're noise.
4. Attach the surviving morphs to each drawable's ``vertex_morphs``
   list. The runtime then blends linearly between rest and
   delta_at_min / delta_at_max as the parameter moves.

The result is an approximate rig: linear blending instead of Cubism's
proprietary curve, and parameters are sampled independently so
non-linear cross-parameter interactions don't carry over. Good
enough for "March 7th shows up and her head turns when ``ParamAngleZ``
moves." Not byte-identical to Cubism's runtime, never can be.

Textures, motions, expressions, physics, hit areas, and display
names load through the existing :mod:`puppet.cubism_import` JSON
pipeline. The Cubism SDK is never redistributed — the user supplies
their own DLL path via ``CUBISM_CORE_DLL`` or a standard
``~/Downloads/CubismSdkForNative-*`` install.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from puppet.cubism_import import (
    apply_bundle,
    load_cdi3,
    load_exp3,
    load_motion3,
    load_physics3,
)
from puppet.cubism_native_bridge import (
    CubismBridgeError,
    CubismModel,
    DrawableInfo,
    ParameterInfo,
    load_library,
    load_model_file,
)
from puppet.document import (
    Drawable,
    Parameter,
    PuppetDocument,
)

logger = logging.getLogger("Imervue.plugin.puppet.cubism_native_convert")

# Vertices within this many pixels of their rest position are treated
# as "not affected by this parameter" and the morph is dropped — keeps
# the .puppet file size sane for rigs with hundreds of parameters
# that each only touch a handful of drawables.
DEFAULT_MORPH_EPSILON: float = 0.001


def cubism_to_puppet(
    model3_path: str | Path,
    *,
    output_path: str | Path | None = None,
    morph_epsilon: float = DEFAULT_MORPH_EPSILON,
    dll_path: str | Path | None = None,
) -> PuppetDocument:
    """Build a :class:`PuppetDocument` from a Cubism ``.model3.json``.

    ``output_path`` (when supplied) saves the result as a ``.puppet``
    archive in one go. ``morph_epsilon`` filters vertex deltas — bump
    it up when the resulting file is too large.

    Raises :class:`CubismBridgeError` when the DLL isn't reachable or
    the moc fails to load."""
    model3_path = Path(model3_path)
    base_dir = model3_path.parent
    with model3_path.open(encoding="utf-8") as fp:
        manifest = json.load(fp)
    file_refs = manifest.get("FileReferences") or {}
    moc_ref = file_refs.get("Moc")
    if not moc_ref:
        raise CubismBridgeError(
            f"{model3_path}: FileReferences.Moc is missing",
        )
    moc_path = base_dir / moc_ref
    lib = load_library(dll_path)
    model = load_model_file(lib, moc_path)
    document = _build_document_from_model(
        model, manifest, base_dir, morph_epsilon=morph_epsilon,
    )
    if output_path is not None:
        from puppet.document_io import save_puppet
        save_puppet(document, output_path)
    return document


def _build_document_from_model(
    model: CubismModel,
    manifest: dict,
    base_dir: Path,
    *,
    morph_epsilon: float,
) -> PuppetDocument:
    canvas = model.canvas_info()
    document = PuppetDocument(
        size=(int(round(canvas["width"])), int(round(canvas["height"]))),
    )
    transform = _CanvasTransform.from_canvas_info(canvas)
    file_refs = manifest.get("FileReferences") or {}
    _attach_textures(document, file_refs, base_dir)
    parameters = model.parameters()
    drawables_rest = model.drawables()
    _attach_drawables(document, drawables_rest, file_refs, transform)
    _attach_parameters(document, parameters)
    _attach_morphs(
        document, model, parameters, drawables_rest,
        morph_epsilon=morph_epsilon, transform=transform,
    )
    _attach_cubism_bundle(document, manifest, base_dir)
    _attach_synthetic_motions(document)
    return document


# Minimum number of authored motions before we stop adding synth ones.
# A Cubism drop with fewer than this gets a small idle pack appended so
# the workspace's motion picker isn't empty — the March 7th bundle, for
# example, ships zero motions and would otherwise look broken to the user.
_SYNTH_MOTION_THRESHOLD: int = 3


def _attach_synthetic_motions(document: PuppetDocument) -> None:
    """When the document is motion-sparse, append a small ``synth_*``
    idle pack so the converted rig has something to play out of the
    box. Names use a ``synth_`` prefix so authors can recognise + delete
    them once they record their own loops."""
    from puppet.synth_motions import synthesise_idle_motions

    if len(document.motions) >= _SYNTH_MOTION_THRESHOLD:
        return
    for motion in synthesise_idle_motions(document):
        document.motions.append(motion)


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
    def from_canvas_info(cls, info: dict) -> "_CanvasTransform":
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
        if 0 <= tex_index < n_textures:
            texture = f"textures/texture_{tex_index:02d}.png"
        else:
            texture = ""
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


# ---------------------------------------------------------------------------
# Sample-and-reconstruct morphs
# ---------------------------------------------------------------------------


def _attach_morphs(
    document: PuppetDocument,
    model: CubismModel,
    parameters: list[ParameterInfo],
    drawables_rest: list[DrawableInfo],
    *,
    morph_epsilon: float,
    transform: _CanvasTransform,
) -> None:
    """Sweep each parameter to its min + max and record the deformed
    vertex positions; subtract rest to get per-vertex deltas (in
    pixel space, via the canvas transform) and attach the
    non-negligible ones as morphs on each drawable."""
    default_values = [p.default for p in parameters]
    n_drawables = len(drawables_rest)
    rest_positions: list[list[float]] = [list(d.positions) for d in drawables_rest]
    for param_index, parameter in enumerate(parameters):
        if parameter.minimum == parameter.maximum:
            continue
        delta_min = _sample_at(model, default_values, param_index, parameter.minimum)
        delta_max = _sample_at(model, default_values, param_index, parameter.maximum)
        for d_index in range(n_drawables):
            rest = rest_positions[d_index]
            d_min = delta_min[d_index]
            d_max = delta_max[d_index]
            if len(rest) != len(d_min) or len(rest) != len(d_max):
                continue
            morph_min = _vertex_deltas(rest, d_min, transform)
            morph_max = _vertex_deltas(rest, d_max, transform)
            if (
                _max_abs(morph_min) < morph_epsilon
                and _max_abs(morph_max) < morph_epsilon
            ):
                continue
            drawable = document.drawables[d_index]
            if drawable.vertex_morphs is None:
                drawable.vertex_morphs = []
            drawable.vertex_morphs.append({
                "parameter": parameter.id,
                "delta_at_min": morph_min,
                "delta_at_max": morph_max,
            })
    # Restore defaults so subsequent canvas info / drawable reads from
    # this same model still reflect the rest pose.
    model.set_parameter_values(default_values)
    model.update()


def _sample_at(
    model: CubismModel,
    base_values: list[float],
    param_index: int,
    value: float,
) -> list[list[float]]:
    """Set parameter ``param_index`` to ``value`` (keeping everything
    else at default), update the model, and return each drawable's
    flat XY vertex array."""
    values = list(base_values)
    values[param_index] = float(value)
    model.set_parameter_values(values)
    model.update()
    return model.vertex_positions()


def _vertex_deltas(
    rest_flat: list[float],
    deformed_flat: list[float],
    transform: _CanvasTransform,
) -> list[tuple[float, float]]:
    """Convert two flat XY arrays (in Cubism normalized units) into a
    list of pixel-space ``(dx, dy)`` deltas."""
    out: list[tuple[float, float]] = []
    for i in range(0, len(rest_flat), 2):
        out.append(transform.delta(
            deformed_flat[i] - rest_flat[i],
            deformed_flat[i + 1] - rest_flat[i + 1],
        ))
    return out


def _max_abs(deltas: list[tuple[float, float]]) -> float:
    best = 0.0
    for dx, dy in deltas:
        absdx = abs(dx)
        absdy = abs(dy)
        if absdx > best:
            best = absdx
        if absdy > best:
            best = absdy
    return best


# ---------------------------------------------------------------------------
# Cubism bundle — motions / expressions / physics / display names
# ---------------------------------------------------------------------------


def _attach_cubism_bundle(
    document: PuppetDocument, manifest: dict, base_dir: Path,
) -> None:
    """Pull motions / expressions / physics / cdi out of the Cubism
    file references and fold them into the document via the existing
    :mod:`puppet.cubism_import` machinery. Missing files are logged +
    skipped rather than fatal — March 7th's bundle ships broken paths
    for some expression files."""
    from puppet.cubism_import import CubismBundle

    file_refs = manifest.get("FileReferences") or {}
    bundle = CubismBundle()
    referenced_motion_paths: set[Path] = set()
    # Motions explicitly referenced by the model3 manifest first.
    motions_raw = file_refs.get("Motions") or {}
    for group_name, entries in motions_raw.items():
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            file_ref = entry.get("File")
            if not isinstance(file_ref, str) or not file_ref:
                continue
            path = base_dir / file_ref
            if not path.is_file():
                logger.info("motion %s missing — skipping", path)
                continue
            stem = Path(file_ref).stem.removesuffix(".motion3")
            motion = load_motion3(path, name=f"{group_name}/{stem}")
            motion.group = str(group_name)
            if isinstance(entry.get("FadeInTime"), (int, float)):
                motion.fade_in_duration = float(entry["FadeInTime"])
            if isinstance(entry.get("FadeOutTime"), (int, float)):
                motion.fade_out_duration = float(entry["FadeOutTime"])
            bundle.motions.append(motion)
            referenced_motion_paths.add(path.resolve())
    # Sweep the conventional ``motions/`` sibling folder for any
    # un-referenced .motion3.json files — real-world bundles often
    # ship motions the model3 forgot to wire up. Skip duplicates we
    # already picked up via FileReferences.
    extra_root = base_dir / "motions"
    if extra_root.is_dir():
        for path in sorted(extra_root.glob("*.motion3.json")):
            if path.resolve() in referenced_motion_paths:
                continue
            stem = path.stem.removesuffix(".motion3")
            motion = load_motion3(path, name=stem)
            motion.group = "Idle"
            motion.fade_in_duration = 0.5
            motion.fade_out_duration = 0.5
            bundle.motions.append(motion)
    # Expressions — broken paths in real-world bundles are common,
    # so we recover by looking under base_dir / "exp" too.
    for entry in file_refs.get("Expressions") or []:
        if not isinstance(entry, dict):
            continue
        file_ref = entry.get("File")
        name = entry.get("Name") or (Path(file_ref).stem if file_ref else "")
        if not file_ref:
            continue
        candidates = [base_dir / file_ref, base_dir / "exp" / file_ref]
        for path in candidates:
            if path.is_file():
                try:
                    bundle.expressions.append(load_exp3(path, name=str(name)))
                except Exception as exc:   # noqa: BLE001
                    logger.info("expression %s failed: %s", path, exc)
                break
        else:
            logger.info("expression %s missing — skipping", file_ref)
    # Physics
    physics_ref = file_refs.get("Physics")
    if isinstance(physics_ref, str) and physics_ref:
        physics_path = base_dir / physics_ref
        if physics_path.is_file():
            try:
                bundle.physics_rigs = load_physics3(physics_path)
            except Exception as exc:   # noqa: BLE001
                logger.info("physics %s failed: %s", physics_path, exc)
    # Display info
    display_ref = file_refs.get("DisplayInfo")
    if isinstance(display_ref, str) and display_ref:
        display_path = base_dir / display_ref
        if display_path.is_file():
            try:
                bundle.display_names = load_cdi3(display_path)
            except Exception as exc:   # noqa: BLE001
                logger.info("cdi %s failed: %s", display_path, exc)
    # HitAreas — keep them even though the drawable ids referenced
    # may differ from what's in this rig; the workspace handler
    # silently no-ops on missing drawables.
    for entry in manifest.get("HitAreas") or []:
        if not isinstance(entry, dict):
            continue
        drawable_id = entry.get("Id")
        name = entry.get("Name") or drawable_id
        if isinstance(drawable_id, str) and drawable_id:
            from puppet.document import HitArea
            bundle.hit_areas.append(HitArea(id=str(name), drawables=[str(drawable_id)]))
    apply_bundle(document, bundle)
