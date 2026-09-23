"""Guards for the size limits no linter here enforces.

* No function in ``Imervue/`` is longer than 80 lines — the workspace rule
  (``D:\\Codes\\CLAUDE.md``, "可讀性"). A function's length runs from its ``def``
  (decorators excluded) to its last line, docstring included.
* No module is longer than 1,000 lines (SonarQube ``python:S104``), except the
  ``multi_language`` dictionaries, which are data.
* No function takes more than 7 positional parameters (``self`` / ``cls`` not
  counted). Options beyond that must be keyword-only with defaults — the
  project's reasoned exception to the workspace's 7-parameter rule, since a
  named option cannot be passed in the wrong slot (see ``CLAUDE.md``).
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "Imervue"
_LIMIT = 80
_FILE_LIMIT = 1000
_POSITIONAL_LIMIT = 7


def _long_functions() -> list[str]:
    found = []
    for path in sorted(_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = node.end_lineno - node.lineno + 1
                if length > _LIMIT:
                    rel = path.relative_to(_ROOT.parent).as_posix()
                    found.append(f"{rel}:{node.lineno} {node.name} ({length} lines)")
    return found


def test_no_function_is_longer_than_the_limit():
    assert _long_functions() == []


def test_no_module_is_longer_than_the_limit():
    too_long = []
    for path in sorted(_ROOT.rglob("*.py")):
        if "multi_language" in path.parts:
            continue
        with path.open(encoding="utf-8") as fh:
            lines = sum(1 for _ in fh)
        if lines > _FILE_LIMIT:
            too_long.append(f"{path.relative_to(_ROOT.parent).as_posix()} ({lines} lines)")
    assert too_long == []


def test_no_function_takes_more_than_seven_positional_parameters():
    wide = []
    for path in sorted(_ROOT.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            positional = [a.arg for a in node.args.posonlyargs + node.args.args]
            if positional[:1] in (["self"], ["cls"]):
                positional = positional[1:]
            if len(positional) > _POSITIONAL_LIMIT:
                rel = path.relative_to(_ROOT.parent).as_posix()
                wide.append(f"{rel}:{node.lineno} {node.name} ({len(positional)} positional)")
    assert wide == []
