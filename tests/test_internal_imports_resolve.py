"""Every ``from Imervue... import name`` in the code names something that exists.

Many imports sit inside functions, so a rename that misses one only fails when
that function first runs. Removing ``image_loader._RAW_EXTS`` broke
``DeepZoomLoadingMixin._should_progressive_decode`` exactly that way: every
recipe reload in the viewer raised ``ImportError`` while the suite stayed green.
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SOURCES = [
    path for root in ("Imervue", "plugins") for path in (_REPO / root).rglob("*.py")
    if "__pycache__" not in path.parts
]


def _internal_imports(source: str) -> list[tuple[int, str, str]]:
    """Return ``(line, module, name)`` for each absolute ``from Imervue... import name``."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
                and node.module.split(".")[0] == "Imervue"):
            found.extend((node.lineno, node.module, alias.name)
                         for alias in node.names if alias.name != "*")
    return found


def _resolves(module: str, name: str) -> bool:
    mod = importlib.import_module(module)
    if hasattr(mod, name):
        return True
    # A submodule not yet imported is not an attribute; only a package has any.
    return hasattr(mod, "__path__") and importlib.util.find_spec(f"{module}.{name}") is not None


def test_detector_finds_function_level_imports():
    source = "def f():\n    from Imervue.a.b import c, d as e\nfrom os import path\nfrom . import x\n"
    assert _internal_imports(source) == [(2, "Imervue.a.b", "c"), (2, "Imervue.a.b", "d")]


def test_resolver_accepts_names_and_submodules_and_rejects_a_missing_name():
    assert _resolves("Imervue.image.formats", "RAW_EXTENSIONS")
    assert _resolves("Imervue.image", "formats")
    assert not _resolves("Imervue.gpu_image_view.images.image_loader", "_RAW_EXTS")


@pytest.mark.parametrize("path", _SOURCES, ids=lambda p: p.relative_to(_REPO).as_posix())
def test_internal_imports_resolve(path):
    missing = [
        f"{line}: from {module} import {name}"
        for line, module, name in _internal_imports(path.read_text(encoding="utf-8"))
        if not _resolves(module, name)
    ]
    assert missing == []
