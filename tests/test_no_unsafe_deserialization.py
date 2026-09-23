"""Guard: product code never deserialises a file in a way that can run code.

Bandit flags ``pickle`` and ``yaml.load`` but not the NumPy and PyTorch forms:
``np.load(..., allow_pickle=True)`` unpickles object arrays, and
``torch.load`` without ``weights_only=True`` unpickles the whole checkpoint.
The semantic-search cache did the former until its paths moved to JSON.
Covers ``Imervue/`` and ``plugins/``.
"""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_ROOTS = (_REPO / "Imervue", _REPO / "plugins")


def _keyword(call: ast.Call, name: str):
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def _is_constant(node, value) -> bool:
    return isinstance(node, ast.Constant) and node.value is value


def _can_unpickle(call: ast.Call) -> bool:
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "load":
        return False
    owner = getattr(call.func.value, "id", None)
    if owner in ("np", "numpy"):
        flag = _keyword(call, "allow_pickle")   # NumPy's default is False
        return flag is not None and not _is_constant(flag, False)
    if owner == "torch":
        return not _is_constant(_keyword(call, "weights_only"), True)
    return False


def _unsafe_loads(source: str) -> list[int]:
    """Return the line of every call that can unpickle file contents."""
    return [node.lineno for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call) and _can_unpickle(node)]


def test_detector_flags_the_unsafe_forms_only():
    source = textwrap.dedent("""\
        import numpy as np, torch
        np.load(p, allow_pickle=True)
        np.load(p, allow_pickle=flag)
        torch.load(p)
        torch.load(p, weights_only=False)
        np.load(p)
        np.load(p, allow_pickle=False)
        torch.load(p, weights_only=True)
    """)
    assert _unsafe_loads(source) == [2, 3, 4, 5]


def test_no_product_code_unpickles_a_file():
    found = [
        f"{path.relative_to(_REPO).as_posix()}:{line}"
        for root in _ROOTS if root.is_dir()
        for path in sorted(root.rglob("*.py")) if "__pycache__" not in path.parts
        for line in _unsafe_loads(path.read_text(encoding="utf-8"))
    ]
    assert found == []
