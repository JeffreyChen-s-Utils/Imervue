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

from Imervue.puppet.cubism_import import (
    CubismBundle,
    apply_bundle,
    load_cdi3,
    load_exp3,
    load_motion3,
    load_physics3,
)
from Imervue.puppet.cubism_native_bridge import (
    CubismBridgeError,
    CubismModel,
    DrawableInfo,
    ParameterInfo,
    load_library,
    load_model_file,
)
from Imervue.puppet.document import (
    Drawable,
    Motion,
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
        from Imervue.puppet.document_io import save_puppet
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
    _attach_visibility_keys(document, model, parameters, drawables_rest)
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
    from Imervue.puppet.synth_motions import synthesise_idle_motions

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


# ---------------------------------------------------------------------------
# Sample-and-reconstruct morphs
# ---------------------------------------------------------------------------


def _build_morph_entry(
    rest: list[float],
    deformed_min: list[float],
    deformed_max: list[float],
    morph_epsilon: float,
    transform: _CanvasTransform,
    parameter_id: str,
) -> dict | None:
    """Subtract rest from the two deformed vertex arrays and return a
    serialisable morph entry — unless both deltas are below the
    threshold (then the morph is noise, drop it)."""
    if len(rest) != len(deformed_min) or len(rest) != len(deformed_max):
        return None
    morph_min = _vertex_deltas(rest, deformed_min, transform)
    morph_max = _vertex_deltas(rest, deformed_max, transform)
    if _max_abs(morph_min) < morph_epsilon and _max_abs(morph_max) < morph_epsilon:
        return None
    return {
        "parameter": parameter_id,
        "delta_at_min": morph_min,
        "delta_at_max": morph_max,
    }


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
    rest_positions: list[list[float]] = [list(d.positions) for d in drawables_rest]
    for param_index, parameter in enumerate(parameters):
        if parameter.minimum == parameter.maximum:
            continue
        delta_min = _sample_at(model, default_values, param_index, parameter.minimum)
        delta_max = _sample_at(model, default_values, param_index, parameter.maximum)
        for d_index, rest in enumerate(rest_positions):
            entry = _build_morph_entry(
                rest, delta_min[d_index], delta_max[d_index],
                morph_epsilon, transform, parameter.id,
            )
            if entry is None:
                continue
            drawable = document.drawables[d_index]
            if drawable.vertex_morphs is None:
                drawable.vertex_morphs = []
            drawable.vertex_morphs.append(entry)
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


def _sample_visibility_at(
    model: CubismModel,
    base_values: list[float],
    param_index: int,
    value: float,
) -> list[bool]:
    """Set one parameter to ``value`` and read the per-drawable
    ``IsVisible`` bit. Used by :func:`_attach_visibility_keys` to
    capture parameter-driven part-tree exclusion that vertex
    sampling alone can't see."""
    values = list(base_values)
    values[param_index] = float(value)
    model.set_parameter_values(values)
    model.update()
    return model.visibility_flags()


def _emit_opacity_curve(
    drawable: Drawable,
    parameter: ParameterInfo,
    vd: bool, vmin: bool, vmax: bool,
) -> None:
    """Append a three-stop ``opacity_keys`` entry to ``drawable`` and
    force it visible + opaque so the curve has authority over the
    renderer. Caller is responsible for deciding when this transition
    is worth recording — this helper trusts that decision."""
    stops = [
        {"value": parameter.minimum, "alpha": 1.0 if vmin else 0.0},
        {"value": parameter.default, "alpha": 1.0 if vd else 0.0},
        {"value": parameter.maximum, "alpha": 1.0 if vmax else 0.0},
    ]
    if drawable.opacity_keys is None:
        drawable.opacity_keys = []
    drawable.opacity_keys.append({
        "parameter": parameter.id,
        "stops": stops,
    })
    # The curve must be the gate, not the authored base. A drawable
    # hidden at rest gets opacity=0.0 from the converter;
    # resolve_drawable_opacity multiplies that by the curve, so
    # 0 * 1 = 0 and the curve does nothing. Force visible + opaque so
    # the curve has the only say.
    drawable.visible = True
    drawable.opacity = 1.0


def _attach_visibility_keys(
    document: PuppetDocument,
    model: CubismModel,
    parameters: list[ParameterInfo],
    drawables_rest: list[DrawableInfo],
) -> None:
    """Sweep each parameter and detect per-drawable visibility flips.

    Cubism rigs toggle alternate-pose meshes (hand gestures, camera
    objects, expression overlays) via dynamic ``IsVisible`` flags
    that the deformation pipeline never touches — so the
    sample-and-reconstruct vertex sweep alone reduces those meshes
    to invisible-and-stationary. Catch the transition by reading
    :meth:`CubismModel.visibility_flags` at each parameter's min,
    default, and max; when a drawable's visibility differs across
    those points, emit a three-stop ``opacity_keys`` curve so the
    runtime fades the mesh in/out as the parameter moves.
    """
    default_values = [p.default for p in parameters]
    default_vis = [d.is_visible for d in drawables_rest]
    for param_index, parameter in enumerate(parameters):
        if parameter.minimum == parameter.maximum:
            continue
        vis_min = _sample_visibility_at(
            model, default_values, param_index, parameter.minimum,
        )
        vis_max = _sample_visibility_at(
            model, default_values, param_index, parameter.maximum,
        )
        for d_index, drawable in enumerate(document.drawables):
            vd, vmin, vmax = default_vis[d_index], vis_min[d_index], vis_max[d_index]
            if vd == vmin == vmax:
                continue
            _emit_opacity_curve(drawable, parameter, vd, vmin, vmax)
    # Restore the rest pose before any downstream caller reads the
    # model — _attach_morphs already does this for its own sweep, but
    # we may be the last sweep so be defensive.
    model.set_parameter_values(default_values)
    model.update()


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
        best = max(best, absdx)
        best = max(best, absdy)
    return best


# ---------------------------------------------------------------------------
# Cubism bundle — motions / expressions / physics / display names
# ---------------------------------------------------------------------------


def _load_referenced_motion(
    base_dir: Path, group_name: str, entry: dict,
) -> tuple[Motion, Path] | None:
    """Resolve and load one entry from the manifest's ``Motions``
    map. Returns ``(motion, resolved_path)`` so the caller can both
    collect the motion and track which files were already consumed.
    Returns ``None`` for missing files or malformed entries."""
    file_ref = entry.get("File")
    if not isinstance(file_ref, str) or not file_ref:
        return None
    path = base_dir / file_ref
    if not path.is_file():
        logger.info("motion %s missing — skipping", path)
        return None
    stem = Path(file_ref).stem.removesuffix(".motion3")
    motion = load_motion3(path, name=f"{group_name}/{stem}")
    motion.group = str(group_name)
    fade_in = entry.get("FadeInTime")
    fade_out = entry.get("FadeOutTime")
    if isinstance(fade_in, (int, float)):
        motion.fade_in_duration = float(fade_in)
    if isinstance(fade_out, (int, float)):
        motion.fade_out_duration = float(fade_out)
    return motion, path.resolve()


def _collect_manifest_motions(
    bundle: CubismBundle, file_refs: dict, base_dir: Path,
) -> set[Path]:
    """Walk ``FileReferences.Motions`` and append every entry that
    resolves. Returns the set of resolved paths so the orphan-sweep
    can skip duplicates."""
    seen: set[Path] = set()
    for group_name, entries in (file_refs.get("Motions") or {}).items():
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            loaded = _load_referenced_motion(base_dir, group_name, entry)
            if loaded is None:
                continue
            motion, resolved = loaded
            bundle.motions.append(motion)
            seen.add(resolved)
    return seen


def _collect_orphan_motions(
    bundle: CubismBundle, base_dir: Path, already_seen: set[Path],
) -> None:
    """Real-world Cubism bundles often ship motions the manifest
    forgot — sweep ``motions/`` and pick up anything not already
    consumed. Default the group to ``Idle`` with a half-second
    cross-fade."""
    extra_root = base_dir / "motions"
    if not extra_root.is_dir():
        return
    for path in sorted(extra_root.glob("*.motion3.json")):
        if path.resolve() in already_seen:
            continue
        stem = path.stem.removesuffix(".motion3")
        motion = load_motion3(path, name=stem)
        motion.group = "Idle"
        motion.fade_in_duration = 0.5
        motion.fade_out_duration = 0.5
        bundle.motions.append(motion)


def _load_expression_entry(
    bundle: CubismBundle, entry: object, base_dir: Path,
) -> None:
    """Resolve and load one entry from the manifest's ``Expressions``
    list. Tries both ``base_dir / file_ref`` and the conventional
    ``base_dir / "exp" / file_ref`` location; logs and skips when
    neither exists. Caught exceptions cover the heterogeneous failure
    surface of :func:`load_exp3` against real-world Cubism rigs."""
    if not isinstance(entry, dict):
        return
    file_ref = entry.get("File")
    if not file_ref:
        return
    name = entry.get("Name") or Path(file_ref).stem
    for path in (base_dir / file_ref, base_dir / "exp" / file_ref):
        if not path.is_file():
            continue
        try:
            bundle.expressions.append(load_exp3(path, name=str(name)))
        except Exception as exc:   # noqa: BLE001 - load_exp3 backends vary
            logger.info("expression %s failed: %s", path, exc)
        return
    logger.info("expression %s missing — skipping", file_ref)


def _collect_expressions(
    bundle: CubismBundle, file_refs: dict, base_dir: Path,
) -> None:
    """Broken paths in real-world bundles are common; also check
    under ``base_dir / "exp"``."""
    for entry in file_refs.get("Expressions") or []:
        _load_expression_entry(bundle, entry, base_dir)


def _collect_single_sidecar(
    file_refs: dict, base_dir: Path, key: str, loader, sink, label: str,
) -> None:
    """Apply the same pattern as physics / display info: look up a
    single string filename, verify it exists, hand the path to the
    loader, swallow any backend error as info-log."""
    ref = file_refs.get(key)
    if not isinstance(ref, str) or not ref:
        return
    path = base_dir / ref
    if not path.is_file():
        return
    try:
        sink(loader(path))
    except Exception as exc:   # noqa: BLE001 - third-party loaders vary
        logger.info("%s %s failed: %s", label, path, exc)


def _collect_hit_areas(bundle: CubismBundle, manifest: dict) -> None:
    from Imervue.puppet.document import HitArea
    for entry in manifest.get("HitAreas") or []:
        if not isinstance(entry, dict):
            continue
        drawable_id = entry.get("Id")
        if not isinstance(drawable_id, str) or not drawable_id:
            continue
        name = entry.get("Name") or drawable_id
        bundle.hit_areas.append(
            HitArea(id=str(name), drawables=[str(drawable_id)]),
        )


def _attach_cubism_bundle(
    document: PuppetDocument, manifest: dict, base_dir: Path,
) -> None:
    """Pull motions / expressions / physics / cdi out of the Cubism
    file references and fold them into the document via the existing
    :mod:`puppet.cubism_import` machinery. Missing files are logged +
    skipped rather than fatal — March 7th's bundle ships broken paths
    for some expression files."""
    from Imervue.puppet.cubism_import import CubismBundle

    file_refs = manifest.get("FileReferences") or {}
    bundle = CubismBundle()

    referenced_paths = _collect_manifest_motions(bundle, file_refs, base_dir)
    _collect_orphan_motions(bundle, base_dir, referenced_paths)
    _collect_expressions(bundle, file_refs, base_dir)
    _collect_single_sidecar(
        file_refs, base_dir, "Physics",
        load_physics3, bundle.physics_rigs.extend, "physics",
    )
    _collect_single_sidecar(
        file_refs, base_dir, "DisplayInfo",
        load_cdi3, bundle.display_names.update, "cdi",
    )
    _collect_hit_areas(bundle, manifest)
    apply_bundle(document, bundle)
