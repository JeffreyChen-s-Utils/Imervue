"""Every key the UI looks up in the language dictionary is defined in it.

``lang.get("key", "English text")`` quietly falls back to the English text
when the key is missing, so a key that was never added to the dictionaries
shows English to every Chinese, Japanese and Korean user without any error.
``tests/test_translations.py`` already keeps every language in step with
``english.py``; this closes the gap on the other side, between the code and
``english.py``.

Most keys never reach ``lang.get`` as a literal: they travel with their English
fallback through a helper (``act("puppet_validate", "Validate", ...)``,
``_add_action(sub, lang, "before_after_title", "Before / After Compare", ...)``)
or sit in a table row (``("paint_layers_add_tooltip", "Add layer", ...)``).
:func:`_key_fallback_pairs` finds those as a key-shaped literal followed by an
English-text literal; 100 keys hid there.
"""
from __future__ import annotations

import ast
import re
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


_KEY_SHAPE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")


def _looks_like_text(value: str) -> bool:
    return (len(value) > 1 and not _KEY_SHAPE.match(value)
            and (" " in value or any(c.isupper() for c in value)))


def _key_fallback_pairs(source: str) -> list[tuple[int, str]]:
    """Return ``(line, key)`` for each ``"a_key", "English text"`` literal pair.

    Pairs are adjacent arguments of a call or adjacent items of a tuple or
    list. A ``.get`` on anything but the language dictionary (``meta.get(
    "project_name", "Untitled")``) reads data, not a translation, and is skipped.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                    and ast.unparse(node.func.value) not in _DICT_NAMES):
                continue
            items = node.args
        elif isinstance(node, (ast.Tuple, ast.List)):
            items = node.elts
        else:
            continue
        for key, text in zip(items, items[1:], strict=False):
            if (isinstance(key, ast.Constant) and isinstance(key.value, str)
                    and _KEY_SHAPE.match(key.value)
                    and isinstance(text, ast.Constant) and isinstance(text.value, str)
                    and _looks_like_text(text.value)):
                found.append((key.lineno, key.value))
    return found


def _sources():
    for path in _ROOT.rglob("*.py"):
        if "multi_language" not in path.parts and "__pycache__" not in path.parts:
            yield path, path.read_text(encoding="utf-8")


def test_pair_detector():
    source = "\n".join((
        "act('puppet_validate', 'Validate', run)",
        "rows = [('paint_layers_add_tooltip', 'Add layer', 1)]",
        "meta.get('project_name', 'Untitled')",
        "lang.get('shown_key', 'Shown')",
        "tools = (('select_rect', 'M'), ('brush_size', 'size_key'), ('plain', 'Plain'))",
    ))
    assert sorted(_key_fallback_pairs(source)) == [
        (1, "puppet_validate"), (2, "paint_layers_add_tooltip"), (4, "shown_key"),
    ]


def test_every_key_passed_with_a_fallback_is_in_the_english_dictionary():
    missing = sorted(
        f"{path.relative_to(_ROOT.parent).as_posix()}:{line} {key}"
        for path, source in _sources()
        for line, key in _key_fallback_pairs(source)
        if key not in english_word_dict
    )
    assert missing == []


def test_every_shortcut_dialog_label_is_translated():
    from Imervue.paint.shortcut_registry import DEFAULT_SHORTCUTS
    assert [e.label_key for e in DEFAULT_SHORTCUTS if e.label_key not in english_word_dict] == []


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
