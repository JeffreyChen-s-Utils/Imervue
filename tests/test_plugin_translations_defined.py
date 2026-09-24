"""Bundled plugins define every translation key they look up.

A plugin may be installed on its own, so a key it only borrows from another
plugin (``bg_remove_menu`` from ai_background_remover, say) falls back to
English whenever that other plugin is absent. Keys shared by several plugins
must also agree word for word: ``merge_translations`` keeps whichever plugin
registered first, and safety_review finds the shared "AI Tools" submenu by its
translated title.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from Imervue.multi_language.english import english_word_dict

_PLUGINS = Path(__file__).resolve().parent.parent / "plugins"
_NAMES = sorted(p.name for p in _PLUGINS.iterdir()
                if p.is_dir() and not p.name.startswith(("_", ".")) and (p / "__init__.py").is_file())


def _looked_up(plugin: str) -> set[str]:
    keys = set()
    for path in (_PLUGINS / plugin).glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and node.args
                    and "lang" in ast.unparse(node.func.value).lower()
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                keys.add(node.args[0].value)
    return keys


def _translations(plugin: str) -> dict[str, dict[str, str]]:
    cls = importlib.import_module(plugin).plugin_class
    return getattr(cls, "get_translations", lambda _self: {})(cls.__new__(cls)) or {}


@pytest.mark.parametrize("plugin", _NAMES)
def test_every_looked_up_key_is_defined_by_the_plugin(qapp, plugin):
    english = set(_translations(plugin).get("English", {}))
    assert sorted(_looked_up(plugin) - english - set(english_word_dict)) == []


def test_shared_keys_agree_across_plugins(qapp):
    seen: dict[tuple[str, str], dict[str, str]] = {}
    for plugin in _NAMES:
        for language, table in _translations(plugin).items():
            for key, text in table.items():
                seen.setdefault((language, key), {})[plugin] = text
    clashes = {k: v for k, v in seen.items() if len(set(v.values())) > 1}
    assert clashes == {}
