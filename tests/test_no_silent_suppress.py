"""Guard: no ``contextlib.suppress(Exception)`` (or ``BaseException``) in product code.

ruff's ``BLE`` rule sees ``except Exception`` but not the ``suppress`` form,
which swallows every failure without a trace. Catch the exceptions the block
can actually meet, or use ``Imervue.system.best_effort.best_effort``, which
still carries on but logs the traceback. Covers ``Imervue/`` and the bundled
``plugins/``.
"""
from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_ROOTS = (_REPO / "Imervue", _REPO / "plugins")
_BROAD = {"Exception", "BaseException"}


def _is_suppress(func: ast.expr) -> bool:
    if isinstance(func, ast.Attribute):
        return func.attr == "suppress"
    return isinstance(func, ast.Name) and func.id == "suppress"


def _broad_arg(node: ast.Call) -> str | None:
    for arg in node.args:
        name = arg.attr if isinstance(arg, ast.Attribute) else getattr(arg, "id", None)
        if name in _BROAD:
            return name
    return None


def _silent_suppressions(source: str) -> list[tuple[int, str]]:
    """Return ``(line, exception name)`` for every broad ``suppress(...)`` call in ``source``."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and _is_suppress(node.func):
            broad = _broad_arg(node)
            if broad is not None:
                found.append((node.lineno, broad))
    return found


def _product_files():
    for root in _ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path


def test_detector_flags_broad_forms_only():
    source = (
        "import contextlib\n"
        "from contextlib import suppress\n"
        "import builtins\n"
        "with contextlib.suppress(Exception): pass\n"
        "with suppress(OSError, BaseException): pass\n"
        "with contextlib.suppress(builtins.Exception): pass\n"
        "with contextlib.suppress(OSError, ValueError): pass\n"
        "with contextlib.suppress(): pass\n"
    )
    assert _silent_suppressions(source) == [(4, "Exception"), (5, "BaseException"),
                                             (6, "Exception")]


def test_no_product_code_suppresses_every_exception():
    found = [
        f"{path.relative_to(_REPO).as_posix()}:{line} suppress({name})"
        for path in _product_files()
        for line, name in _silent_suppressions(path.read_text(encoding="utf-8"))
    ]
    assert found == []
