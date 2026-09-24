"""Guard: every module under ``Imervue/`` is imported by production code.

An AST scan of ``Imervue/`` and ``plugins/`` (tests excluded) collects every
import, resolving relative ones, plus dotted module names written as string
literals for lazy ``importlib`` loads. A module nothing imports is either an
entry point run with ``py -m`` or code no user can reach.

``_KNOWN_UNWIRED`` lists the modules that were already unreachable when the
guard was added (``progress.md`` #22 asks the owner to wire or remove them).
The list may only shrink: a new unreachable module fails
``test_no_new_unwired_modules``, and wiring or deleting a listed one fails
``test_known_list_is_current`` until its entry is removed.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_ENTRY_POINTS = {"Imervue.__main__", "Imervue.cli", "Imervue.mcp_server.__main__"}

_KNOWN_UNWIRED = {
    "Imervue.desktop_pet.command_parser", "Imervue.desktop_pet.hotkey_conflicts",
    "Imervue.desktop_pet.pet_registry",
    "Imervue.export.contact_sheet_layouts", "Imervue.export.gallery_sort",
    "Imervue.gpu_image_view.actions.undo_coalescer",
    "Imervue.image.annotations", "Imervue.image.caption", "Imervue.image.metadata_sync",
    "Imervue.library.capture_time", "Imervue.library.face_clustering",
    "Imervue.library.gpx_geotag",
    "Imervue.multi_language.translation_validation",
    "Imervue.paint.action_recorder_dialog", "Imervue.paint.animation_export",
    "Imervue.paint.auto_base_color", "Imervue.paint.auto_correct", "Imervue.paint.brush_random",
    "Imervue.paint.canvas_presets", "Imervue.paint.catmull_rom_spline",
    "Imervue.paint.color_management", "Imervue.paint.color_palette",
    "Imervue.paint.color_sampler", "Imervue.paint.color_wheel_widget",
    "Imervue.paint.comic_formats", "Imervue.paint.export_utils",
    "Imervue.paint.filter_preview_dialog", "Imervue.paint.frame_splitter",
    "Imervue.paint.gradient_editor", "Imervue.paint.line_cleanup",
    "Imervue.paint.magnetic_lasso", "Imervue.paint.match_color", "Imervue.paint.match_palette",
    "Imervue.paint.paint_project_io", "Imervue.paint.pattern_fill",
    "Imervue.paint.perspective_warp", "Imervue.paint.polyline_offset",
    "Imervue.paint.reference_panel", "Imervue.paint.rich_text",
    "Imervue.paint.save_region_as_material", "Imervue.paint.smart_guides",
    "Imervue.paint.speech_bubbles", "Imervue.paint.tablet_mapping",
    "Imervue.paint.text_on_selection", "Imervue.paint.timelapse",
    "Imervue.paint.view_transform", "Imervue.paint.watercolor",
    "Imervue.puppet.audio_lipsync", "Imervue.puppet.bone_weights", "Imervue.puppet.easing",
    "Imervue.puppet.ik", "Imervue.puppet.mesh_repair", "Imervue.puppet.motion_compress",
    "Imervue.sessions.session_migration",
    "Imervue.system.macos_bundle", "Imervue.system.theme_color_math",
    "Imervue.user_settings.metadata_template", "Imervue.user_settings.tag_validator",
}


def _dotted(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    own = _dotted(path)
    package = own if path.name == "__init__.py" else own.rsplit(".", 1)[0]
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                parts = parts[: len(parts) - (node.level - 1)]
                base = ".".join(parts + ([base] if base else []))
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value.startswith("Imervue."):
            names.add(node.value)
    names.discard(own)
    return names


@lru_cache(maxsize=1)
def _unwired() -> frozenset[str]:
    modules = {_dotted(p) for p in (ROOT / "Imervue").rglob("*.py") if p.name != "__init__.py"}
    sources = [*(ROOT / "Imervue").rglob("*.py"), *(ROOT / "plugins").rglob("*.py")]
    imported: set[str] = set()
    for source in sources:
        imported |= _imported_names(source)
    return frozenset(modules - imported - _ENTRY_POINTS)


def test_no_new_unwired_modules():
    new = sorted(_unwired() - _KNOWN_UNWIRED)
    assert new == [], f"modules nothing in Imervue/ or plugins/ imports: {new}"


def test_known_list_is_current():
    stale = sorted(_KNOWN_UNWIRED - _unwired())
    assert stale == [], f"now wired or removed; drop from _KNOWN_UNWIRED: {stale}"


def test_scan_sees_relative_and_lazy_imports():
    assert "Imervue.gui.dialog_rows" not in _unwired()        # plain absolute imports
    assert "Imervue.image.read_errors" not in _unwired()      # imported inside functions too
    assert "Imervue.export.gallery_sort" in _unwired()
