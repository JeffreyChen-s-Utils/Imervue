"""Contracts of the plugin manager: hook order, failure isolation, status rows, reloads.

Pins what ``tests/test_plugin.py`` leaves open: the order every hook reaches
the plugins in, what a failure in each step logs and publishes, the
``sys.path`` / ``sys.modules`` bookkeeping, and the public surface of
:class:`PluginManager` and its module.
"""
from __future__ import annotations

import logging
import sys
import textwrap
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from Imervue.plugin import plugin_manager
from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.plugin.plugin_manager import PluginManager
from Imervue.plugin.status import status_registry

_LOGGER = "Imervue.plugin"
_DISPATCH_CALLS = [
    ("dispatch_build_menu_bar", "on_build_menu_bar", ("menu_bar",)),
    ("dispatch_build_context_menu", "on_build_context_menu", ("menu", "viewer")),
    ("dispatch_image_loaded", "on_image_loaded", ("a.png", "viewer")),
    ("dispatch_folder_opened", "on_folder_opened", ("dir", ["dir/a.png"], "viewer")),
    ("dispatch_image_switched", "on_image_switched", ("b.png", "viewer")),
    ("dispatch_image_deleted", "on_image_deleted", (["a.png"], "viewer")),
    ("dispatch_pet_created", "on_pet_created", ("pet",)),
    ("dispatch_app_closing", "on_app_closing", ("window",)),
]


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch):
    """Language dicts copied, sys.path restored and this file's plugin modules forgotten."""
    from Imervue.multi_language.language_wrapper import language_wrapper
    copies = {code: dict(words) for code, words in language_wrapper.choose_language_dict.items()}
    monkeypatch.setattr(language_wrapper, "choose_language_dict", copies)
    monkeypatch.setattr(language_wrapper, "plugin_languages", dict(language_wrapper.plugin_languages))
    monkeypatch.setattr(language_wrapper, "language", language_wrapper.language)
    monkeypatch.setattr(language_wrapper, "language_word_dict", copies[language_wrapper.language])
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield
    for name in [n for n in sys.modules if n.startswith("pmc_")]:
        sys.modules.pop(name, None)


def _unique(prefix: str = "pmc") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _package(root, name, body):
    package = root / name
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return package


def _plugin_source(class_name, plugin_name, extra=""):
    return (
        "from Imervue.plugin.plugin_base import ImervuePlugin\n"
        f"class {class_name}(ImervuePlugin):\n"
        f"    plugin_name = '{plugin_name}'\n"
        f"{textwrap.indent(textwrap.dedent(extra), '    ')}"
        f"plugin_class = {class_name}\n"
    )


def _recording_plugins(manager, names, journal):
    """Inject mocks that record ``(plugin, hook)`` into one shared journal."""
    plugins = []
    for name in names:
        plugin = MagicMock(spec=ImervuePlugin)
        plugin.plugin_name = name
        for hook in [h for h in vars(ImervuePlugin) if h.startswith("on_")]:
            getattr(plugin, hook).side_effect = (
                lambda *_a, _n=name, _h=hook: journal.append((_n, _h)))
        manager._plugins.append(plugin)
        plugins.append(plugin)
    return plugins


def _rows(manager):
    return {row.name: row for row in status_registry.snapshot(manager.status_scope)}


# ---------------------------------------------------------------- public surface

def test_the_manager_keeps_every_public_method():
    expected = {
        "plugins", "discover_and_load", "refresh_imports", "unload_all", "connect_pet_hooks",
        *(method for method, _hook, _args in _DISPATCH_CALLS), "dispatch_key_press",
    }
    assert expected <= {n for n in dir(PluginManager) if not n.startswith("_")}


def test_the_module_keeps_its_public_functions():
    for name in ("PluginManager", "register_plugin_languages", "apply_saved_language", "logger"):
        assert hasattr(plugin_manager, name)
    assert plugin_manager.logger.name == _LOGGER


def test_every_on_hook_of_the_base_class_has_a_dispatcher():
    hooks = {h for h in vars(ImervuePlugin) if h.startswith("on_")}
    dispatched = {hook for _m, hook, _a in _DISPATCH_CALLS} | {"on_key_press"}
    lifecycle = {"on_plugin_loaded", "on_plugin_unloaded"}
    tabs = {"on_build_main_tabs"}        # dispatched by Imervue.integration_guide
    assert hooks - lifecycle - tabs == dispatched


