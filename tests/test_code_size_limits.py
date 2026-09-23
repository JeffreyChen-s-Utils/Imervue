"""Guards for the size limits no linter here enforces, in ``Imervue/`` and ``plugins/``.

* No function is longer than 80 lines — the workspace rule
  (``D:\\Codes\\CLAUDE.md``, "可讀性"). A function's length runs from its ``def``
  (decorators excluded) to its last line, docstring included.
* No module is longer than 1,000 lines (SonarQube ``python:S104``), except
  translation data: the ``multi_language`` dictionaries and the language
  plugins (``plugins/*_translation/``).
* No function takes more than 7 positional parameters (``self`` / ``cls`` not
  counted). Options beyond that must be keyword-only with defaults — the
  project's reasoned exception to the workspace's 7-parameter rule, since a
  named option cannot be passed in the wrong slot (see ``CLAUDE.md``).
"""
from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_ROOTS = (_REPO / "Imervue", _REPO / "plugins")
_LIMIT = 80
_FILE_LIMIT = 1000
_POSITIONAL_LIMIT = 7


def _sources():
    for root in _ROOTS:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path, path.relative_to(_REPO).as_posix()


def _is_translation_data(path: Path) -> bool:
    return "multi_language" in path.parts or any(
        part.endswith("_translation") for part in path.parts)


def _functions(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def test_no_function_is_longer_than_the_limit():
    found = []
    for path, rel in _sources():
        for node in _functions(path):
            length = node.end_lineno - node.lineno + 1
            if length > _LIMIT:
                found.append(f"{rel}:{node.lineno} {node.name} ({length} lines)")
    assert found == []


def test_no_module_is_longer_than_the_limit():
    too_long = []
    for path, rel in _sources():
        if _is_translation_data(path):
            continue
        with path.open(encoding="utf-8") as fh:
            lines = sum(1 for _ in fh)
        if lines > _FILE_LIMIT:
            too_long.append(f"{rel} ({lines} lines)")
    assert too_long == []


def test_no_function_takes_more_than_seven_positional_parameters():
    wide = []
    for path, rel in _sources():
        for node in _functions(path):
            positional = [a.arg for a in node.args.posonlyargs + node.args.args]
            if positional[:1] in (["self"], ["cls"]):
                positional = positional[1:]
            if len(positional) > _POSITIONAL_LIMIT:
                wide.append(f"{rel}:{node.lineno} {node.name} ({len(positional)} positional)")
    assert wide == []


def test_translation_data_exemption_is_narrow():
    assert _is_translation_data(_REPO / "Imervue" / "multi_language" / "english.py")
    assert _is_translation_data(_REPO / "plugins" / "spanish_translation" / "spanish.py")
    assert not _is_translation_data(_REPO / "plugins" / "npr_filters" / "npr_filters_plugin.py")
    assert not _is_translation_data(_REPO / "Imervue" / "gui" / "translation_editor.py")
