"""Every key the UI looks up in the language dictionary is defined in it.

``lang.get("key", "English text")`` quietly falls back to the English text
when the key is missing, so a key that was never added to the dictionaries
shows English to every Chinese, Japanese and Korean user without any error.
``tests/test_translations.py`` already keeps every language in step with
``english.py``; this closes the gap on the other side, between the code and
``english.py``.
"""
from __future__ import annotations

import ast
from pathlib import Path

from Imervue.multi_language.english import english_word_dict

_ROOT = Path(__file__).resolve().parent.parent / "Imervue"
# Names the code binds the active language dictionary to.
_DICT_NAMES = {"lang", "self._lang", "language_wrapper.language_word_dict"}


def _lookups(source: str) -> list[tuple[int, str]]:
    """Return ``(line, key)`` for each ``<language dict>.get("key", ...)`` call."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and node.args
                and ast.unparse(node.func.value) in _DICT_NAMES
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            found.append((node.lineno, node.args[0].value))
    return found


def test_lookup_detector():
    source = "lang.get('a', 'A')\nself._lang.get('b')\nother.get('c', 'C')\nlang.get(key)\n"
    assert _lookups(source) == [(1, "a"), (2, "b")]


def test_every_looked_up_key_is_in_the_english_dictionary():
    missing = sorted(
        f"{path.relative_to(_ROOT.parent).as_posix()}:{line} {key}"
        for path in _ROOT.rglob("*.py")
        if "multi_language" not in path.parts and "__pycache__" not in path.parts
        for line, key in _lookups(path.read_text(encoding="utf-8"))
        if key not in english_word_dict
    )
    assert missing == []