# ---------------------------------------------------------------- dispatch order and isolation

@pytest.mark.parametrize(("method", "hook", "args"), _DISPATCH_CALLS)
def test_each_hook_reaches_the_plugins_in_load_order(method, hook, args):
    manager = PluginManager(MagicMock())
    journal = []
    _recording_plugins(manager, ["first", "second", "third"], journal)
    getattr(manager, method)(*args)
    assert journal == [("first", hook), ("second", hook), ("third", hook)]


@pytest.mark.parametrize(("method", "hook", "args"), _DISPATCH_CALLS)
def test_a_failing_hook_is_logged_and_the_next_plugin_still_runs(method, hook, args, caplog):
    manager = PluginManager(MagicMock())
    journal = []
    first, _second = _recording_plugins(manager, ["first", "second"], journal)
    getattr(first, hook).side_effect = RuntimeError("boom")
    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        assert getattr(manager, method)(*args) is None
    assert journal == [("second", hook)]
    assert f"[first] {hook} error: boom" in caplog.text
    assert caplog.records[-1].exc_info is not None


def test_key_press_stops_at_the_first_plugin_that_consumes_it():
    manager = PluginManager(MagicMock())
    first, second, third = (MagicMock(plugin_name=n) for n in ("a", "b", "c"))
    first.on_key_press.return_value = False
    second.on_key_press.return_value = True
    manager._plugins.extend([first, second, third])
    assert manager.dispatch_key_press(65, 0, "viewer") is True
    first.on_key_press.assert_called_once_with(65, 0, "viewer")
    third.on_key_press.assert_not_called()


def test_a_failing_key_press_is_logged_and_the_next_plugin_may_consume(caplog):
    manager = PluginManager(MagicMock())
    first, second = MagicMock(plugin_name="a"), MagicMock(plugin_name="b")
    first.on_key_press.side_effect = KeyError("k")
    second.on_key_press.return_value = 1          # truthy, not just True
    manager._plugins.extend([first, second])
    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        assert manager.dispatch_key_press(1, 0, None) is True
    assert "[a] on_key_press error:" in caplog.text


def test_unload_all_runs_in_reverse_order_clears_and_drops_the_status_rows(caplog):
    manager = PluginManager(MagicMock())
    journal = []
    first, _second, _third = _recording_plugins(manager, ["first", "second", "third"], journal)
    first.on_plugin_unloaded.side_effect = RuntimeError("stuck")
    status_registry.publish(manager.status_scope + ":X", "X", "loaded", "", scope=manager.status_scope)
    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        manager.unload_all()
    assert journal == [("third", "on_plugin_unloaded"), ("second", "on_plugin_unloaded")]
    assert "[first] on_plugin_unloaded error: stuck" in caplog.text
    assert manager.plugins == []
    assert not status_registry.snapshot(manager.status_scope)


def test_connect_pet_hooks_routes_later_pets_through_dispatch():
    window = MagicMock()
    window.pet_workspace.pet_window.return_value = None
    manager = PluginManager(window)
    journal = []
    _recording_plugins(manager, ["only"], journal)
    manager.connect_pet_hooks()
    callback = window.pet_workspace.pet_created.connect.call_args.args[0]
    callback("new pet")
    assert journal == [("only", "on_pet_created")]
    assert manager._pet_hook_connected is True


# ---------------------------------------------------------------- discovery and loading

def test_discovery_prepends_each_existing_dir_once_and_skips_missing_ones(tmp_path, caplog):
    first, second, missing = tmp_path / "a", tmp_path / "b", tmp_path / "missing"
    first.mkdir()
    second.mkdir()
    manager = PluginManager(MagicMock())
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        manager.discover_and_load([first, missing, second])
        manager.discover_and_load([first, missing, second])
    assert sys.path[:2] == [str(second), str(first)]
    assert sys.path.count(str(first)) == 1
    assert f"Plugin directory does not exist, skipping: {missing}" in caplog.text


def test_plugins_load_across_dirs_in_dir_then_name_order(tmp_path):
    late, early = tmp_path / "late", tmp_path / "early"
    tag = _unique()
    _package(late, f"pmc_b_{tag}", _plugin_source("Bee", "Bee"))
    _package(late, f"pmc_a_{tag}", _plugin_source("Ay", "Ay"))
    _package(early, f"pmc_z_{tag}", _plugin_source("Zed", "Zed"))
    manager = PluginManager(MagicMock())
    manager.discover_and_load([late, early])
    assert [p.plugin_name for p in manager.plugins] == ["Ay", "Bee", "Zed"]


