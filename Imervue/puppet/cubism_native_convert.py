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
enough for "the character shows up and her head turns when
``ParamAngleZ`` moves." Not byte-identical to Cubism's runtime, never can be.

Textures, motions, expressions, physics, hit areas, and display
names load through the existing :mod:`puppet.cubism_import` JSON
pipeline. The Cubism SDK is never redistributed — the user supplies
their own DLL path via ``CUBISM_CORE_DLL`` or a standard
``~/Downloads/CubismSdkForNative-*`` install.
"""
from __future__ import annotations

import logging
from pathlib import Path

from Imervue.puppet.cubism_import import (
    CubismBundle,
    _read_json,
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
from Imervue.puppet.cubism_native_bundle import (
    _attach_cubism_bundle,
    _collect_expressions,
    _collect_hit_areas,
    _collect_single_sidecar,
    _load_expression_entry,
)
from Imervue.puppet.cubism_native_mesh import (
    _attach_drawables,
    _attach_parameters,
    _attach_textures,
    _CanvasTransform,
    _translate_blend_mode,
)
from Imervue.puppet.cubism_native_morphs import (
    _attach_morphs,
    _attach_visibility_keys,
    _build_morph_entry,
    _emit_opacity_curve,
    _max_abs,
    _sample_at,
    _sample_visibility_at,
    _vertex_deltas,
)
from Imervue.puppet.cubism_native_motions import (
    _collect_manifest_motions,
    _collect_orphan_motions,
    _load_referenced_motion,
)
from Imervue.puppet.document import (
    Drawable,
    Motion,
    Parameter,
    PuppetDocument,
)

# The rest-pose wiring, the parameter sweeps, the motion loaders and the
# bundle assembly live in the cubism_native_* siblings; every name stays
# importable from here.
__all__ = [
    "DEFAULT_MORPH_EPSILON",
    "CubismBridgeError",
    "CubismBundle",
    "CubismModel",
    "Drawable",
    "DrawableInfo",
    "Motion",
    "Parameter",
    "ParameterInfo",
    "PuppetDocument",
    "_CanvasTransform",
    "_attach_cubism_bundle",
    "_attach_drawables",
    "_attach_morphs",
    "_attach_parameters",
    "_attach_synthetic_motions",
    "_attach_textures",
    "_attach_visibility_keys",
    "_build_document_from_model",
    "_build_morph_entry",
    "_collect_expressions",
    "_collect_hit_areas",
    "_collect_manifest_motions",
    "_collect_orphan_motions",
    "_collect_single_sidecar",
    "_emit_opacity_curve",
    "_load_expression_entry",
    "_load_referenced_motion",
    "_max_abs",
    "_read_json",
    "_sample_at",
    "_sample_visibility_at",
    "_translate_blend_mode",
    "_vertex_deltas",
    "apply_bundle",
    "cubism_to_puppet",
    "load_cdi3",
    "load_exp3",
    "load_library",
    "load_model_file",
    "load_motion3",
    "load_physics3",
]

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
    the moc fails to load, and :class:`CubismFormatError` when the
    ``.model3.json`` is not JSON."""
    model3_path = Path(model3_path)
    base_dir = model3_path.parent
    # Malformed JSON raises CubismFormatError, which the importer reports; a
    # json.JSONDecodeError escaped it and ended the import with a traceback.
    manifest = _read_json(model3_path)
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
# the workspace's motion picker isn't empty — a bundle that ships zero
# motions would otherwise look broken to the user.
_SYNTH_MOTION_THRESHOLD: int = 3


def _attach_synthetic_motions(document: PuppetDocument) -> None:
    """When the document is motion-sparse, append a small ``synth_*``
    idle pack so the converted rig has something to play out of the
    box. Names use a ``synth_`` prefix so authors can recognise + delete
    them once they record their own loops."""
    from Imervue.puppet.synth_motions import synthesise_idle_motions

    if len(document.motions) >= _SYNTH_MOTION_THRESHOLD:
        return
    document.motions.extend(synthesise_idle_motions(document))
