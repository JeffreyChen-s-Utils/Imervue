"""Documentation coverage: what the code offers must be named in the docs.

``test_docs_parity`` checks that the translations keep the English structure;
this checks the English docs, and every translation, against the code itself.
Each inventory is read from its source of truth:

* every ``py -m Imervue.cli`` subcommand and ``pipeline`` op;
* every MCP tool, prompt and JSON-RPC method;
* every plugin hook of ``ImervuePlugin``;
* every entry of the Extra Tools menu (its English label, as the menu shows it);
* every default Paint shortcut.

The Sphinx guide (``docs/<lang>/index.rst``) must name all of them as ````literals````;
the READMEs name the subcommands, MCP tools and prompts and the plugin hooks as
```code``` spans; ``PLUGIN_DEV_GUIDE.md`` names every hook. Names are code or
UI labels, so a translation keeps them in English too.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DOC_LANGS = ["en", "de", "es", "fr", "ja", "ko", "pt-BR", "ru", "zh-cn", "zh-tw"]
_README_LANGS = ["de", "es", "fr", "ja", "ko", "pt-BR", "ru", "zh-CN", "zh-TW"]


# --- inventories -------------------------------------------------------------

def cli_subcommands() -> list[str]:
    import argparse

    from Imervue.cli import build_parser
    action = next(a for a in build_parser()._actions  # noqa: SLF001
                  if isinstance(a, argparse._SubParsersAction))  # noqa: SLF001
    return list(action.choices)


def pipeline_ops() -> list[str]:
    from Imervue.cli import _PIPELINE_OPS
    return list(_PIPELINE_OPS)


def mcp_tools() -> list[str]:
    from Imervue.mcp_server.tools import _TOOL_DEFINITIONS
    return [tool["name"] for tool in _TOOL_DEFINITIONS]


def mcp_prompts() -> list[str]:
    from Imervue.mcp_server.prompts import _PROMPTS
    return [prompt["name"] for prompt in _PROMPTS]


def mcp_methods() -> list[str]:
    from Imervue.mcp_server.server import _METHOD_HANDLERS
    return list(_METHOD_HANDLERS)


def plugin_hooks() -> list[str]:
    from Imervue.plugin.plugin_base import ImervuePlugin
    hooks = [name for name in vars(ImervuePlugin) if name.startswith("on_")]
    return [*hooks, "register_languages", "get_translations"]


class _RecordingMenu:
    """Stands in for a QMenu: remembers every action label under its menu path."""

    def __init__(self, labels: list[tuple[str, ...]], path: tuple[str, ...] = ()) -> None:
        self._labels = labels
        self._path = path

    def addMenu(self, title: str) -> _RecordingMenu:  # noqa: N802 - Qt API
        return _RecordingMenu(self._labels, (*self._path, title))

    def addAction(self, text: str) -> SimpleNamespace:  # noqa: N802 - Qt API
        self._labels.append((*self._path, text))
        return SimpleNamespace(triggered=SimpleNamespace(connect=lambda _slot: None))

    def __getattr__(self, _name):   # setObjectName, addSeparator, ...
        return lambda *_args, **_kwargs: None


def extra_tools_entries() -> list[tuple[str, ...]]:
    """``(Extra Tools, submenu, …, label)`` for every entry, with the English labels."""
    from Imervue.menu import extra_tools_menu
    from Imervue.multi_language.english import english_word_dict
    from Imervue.multi_language.language_wrapper import language_wrapper
    labels: list[tuple[str, ...]] = []
    root = _RecordingMenu(labels)
    saved = language_wrapper.language_word_dict
    language_wrapper.language_word_dict = english_word_dict
    try:
        extra_tools_menu.build_extra_tools_menu(SimpleNamespace(menuBar=lambda: root))
    finally:
        language_wrapper.language_word_dict = saved
    return labels


def paint_shortcuts() -> list[str]:
    from Imervue.paint.shortcut_registry import DEFAULT_SHORTCUTS
    return [entry.default_key for entry in DEFAULT_SHORTCUTS]


# --- what a document names ----------------------------------------------------

def _rst_literals(text: str) -> set[str]:
    return {" ".join(m.split()) for m in re.findall(r"``(.+?)``", text, flags=re.S)}


def _md_code(text: str) -> set[str]:
    return {" ".join(m.split()) for m in re.findall(r"`([^`\n]+)`", text)}


def _named(name: str, literals: set[str], *, prefix: bool = False) -> bool:
    """*name* is a literal, or (with *prefix*) starts one: ``list-images FOLDER``, ``on_x(a)``."""
    if name in literals:
        return True
    return prefix and any(lit.startswith((name + " ", name + "(")) for lit in literals)


def _key(text: str) -> str:
    return text.replace(" ", "").lower()


def _read(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def _docs_page(lang: str) -> str:
    return _read(f"docs/{lang}/index.rst")


def _readme(lang: str | None) -> str:
    return _read("README.md" if lang is None else f"README/README_{lang}.md")


def _missing(names, literals, *, prefix=False) -> list[str]:
    return [name for name in names if not _named(name, literals, prefix=prefix)]


# --- the inventories are real ---------------------------------------------------

def test_the_inventories_are_not_empty():
    assert len(cli_subcommands()) >= 60
    assert len(mcp_tools()) >= 56
    assert len(extra_tools_entries()) >= 100
    assert "on_image_loaded" in plugin_hooks()
    assert "Ctrl+J" in paint_shortcuts()


def test_the_menu_labels_are_the_english_ones():
    entries = extra_tools_entries()
    assert ("Extra Tools", "Batch", "Deflicker (Time-lapse)") in entries
    assert ("Extra Tools", "Views", "Color blindness preview", "Off") in entries
    assert ("Extra Tools", "Views", "Timeline View", "By day") in entries


# --- the Sphinx guide, every language -------------------------------------------

@pytest.mark.parametrize("lang", _DOC_LANGS)
def test_the_guide_names_every_cli_subcommand_and_pipeline_op(lang):
    literals = _rst_literals(_docs_page(lang))
    assert _missing(cli_subcommands(), literals, prefix=True) == []
    assert _missing(pipeline_ops(), literals) == []


@pytest.mark.parametrize("lang", _DOC_LANGS)
def test_the_guide_names_every_mcp_tool_prompt_and_method(lang):
    literals = _rst_literals(_docs_page(lang))
    assert _missing(mcp_tools(), literals) == []
    assert _missing(mcp_prompts(), literals) == []
    assert _missing(mcp_methods(), literals) == []


@pytest.mark.parametrize("lang", _DOC_LANGS)
def test_the_guide_names_every_plugin_hook(lang):
    assert _missing(plugin_hooks(), _rst_literals(_docs_page(lang)), prefix=True) == []


@pytest.mark.parametrize("lang", _DOC_LANGS)
def test_the_guide_names_every_extra_tools_entry(lang):
    literals = _rst_literals(_docs_page(lang))
    missing = [" > ".join(path) for path in extra_tools_entries() if path[-1] not in literals]
    assert missing == []


@pytest.mark.parametrize("lang", _DOC_LANGS)
def test_the_guide_names_every_paint_shortcut(lang):
    keys = {_key(literal) for literal in _rst_literals(_docs_page(lang))}
    for literal in list(keys):          # "ctrl+shift+z/ctrl+y" lists two keys
        keys.update(part for part in literal.split("/") if part)
    assert [key for key in paint_shortcuts() if _key(key) not in keys] == []


# --- the READMEs and the plugin guide ---------------------------------------------

@pytest.mark.parametrize("lang", [None, *_README_LANGS])
def test_every_readme_names_the_cli_mcp_and_hooks(lang):
    code = _md_code(_readme(lang))
    assert _missing(cli_subcommands(), code, prefix=True) == []
    assert _missing(mcp_tools(), code) == []
    assert _missing(mcp_prompts(), code) == []
    assert _missing(plugin_hooks(), code, prefix=True) == []


def test_the_plugin_guide_names_every_hook():
    assert _missing(plugin_hooks(), _md_code(_read("PLUGIN_DEV_GUIDE.md")), prefix=True) == []


# --- the helpers ---------------------------------------------------------------

def test_literal_and_code_extraction():
    assert _rst_literals("a ``x`` b ``list-images\n   FOLDER``") == {"x", "list-images FOLDER"}
    assert _md_code("`a` and `on_x(p)`") == {"a", "on_x(p)"}
    assert _named("list-images", {"list-images FOLDER"}, prefix=True)
    assert _named("on_x", {"on_x(p)"}, prefix=True)
    assert not _named("on_x", {"on_xy"}, prefix=True)
    assert not _named("list-images", {"list-images FOLDER"})
