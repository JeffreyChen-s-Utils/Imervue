"""Guard: every module under ``Imervue/`` is imported by production code.

An AST scan of ``Imervue/``, ``plugins/`` and the root ``*.spec`` build files (tests
excluded) collects every
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
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_ENTRY_POINTS = {"Imervue.__main__", "Imervue.cli", "Imervue.mcp_server.__main__"}

_KNOWN_UNWIRED = {
    "Imervue.desktop_pet.command_parser", "Imervue.desktop_pet.hotkey_conflicts",
    "Imervue.export.contact_sheet_layouts", "Imervue.image.caption",
    "Imervue.library.capture_time", "Imervue.library.gpx_geotag",
    "Imervue.multi_language.translation_validation",
    "Imervue.paint.auto_base_color",
    "Imervue.paint.filter_preview_dialog",
    "Imervue.paint.text_on_selection",
    "Imervue.puppet.audio_lipsync", "Imervue.puppet.bone_weights", "Imervue.puppet.easing",
    "Imervue.puppet.mesh_repair", "Imervue.puppet.motion_compress",
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
    # The build specs are Python too: Imervue_mac.spec imports system.macos_bundle.
    sources = [*(ROOT / "Imervue").rglob("*.py"), *(ROOT / "plugins").rglob("*.py"),
               *ROOT.glob("*.spec")]
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
    assert "Imervue.system.macos_bundle" not in _unwired()     # imported by a build spec


def test_relative_imports_resolve_against_the_package(tmp_path, monkeypatch):
    package = tmp_path / "Imervue" / "pkg"
    package.mkdir(parents=True)
    source = package / "user.py"
    source.write_text("from . import sibling\nfrom ..other import thing\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    names = _imported_names(source)
    assert {"Imervue.pkg.sibling", "Imervue.other", "Imervue.other.thing"} <= names
