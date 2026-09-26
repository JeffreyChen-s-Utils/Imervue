"""Plugin languages are registered before the main window builds its text.

The window used to reset the language before any plugin was loaded, so a
plugin language (Spanish) picked in the Language menu was never applied
after the restart the menu asks for.
"""
from __future__ import annotations

import sys
import textwrap
import uuid
from unittest.mock import MagicMock

import pytest

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin import plugin_manager
from Imervue.plugin.plugin_manager import (
    PluginManager,
    apply_saved_language,
    register_plugin_languages,
)

_LANGUAGE_PLUGIN = textwrap.dedent("""\
    from Imervue.multi_language.language_wrapper import language_wrapper
    from Imervue.plugin.plugin_base import ImervuePlugin

    EVENTS = []


    class KlingonPlugin(ImervuePlugin):
        plugin_name = "Klingon"

        def __init__(self, main_window):
            EVENTS.append("instantiated")
            super().__init__(main_window)

        @classmethod
        def register_languages(cls):
            EVENTS.append("register_languages")
            language_wrapper.register_language(
                "Klingon", "tlhIngan Hol", {"menu_bar_language": "Hol"})


    plugin_class = KlingonPlugin
""")


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch):
    """Copies of the global language state; plugin imports and sys.path undone."""
    copies = {code: dict(words) for code, words in language_wrapper.choose_language_dict.items()}
    monkeypatch.setattr(language_wrapper, "choose_language_dict", copies)
    monkeypatch.setattr(language_wrapper, "plugin_languages", {})
    monkeypatch.setattr(language_wrapper, "language", "English")
    monkeypatch.setattr(language_wrapper, "language_word_dict", copies["English"])
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield
    for name in [n for n in sys.modules if n.startswith(("langplug_", "aaa_broken"))]:
        sys.modules.pop(name, None)


def _plugin_dir(tmp_path, code=_LANGUAGE_PLUGIN):
    """A plugins directory holding one package plugin; returns (dir, module name)."""
    name = f"langplug_{uuid.uuid4().hex[:8]}"
    package = tmp_path / "plugins" / name
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(code, encoding="utf-8")
    return tmp_path / "plugins", name


def _main_window():
    window = MagicMock()
    window.viewer = MagicMock()
    return window


def test_the_pre_pass_registers_languages_without_instantiating(tmp_path):
    plugins, name = _plugin_dir(tmp_path)
    register_plugin_languages([plugins])
    assert language_wrapper.plugin_languages == {"Klingon": "tlhIngan Hol"}
    assert sys.modules[name].EVENTS == ["register_languages"]


def test_a_saved_plugin_language_is_applied(tmp_path):
    plugins, _name = _plugin_dir(tmp_path)
    apply_saved_language("Klingon", [plugins])
    assert language_wrapper.language == "Klingon"
    assert language_wrapper.language_word_dict["menu_bar_language"] == "Hol"


def test_a_built_in_language_does_not_import_the_plugins(tmp_path):
    plugins, name = _plugin_dir(tmp_path)
    apply_saved_language("Japanese", [plugins])
    assert language_wrapper.language == "Japanese"
    assert name not in sys.modules


def test_a_language_no_plugin_provides_keeps_the_current_one(tmp_path):
    plugins, _name = _plugin_dir(tmp_path)
    apply_saved_language("Vulcan", [plugins])
    assert language_wrapper.language == "English"


def test_the_default_plugin_directory_is_used(monkeypatch, tmp_path):
    plugins, _name = _plugin_dir(tmp_path)
    monkeypatch.setattr(plugin_manager, "_plugins_dir", lambda: plugins)
    apply_saved_language("Klingon")
    assert language_wrapper.language == "Klingon"


def test_loading_registers_before_instantiating_and_keeps_the_active_dict(tmp_path):
    plugins, name = _plugin_dir(tmp_path)
    apply_saved_language("Klingon", [plugins])
    active = language_wrapper.language_word_dict
    manager = PluginManager(_main_window())
    manager.discover_and_load([plugins])
    assert sys.modules[name].EVENTS == [
        "register_languages", "register_languages", "instantiated"]
    assert language_wrapper.choose_language_dict["Klingon"] is active
    language_wrapper.merge_translations({"Klingon": {"later_key": "later"}})
    assert active["later_key"] == "later"


def test_a_failing_register_languages_still_loads_the_plugin(tmp_path, caplog):
    registers = '        EVENTS.append("register_languages")\n'
    assert registers in _LANGUAGE_PLUGIN
    code = _LANGUAGE_PLUGIN.replace(registers, registers + '        raise ValueError("bad")\n')
    plugins, name = _plugin_dir(tmp_path, code)
    manager = PluginManager(_main_window())
    with caplog.at_level("ERROR", logger="Imervue.plugin"):
        manager.discover_and_load([plugins])
    assert [p.plugin_name for p in manager.plugins] == ["Klingon"]
    assert sys.modules[name].EVENTS == ["register_languages", "instantiated"]
    assert any("register_languages error" in r.getMessage() for r in caplog.records)


def test_a_broken_plugin_does_not_stop_the_pre_pass(tmp_path):
    plugins, _name = _plugin_dir(tmp_path)
    broken = plugins / "aaa_broken"
    broken.mkdir()
    (broken / "__init__.py").write_text("raise ImportError('missing')\n", encoding="utf-8")
    register_plugin_languages([plugins])
    assert "Klingon" in language_wrapper.plugin_languages


def test_the_spanish_plugin_registers_from_the_class():
    from spanish_translation.spanish_translation_plugin import SpanishTranslationPlugin
    SpanishTranslationPlugin.register_languages()
    assert language_wrapper.plugin_languages == {"Spanish": "Español"}
    assert language_wrapper.choose_language_dict["Spanish"]["menu_bar_language"]


@pytest.mark.parametrize("registered", [True, False])
def test_the_spanish_plugin_registers_on_load_only_when_missing(monkeypatch, registered):
    from spanish_translation.spanish_translation_plugin import SpanishTranslationPlugin
    calls = []
    monkeypatch.setattr(SpanishTranslationPlugin, "register_languages",
                        classmethod(lambda cls: calls.append(cls)))
    if registered:
        language_wrapper.plugin_languages["Spanish"] = "Español"
    SpanishTranslationPlugin(_main_window()).on_plugin_loaded()
    assert calls == ([] if registered else [SpanishTranslationPlugin])
