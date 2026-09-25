"""Every ``.format(...)`` on a translated string passes the placeholders the string uses.

``lang.get("token_rename_done", ...).format(ok=ok, failed=failed)`` raised
``KeyError: 'f'`` on every Token Batch Rename: each translation spells the
failure count ``{f}``. ``tests/test_translations.py`` keeps every language's
placeholders equal to ``english.py``'s; this closes the gap between
``english.py`` (and the inline English fallback) and the code that formats it.

A lookup is ``<x>.get("key", "fallback")``, ``<x>["key"]`` or a ``_tr("key",
"fallback")`` helper call, formatted directly or through a name assigned once
in the same module. Calls passing ``**kwargs`` can't be checked and are skipped.
"""
from __future__ import annotations

import ast
import string
from pathlib import Path

from Imervue.multi_language.english import english_word_dict

_ROOT = Path(__file__).resolve().parent.parent
_HELPERS = {"_tr", "_t", "tr"}


def _fields(text: str) -> set[str]:
    """The replacement fields of *text* (``""`` or a digit for positional ones)."""
    return {name.split(".")[0].split("[")[0]
            for _literal, name, _spec, _conv in string.Formatter().parse(text)
            if name is not None}


def _literal(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _lookup(node) -> tuple[str, str | None] | None:
    """``(key, inline fallback)`` when *node* looks a translation up, else None."""
    if isinstance(node, ast.Subscript):
        key = _literal(node.slice)
        return (key, None) if key else None
    if not isinstance(node, ast.Call) or not node.args:
        return None
    is_get = isinstance(node.func, ast.Attribute) and node.func.attr == "get"
    is_helper = isinstance(node.func, ast.Name) and node.func.id in _HELPERS
    key = _literal(node.args[0])
    if not (is_get or is_helper) or key is None:
        return None
    return key, _literal(node.args[1]) if len(node.args) > 1 else None


def _single_assignments(tree) -> dict[str, tuple[str, str | None]]:
    """Names assigned a translation lookup exactly once in the module."""
    seen: dict[str, list] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            found = _lookup(node.value)
            if found:
                seen.setdefault(node.targets[0].id, []).append(found)
    return {name: found[0] for name, found in seen.items() if len(found) == 1}


def _problems_in(path: Path, root: Path = _ROOT) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assigned = _single_assignments(tree)
    problems = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "format"):
            continue
        target = node.func.value
        found = _lookup(target)
        if found is None and isinstance(target, ast.Name):
            found = assigned.get(target.id)
        if found is None or any(k.arg is None for k in node.keywords):
            continue
        key, fallback = found
        given = {k.arg for k in node.keywords}
        for source, text in (("english.py", english_word_dict.get(key)), ("fallback", fallback)):
            if not isinstance(text, str):
                continue
            needed = _fields(text)
            missing = {n for n in needed if n and not n.isdigit()} - given
            if any(n == "" or n.isdigit() for n in needed) and not node.args:
                missing.add("<positional>")
            if missing:
                problems.append(f"{path.relative_to(root)}:{node.lineno} {key!r} ({source}) "
                                f"needs {sorted(missing)}")
    return problems


def _sources() -> list[Path]:
    files = []
    for base in ("Imervue", "plugins"):
        for path in (_ROOT / base).rglob("*.py"):
            parts = path.parts
            if "__pycache__" in parts or "multi_language" in parts \
                    or any(part.endswith("_translation") for part in parts):
                continue
            files.append(path)
    return files


def test_every_formatted_translation_gets_its_placeholders():
    problems = [problem for path in _sources() for problem in _problems_in(path)]
    assert problems == []


def test_the_scan_catches_the_token_rename_crash(tmp_path):
    """The shape of the bug this guards against, so the scan can't silently match nothing."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        'msg = lang.get("token_rename_done", "Renamed {ok}, failed {f}")'
        '.format(ok=1, failed=0)\n', encoding="utf-8")
    good = tmp_path / "good.py"
    good.write_text(
        'text = lang.get("token_rename_done", "Renamed {ok}, failed {f}")\n'
        'msg = text.format(ok=1, f=0)\n', encoding="utf-8")
    assert len(_problems_in(bad, tmp_path)) == 2          # english.py and the fallback
    assert _problems_in(good, tmp_path) == []


def test_the_scan_follows_a_name_assigned_once(tmp_path):
    source = tmp_path / "two_step.py"
    source.write_text(
        'template = self._lang.get("token_rename_done", "Renamed {ok}, failed {f}")\n'
        'print(template.format(ok=1))\n', encoding="utf-8")
    assert [p.split(" ", 1)[1] for p in _problems_in(source, tmp_path)] == [
        "'token_rename_done' (english.py) needs ['f']",
        "'token_rename_done' (fallback) needs ['f']",
    ]