def test_candidates_ignore_init_files_plain_dirs_and_non_python_files(tmp_path):
    (tmp_path / "__init__.py").write_text("raise RuntimeError('never imported')", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    (tmp_path / "pmc_data_only").mkdir()
    manager = PluginManager(MagicMock())
    manager.discover_and_load([tmp_path])
    assert manager.plugins == []
    assert _rows(manager) == {}


def test_a_loaded_plugin_publishes_a_loaded_row(tmp_path):
    name = _unique()
    _package(tmp_path, name, _plugin_source("Fine", "Fine Plugin"))
    manager = PluginManager(MagicMock())
    manager.discover_and_load([tmp_path])
    row = _rows(manager)["Fine Plugin"]
    assert (row.status, row.reason) == (
        "loaded", "Optional dependencies, models and backends are checked on use")


def test_import_failure_and_missing_class_publish_failed_rows(tmp_path, caplog):
    broken, empty = _unique(), _unique()
    _package(tmp_path, broken, "raise ImportError('needs torch')\n")
    _package(tmp_path, empty, "VALUE = 1\n")
    manager = PluginManager(MagicMock())
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        manager.discover_and_load([tmp_path])
    rows = _rows(manager)
    assert (rows[broken].status, rows[broken].reason) == ("failed", "needs torch")
    assert (rows[empty].status, rows[empty].reason) == ("failed", "No valid ImervuePlugin class")
    assert f"Failed to load plugin '{broken}': needs torch" in caplog.text
    assert "No plugin class found in" in caplog.text


def test_an_exception_without_a_message_reports_its_type(tmp_path):
    name = _unique()
    _package(tmp_path, name, "raise RuntimeError()\n")
    manager = PluginManager(MagicMock())
    manager.discover_and_load([tmp_path])
    assert _rows(manager)[name].reason == "RuntimeError"


def test_an_incompatible_package_publishes_its_reason_without_importing(tmp_path):
    name = _unique()
    package = _package(tmp_path, name, "raise RuntimeError('imported')\n")
    (package / "plugin.json").write_text('{"min_api_version": 999}', encoding="utf-8")
    manager = PluginManager(MagicMock())
    manager.discover_and_load([tmp_path])
    row = _rows(manager)[name]
    assert (row.status, row.reason) == (
        "failed", "Incompatible plugin API; update Imervue or the plugin")
    assert name not in sys.modules


def test_a_non_plugin_plugin_class_is_rejected(tmp_path, caplog):
    name = _unique()
    _package(tmp_path, name, "plugin_class = int\n")
    manager = PluginManager(MagicMock())
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        manager.discover_and_load([tmp_path])
    assert manager.plugins == []
    assert "is not a subclass of ImervuePlugin, skipping." in caplog.text


def test_a_single_file_plugin_is_registered_in_sys_modules(tmp_path):
    name = _unique()
    (tmp_path / f"{name}.py").write_text(_plugin_source("Solo", "Solo"), encoding="utf-8")
    manager = PluginManager(MagicMock())
    manager.discover_and_load([tmp_path])
    assert [p.plugin_name for p in manager.plugins] == ["Solo"]
    assert sys.modules[name].plugin_class is type(manager.plugins[0])


def test_a_failing_on_plugin_loaded_is_rolled_back(tmp_path, caplog):
    name = _unique()
    extra = """
        unloaded = []
        def on_plugin_loaded(self):
            raise ValueError("bad init")
        def on_plugin_unloaded(self):
            type(self).unloaded.append(self)
    """
    _package(tmp_path, name, _plugin_source("Shaky", "Shaky", extra))
    manager = PluginManager(MagicMock())
    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        manager.discover_and_load([tmp_path])
    assert manager.plugins == []
    assert len(sys.modules[name].plugin_class.unloaded) == 1
    row = _rows(manager)["Shaky"]
    assert (row.status, row.reason) == ("failed", "bad init")
    assert "Failed to instantiate plugin 'Shaky': bad init" in caplog.text


def test_a_failure_after_registration_removes_the_plugin_again(tmp_path, caplog):
    name = _unique()
    extra = """
        def get_translations(self):
            raise RuntimeError("bad strings")
        def on_plugin_unloaded(self):
            raise OSError("cleanup failed too")
    """
    _package(tmp_path, name, _plugin_source("Late", "Late", extra))
    manager = PluginManager(MagicMock())
    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        manager.discover_and_load([tmp_path])
    assert manager.plugins == []
    assert "Failed to clean up partially loaded plugin" in caplog.text
    assert _rows(manager)["Late"].reason == "bad strings"


def test_a_constructor_failure_skips_cleanup(tmp_path):
    name = _unique()
    extra = """
        unloaded = []
        def __init__(self, main_window):
            raise RuntimeError("ctor")
        def on_plugin_unloaded(self):
            type(self).unloaded.append(self)
    """
    _package(tmp_path, name, _plugin_source("Ctor", "Ctor", extra))
    manager = PluginManager(MagicMock())
    manager.discover_and_load([tmp_path])
    assert sys.modules[name].plugin_class.unloaded == []
    assert _rows(manager)["Ctor"].reason == "ctor"


def test_a_duplicate_class_name_is_warned_and_skipped(tmp_path, caplog):
    first, second = tmp_path / "a", tmp_path / "b"
    _package(first, _unique(), _plugin_source("Twin", "Twin 1"))
    _package(second, _unique(), _plugin_source("Twin", "Twin 2"))
    manager = PluginManager(MagicMock())
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        manager.discover_and_load([first, second])
    assert [p.plugin_name for p in manager.plugins] == ["Twin 1"]
    assert "Plugin 'Twin' already loaded, skipping duplicate." in caplog.text


def test_the_default_dir_is_read_at_call_time(monkeypatch, tmp_path):
    name = _unique()
    _package(tmp_path, name, _plugin_source("Default", "Default"))
    monkeypatch.setattr(plugin_manager, "_plugins_dir", lambda: tmp_path)
    manager = PluginManager(MagicMock())
    manager.discover_and_load()
    assert [p.plugin_name for p in manager.plugins] == ["Default"]


# ---------------------------------------------------------------- refresh_imports

def test_refresh_imports_forgets_only_this_managers_modules_and_their_bytecode(tmp_path):
    mine, other = tmp_path / "mine", tmp_path / "other"
    mine.mkdir()
    other.mkdir()
    cached = mine / "pmc_mine.cpython.pyc"
    cached.write_bytes(b"x")
    outside_cache = other / "pmc_cache.pyc"
    outside_cache.write_bytes(b"x")
    sys.modules["pmc_mine"] = SimpleNamespace(__file__=str(mine / "m.py"), __cached__=str(cached))
    sys.modules["pmc_mine_far_cache"] = SimpleNamespace(
        __file__=str(mine / "n.py"), __cached__=str(outside_cache))
    sys.modules["pmc_other"] = SimpleNamespace(__file__=str(other / "o.py"))
    sys.modules["pmc_builtin"] = SimpleNamespace()
    manager = PluginManager(MagicMock())
    manager.discover_and_load([mine])
    manager.refresh_imports()
    assert "pmc_mine" not in sys.modules
    assert "pmc_mine_far_cache" not in sys.modules
    assert {"pmc_other", "pmc_builtin"} <= set(sys.modules)
    assert not cached.exists()
    assert outside_cache.exists()


def test_refresh_imports_logs_bytecode_it_cannot_remove(tmp_path, monkeypatch, caplog):
    tmp_path.joinpath("pmc_locked.pyc").write_bytes(b"x")
    sys.modules["pmc_locked"] = SimpleNamespace(
        __file__=str(tmp_path / "l.py"), __cached__=str(tmp_path / "pmc_locked.pyc"))
    manager = PluginManager(MagicMock())
    manager.discover_and_load([tmp_path])

    def refuse(self, missing_ok=False):
        raise PermissionError("locked")
    monkeypatch.setattr(type(tmp_path), "unlink", refuse)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        manager.refresh_imports()
    assert "pmc_locked" not in sys.modules
    assert "Could not remove plugin bytecode" in caplog.text


def test_refresh_imports_before_any_discovery_touches_nothing():
    sys.modules["pmc_untouched"] = SimpleNamespace(__file__=__file__)
    PluginManager(MagicMock()).refresh_imports()
    assert "pmc_untouched" in sys.modules
