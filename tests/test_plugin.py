"""Tests for plugin system: plugin_base, plugin_manager, pip_installer, plugin_downloader."""
from __future__ import annotations

import importlib
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ===========================
# Helpers
# ===========================

def _create_plugin_package(plugin_dir: Path, name: str, code: str) -> Path:
    """Create a plugin package directory with __init__.py."""
    pkg = plugin_dir / name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(code, encoding="utf-8")
    return pkg


def _create_plugin_file(plugin_dir: Path, name: str, code: str) -> Path:
    """Create a single-file plugin (.py)."""
    plugin_dir.mkdir(parents=True, exist_ok=True)
    f = plugin_dir / f"{name}.py"
    f.write_text(code, encoding="utf-8")
    return f


def _make_mock_main_window():
    """Create a mock ImervueMainWindow with viewer attribute."""
    mw = MagicMock()
    mw.viewer = MagicMock()
    return mw


# ===========================
# ImervuePlugin base class
# ===========================

class TestImervuePlugin:
    def test_default_attributes(self):
        from Imervue.plugin.plugin_base import ImervuePlugin
        assert ImervuePlugin.plugin_name == "Unnamed Plugin"
        assert ImervuePlugin.plugin_version == "0.0.1"
        assert ImervuePlugin.plugin_description == ""
        assert ImervuePlugin.plugin_author == ""

    def test_instantiation(self):
        from Imervue.plugin.plugin_base import ImervuePlugin
        mw = _make_mock_main_window()
        plugin = ImervuePlugin(mw)
        assert plugin.main_window is mw
        assert plugin.viewer is mw.viewer

    def test_lifecycle_hooks_are_noop(self):
        from Imervue.plugin.plugin_base import ImervuePlugin
        mw = _make_mock_main_window()
        plugin = ImervuePlugin(mw)
        # Should not raise
        plugin.on_plugin_loaded()
        plugin.on_plugin_unloaded()

    def test_menu_hooks_are_noop(self):
        from Imervue.plugin.plugin_base import ImervuePlugin
        mw = _make_mock_main_window()
        plugin = ImervuePlugin(mw)
        plugin.on_build_menu_bar(MagicMock())
        plugin.on_build_context_menu(MagicMock(), mw.viewer)

    def test_image_hooks_are_noop(self):
        from Imervue.plugin.plugin_base import ImervuePlugin
        mw = _make_mock_main_window()
        plugin = ImervuePlugin(mw)
        plugin.on_image_loaded("/img.png", mw.viewer)
        plugin.on_folder_opened("/folder", ["/folder/a.png"], mw.viewer)
        plugin.on_image_switched("/img2.png", mw.viewer)
        plugin.on_image_deleted(["/img.png"], mw.viewer)

    def test_on_key_press_returns_false(self):
        from Imervue.plugin.plugin_base import ImervuePlugin
        mw = _make_mock_main_window()
        plugin = ImervuePlugin(mw)
        assert plugin.on_key_press(0, 0, mw.viewer) is False

    def test_get_translations_returns_empty(self):
        from Imervue.plugin.plugin_base import ImervuePlugin
        mw = _make_mock_main_window()
        plugin = ImervuePlugin(mw)
        assert plugin.get_translations() == {}

    def test_on_app_closing_is_noop(self):
        from Imervue.plugin.plugin_base import ImervuePlugin
        mw = _make_mock_main_window()
        plugin = ImervuePlugin(mw)
        plugin.on_app_closing(mw)


# ===========================
# PluginManager
# ===========================

class TestPluginManager:
    def test_initial_state(self):
        from Imervue.plugin.plugin_manager import PluginManager
        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        assert pm.plugins == []
        assert pm.main_window is mw

    def test_plugins_returns_copy(self):
        from Imervue.plugin.plugin_manager import PluginManager
        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        plugins = pm.plugins
        plugins.append("fake")
        assert pm.plugins == []  # internal list unchanged

    def test_discover_nonexistent_dir(self, tmp_path):
        """discover_and_load with a non-existent directory should not crash."""
        from Imervue.plugin.plugin_manager import PluginManager
        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([tmp_path / "no_such_dir"])
        assert pm.plugins == []

    def test_discover_empty_dir(self, tmp_path):
        """Empty plugin directory yields no plugins."""
        from Imervue.plugin.plugin_manager import PluginManager
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])
        assert pm.plugins == []

    def test_load_plugin_package(self, tmp_path):
        """Load a plugin from a package with plugin_class attribute."""
        from Imervue.plugin.plugin_manager import PluginManager
        plugin_dir = tmp_path / "plugins"
        code = textwrap.dedent("""\
            from Imervue.plugin.plugin_base import ImervuePlugin

            class HelloPlugin(ImervuePlugin):
                plugin_name = "Hello"
                plugin_version = "1.0.0"
                plugin_author = "Test"
                plugin_description = "A test plugin"

            plugin_class = HelloPlugin
        """)
        _create_plugin_package(plugin_dir, "hello_plugin", code)

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])

        assert len(pm.plugins) == 1
        p = pm.plugins[0]
        assert p.plugin_name == "Hello"
        assert p.plugin_version == "1.0.0"
        assert p.plugin_author == "Test"

    def test_load_plugin_auto_detect_subclass(self, tmp_path):
        """Load a plugin package without plugin_class — auto-detect ImervuePlugin subclass."""
        from Imervue.plugin.plugin_manager import PluginManager
        plugin_dir = tmp_path / "plugins"
        code = textwrap.dedent("""\
            from Imervue.plugin.plugin_base import ImervuePlugin

            class AutoPlugin(ImervuePlugin):
                plugin_name = "AutoDetect"
                plugin_version = "0.1.0"
                plugin_author = "Auto"
        """)
        _create_plugin_package(plugin_dir, "auto_plugin", code)

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])

        assert len(pm.plugins) == 1
        assert pm.plugins[0].plugin_name == "AutoDetect"

    def test_load_single_file_plugin(self, tmp_path):
        """Load a plugin from a single .py file."""
        from Imervue.plugin.plugin_manager import PluginManager
        plugin_dir = tmp_path / "plugins"
        code = textwrap.dedent("""\
            from Imervue.plugin.plugin_base import ImervuePlugin

            class FilePlugin(ImervuePlugin):
                plugin_name = "FileBased"
                plugin_version = "0.2.0"
                plugin_author = "File"

            plugin_class = FilePlugin
        """)
        _create_plugin_file(plugin_dir, "file_plugin", code)

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])

        assert len(pm.plugins) == 1
        assert pm.plugins[0].plugin_name == "FileBased"

    def test_skip_duplicate_plugin(self, tmp_path):
        """Same plugin class name should not be loaded twice."""
        from Imervue.plugin.plugin_manager import PluginManager
        plugin_dir = tmp_path / "plugins"
        code = textwrap.dedent("""\
            from Imervue.plugin.plugin_base import ImervuePlugin

            class DupPlugin(ImervuePlugin):
                plugin_name = "Dup"
                plugin_version = "1.0.0"
                plugin_author = "Test"

            plugin_class = DupPlugin
        """)
        _create_plugin_package(plugin_dir, "dup1", code)
        _create_plugin_package(plugin_dir, "dup2", code)

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])

        assert len(pm.plugins) == 1

    def test_skip_package_without_plugin_class(self, tmp_path):
        """A package with no ImervuePlugin subclass is skipped."""
        from Imervue.plugin.plugin_manager import PluginManager
        plugin_dir = tmp_path / "plugins"
        code = "x = 42\n"
        _create_plugin_package(plugin_dir, "not_a_plugin", code)

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])
        assert pm.plugins == []

    def test_broken_plugin_does_not_crash(self, tmp_path):
        """A plugin with a syntax error should be skipped, not crash the manager."""
        from Imervue.plugin.plugin_manager import PluginManager
        plugin_dir = tmp_path / "plugins"
        _create_plugin_package(plugin_dir, "broken_plugin", "def broken(:\n")

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])
        assert pm.plugins == []

    def test_on_plugin_loaded_called(self, tmp_path):
        """on_plugin_loaded should be called during discover_and_load."""
        from Imervue.plugin.plugin_manager import PluginManager
        plugin_dir = tmp_path / "plugins"
        code = textwrap.dedent("""\
            from Imervue.plugin.plugin_base import ImervuePlugin

            class TrackPlugin(ImervuePlugin):
                plugin_name = "Track"
                loaded = False

                def on_plugin_loaded(self):
                    TrackPlugin.loaded = True

            plugin_class = TrackPlugin
        """)
        _create_plugin_package(plugin_dir, "track_plugin", code)

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])

        assert len(pm.plugins) == 1
        # Access the class-level flag through the module
        assert pm.plugins[0].__class__.loaded is True

    def test_plugin_translations_merged(self, tmp_path):
        """Plugin translations should be merged into language_wrapper."""
        from Imervue.plugin.plugin_manager import PluginManager
        from Imervue.multi_language.language_wrapper import language_wrapper

        plugin_dir = tmp_path / "plugins"
        code = textwrap.dedent("""\
            from Imervue.plugin.plugin_base import ImervuePlugin

            class TransPlugin(ImervuePlugin):
                plugin_name = "TransTest"

                def get_translations(self):
                    return {
                        "English": {"trans_test_key": "Test Value"},
                    }

            plugin_class = TransPlugin
        """)
        _create_plugin_package(plugin_dir, "trans_plugin", code)

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])

        assert language_wrapper.language_word_dict.get("trans_test_key") == "Test Value"
        # Cleanup
        language_wrapper.language_word_dict.pop("trans_test_key", None)

    def test_unload_all(self, tmp_path):
        """unload_all should call on_plugin_unloaded and clear the list."""
        from Imervue.plugin.plugin_manager import PluginManager
        plugin_dir = tmp_path / "plugins"
        code = textwrap.dedent("""\
            from Imervue.plugin.plugin_base import ImervuePlugin

            class UnloadPlugin(ImervuePlugin):
                plugin_name = "Unload"
                unloaded = False

                def on_plugin_unloaded(self):
                    UnloadPlugin.unloaded = True

            plugin_class = UnloadPlugin
        """)
        _create_plugin_package(plugin_dir, "unload_plugin", code)

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])
        assert len(pm.plugins) == 1

        plugin_cls = pm.plugins[0].__class__
        pm.unload_all()

        assert pm.plugins == []
        assert plugin_cls.unloaded is True

    def test_unload_all_error_does_not_crash(self, tmp_path):
        """If on_plugin_unloaded raises, unload_all should still clear the list."""
        from Imervue.plugin.plugin_manager import PluginManager
        plugin_dir = tmp_path / "plugins"
        code = textwrap.dedent("""\
            from Imervue.plugin.plugin_base import ImervuePlugin

            class CrashUnloadPlugin(ImervuePlugin):
                plugin_name = "CrashUnload"

                def on_plugin_unloaded(self):
                    raise RuntimeError("boom")

            plugin_class = CrashUnloadPlugin
        """)
        _create_plugin_package(plugin_dir, "crash_unload", code)

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugin_dir])
        pm.unload_all()
        assert pm.plugins == []


# ===========================
# PluginManager dispatch hooks
# ===========================

class TestPluginManagerDispatch:
    """Test dispatch methods by directly injecting mock plugins into the manager."""

    def _make_pm_with_mock_plugin(self):
        from Imervue.plugin.plugin_manager import PluginManager
        from Imervue.plugin.plugin_base import ImervuePlugin
        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        plugin = MagicMock(spec=ImervuePlugin)
        plugin.plugin_name = "MockPlugin"
        pm._plugins.append(plugin)
        return pm, mw, plugin

    def test_dispatch_image_loaded(self):
        pm, mw, plugin = self._make_pm_with_mock_plugin()
        pm.dispatch_image_loaded("/test.png", mw.viewer)
        plugin.on_image_loaded.assert_called_once_with("/test.png", mw.viewer)

    def test_dispatch_folder_opened(self):
        pm, mw, plugin = self._make_pm_with_mock_plugin()
        pm.dispatch_folder_opened("/folder", ["/folder/a.png"], mw.viewer)
        plugin.on_folder_opened.assert_called_once_with("/folder", ["/folder/a.png"], mw.viewer)

    def test_dispatch_image_switched(self):
        pm, mw, plugin = self._make_pm_with_mock_plugin()
        pm.dispatch_image_switched("/new.png", mw.viewer)
        plugin.on_image_switched.assert_called_once_with("/new.png", mw.viewer)

    def test_dispatch_image_deleted(self):
        pm, mw, plugin = self._make_pm_with_mock_plugin()
        pm.dispatch_image_deleted(["/a.png"], mw.viewer)
        plugin.on_image_deleted.assert_called_once_with(["/a.png"], mw.viewer)

    def test_dispatch_key_press_consumed(self):
        pm, mw, plugin = self._make_pm_with_mock_plugin()
        plugin.on_key_press.return_value = True
        assert pm.dispatch_key_press(65, 0, mw.viewer) is True
        plugin.on_key_press.assert_called_once_with(65, 0, mw.viewer)

    def test_dispatch_key_press_not_consumed(self):
        pm, mw, plugin = self._make_pm_with_mock_plugin()
        plugin.on_key_press.return_value = False
        assert pm.dispatch_key_press(65, 0, mw.viewer) is False

    def test_dispatch_app_closing(self):
        pm, mw, plugin = self._make_pm_with_mock_plugin()
        pm.dispatch_app_closing(mw)
        plugin.on_app_closing.assert_called_once_with(mw)

    def test_dispatch_build_menu_bar(self):
        pm, mw, plugin = self._make_pm_with_mock_plugin()
        menu_bar = MagicMock()
        pm.dispatch_build_menu_bar(menu_bar)
        plugin.on_build_menu_bar.assert_called_once_with(menu_bar)

    def test_dispatch_build_context_menu(self):
        pm, mw, plugin = self._make_pm_with_mock_plugin()
        menu = MagicMock()
        pm.dispatch_build_context_menu(menu, mw.viewer)
        plugin.on_build_context_menu.assert_called_once_with(menu, mw.viewer)

    def test_dispatch_error_does_not_propagate(self):
        """If a plugin hook raises, dispatch should not propagate the error."""
        pm, mw, plugin = self._make_pm_with_mock_plugin()
        plugin.on_image_loaded.side_effect = ValueError("plugin error")
        # Should not raise
        pm.dispatch_image_loaded("/test.png", mw.viewer)


# ===========================
# pip_installer: check_missing_packages
# ===========================

class TestCheckMissingPackages:
    def test_all_present(self):
        from Imervue.plugin.pip_installer import check_missing_packages
        # os and sys are always available
        result = check_missing_packages([("os", "os"), ("sys", "sys")])
        assert result == []

    def test_missing_package(self):
        from Imervue.plugin.pip_installer import check_missing_packages
        result = check_missing_packages([
            ("os", "os"),
            ("nonexistent_package_xyz_123", "nonexistent-package-xyz-123"),
        ])
        assert len(result) == 1
        assert result[0] == ("nonexistent_package_xyz_123", "nonexistent-package-xyz-123")

    def test_empty_list(self):
        from Imervue.plugin.pip_installer import check_missing_packages
        assert check_missing_packages([]) == []


# ===========================
# pip_installer: _verify_python
# ===========================

class TestVerifyPython:
    def test_verify_current_python(self):
        from Imervue.plugin.pip_installer import _verify_python
        # Current interpreter should have pip
        assert _verify_python(sys.executable) is True

    def test_verify_nonexistent_path(self):
        from Imervue.plugin.pip_installer import _verify_python
        assert _verify_python("/no/such/python") is False

    def test_verify_invalid_executable(self, tmp_path):
        from Imervue.plugin.pip_installer import _verify_python
        fake = tmp_path / "not_python.exe"
        fake.write_text("not a real executable")
        assert _verify_python(str(fake)) is False


# ===========================
# pip_installer: _find_python (non-frozen)
# ===========================

class TestFindPython:
    def test_find_python_non_frozen(self):
        """In a non-frozen environment, _find_python should return sys.executable."""
        from Imervue.plugin.pip_installer import _find_python
        result = _find_python()
        assert result == sys.executable


# ===========================
# pip_installer: _is_frozen
# ===========================

class TestIsFrozen:
    def test_not_frozen(self):
        from Imervue.plugin.pip_installer import _is_frozen
        assert _is_frozen() is False

    def test_frozen_with_attr(self):
        from Imervue.plugin.pip_installer import _is_frozen
        with patch.object(sys, "frozen", True, create=True):
            assert _is_frozen() is True

    def test_frozen_nuitka_compiled(self):
        """Nuitka injects __compiled__ into every compiled module's globals.

        Simulate that by poking the attribute onto app_paths' module dict
        and asserting ``is_frozen()`` reports True — otherwise the frozen
        ``lib/site-packages`` path never gets added to ``sys.path`` under
        Nuitka builds and plugin pip-installs silently fail.
        """
        from Imervue.system import app_paths
        sentinel = object()
        had_attr = "__compiled__" in app_paths.__dict__
        original = app_paths.__dict__.get("__compiled__")
        app_paths.__dict__["__compiled__"] = sentinel
        try:
            assert app_paths.is_frozen() is True
        finally:
            if had_attr:
                app_paths.__dict__["__compiled__"] = original
            else:
                app_paths.__dict__.pop("__compiled__", None)

    def test_ensure_frozen_site_packages_noop_when_not_frozen(self, tmp_path):
        """In dev mode the helper must be a no-op — must not mess with sys.path."""
        from Imervue.system.app_paths import ensure_frozen_site_packages_on_path
        before = list(sys.path)
        ensure_frozen_site_packages_on_path()
        assert sys.path == before


# ===========================
# pip_installer: _subprocess_kwargs
# ===========================

class TestSubprocessKwargs:
    def test_returns_dict(self):
        from Imervue.plugin.pip_installer import _subprocess_kwargs
        kw = _subprocess_kwargs()
        assert isinstance(kw, dict)
        assert "encoding" in kw
        assert kw["encoding"] == "utf-8"

    def test_windows_creationflags(self):
        import subprocess
        from Imervue.plugin.pip_installer import _subprocess_kwargs
        if sys.platform == "win32":
            kw = _subprocess_kwargs()
            assert "creationflags" in kw
            assert kw["creationflags"] == subprocess.CREATE_NO_WINDOW


# ===========================
# pip_installer: _embedded_python_dir
# ===========================

class TestEmbeddedPythonDir:
    def test_returns_path(self):
        from Imervue.plugin.pip_installer import _embedded_python_dir
        result = _embedded_python_dir()
        assert isinstance(result, Path)
        assert result.name == "python_embedded"


# ===========================
# pip_installer: ensure_dependencies
# ===========================

class TestEnsureDependencies:
    def test_check_deps_worker_all_present(self):
        """_CheckDepsWorker returns empty list when all packages are importable."""
        from Imervue.plugin.pip_installer import _CheckDepsWorker
        worker = _CheckDepsWorker([("os", "os"), ("sys", "sys")])
        results = []
        worker.result_ready.connect(results.append)
        worker.run()  # run directly (not start) for synchronous test
        assert results == [[]]

    def test_check_deps_worker_missing(self):
        """_CheckDepsWorker returns missing packages."""
        from Imervue.plugin.pip_installer import _CheckDepsWorker
        worker = _CheckDepsWorker([("os", "os"), ("nonexistent_xyz_pkg", "nonexistent-xyz")])
        results = []
        worker.result_ready.connect(results.append)
        worker.run()
        assert len(results) == 1
        assert results[0] == [("nonexistent_xyz_pkg", "nonexistent-xyz")]

    def test_import_worker(self):
        """_ImportWorker imports modules without blocking."""
        from Imervue.plugin.pip_installer import _ImportWorker
        worker = _ImportWorker(["os", "sys"])
        done = []
        worker.result_ready.connect(lambda: done.append(True))
        worker.run()
        assert done == [True]


# ===========================
# pip_installer: register_translations
# ===========================

class TestPipInstallerTranslations:
    def test_translations_dict_has_all_languages(self):
        from Imervue.plugin.pip_installer import _TRANSLATIONS
        expected = {"English", "Traditional_Chinese", "Chinese", "Japanese", "Korean"}
        assert set(_TRANSLATIONS.keys()) == expected

    def test_all_languages_have_same_keys(self):
        from Imervue.plugin.pip_installer import _TRANSLATIONS
        en_keys = set(_TRANSLATIONS["English"].keys())
        for lang, d in _TRANSLATIONS.items():
            assert set(d.keys()) == en_keys, f"{lang} keys mismatch"

    def test_register_translations(self):
        from Imervue.plugin.pip_installer import register_translations
        # Should not raise
        register_translations()


# ===========================
# plugin_downloader: _get_plugin_dir
# ===========================

class TestPluginDownloaderHelpers:
    def test_get_plugin_dir(self):
        from Imervue.plugin.plugin_downloader import _get_plugin_dir
        result = _get_plugin_dir()
        assert isinstance(result, Path)
        assert result.name == "plugins"

    def test_get_installed_plugins_empty(self, tmp_path):
        """_get_installed_plugins returns empty set when dir doesn't exist."""
        from Imervue.plugin.plugin_downloader import PluginDownloaderDialog
        with patch("Imervue.plugin.plugin_downloader._get_plugin_dir", return_value=tmp_path / "nope"):
            result = PluginDownloaderDialog._get_installed_plugins()
            assert result == set()

    def test_get_installed_plugins_with_plugins(self, tmp_path):
        """_get_installed_plugins detects dirs with __init__.py."""
        from Imervue.plugin.plugin_downloader import PluginDownloaderDialog
        (tmp_path / "good_plugin").mkdir()
        (tmp_path / "good_plugin" / "__init__.py").write_text("")
        (tmp_path / "bad_dir").mkdir()  # no __init__.py
        (tmp_path / "file.txt").write_text("not a dir")

        with patch("Imervue.plugin.plugin_downloader._get_plugin_dir", return_value=tmp_path):
            result = PluginDownloaderDialog._get_installed_plugins()
            assert result == {"good_plugin"}


# ===========================
# plugin_downloader: FetchPluginListWorker
# ===========================

class TestFetchPluginListWorker:
    def test_worker_emits_error_on_network_failure(self):
        from Imervue.plugin.plugin_downloader import FetchPluginListWorker

        worker = FetchPluginListWorker()
        errors = []
        worker.error.connect(errors.append)

        with patch("Imervue.plugin.plugin_downloader._github_get", side_effect=Exception("network error")):
            worker.run()

        assert len(errors) == 1
        assert "network error" in errors[0]

    def test_worker_emits_results_on_success(self):
        from Imervue.plugin.plugin_downloader import FetchPluginListWorker

        mock_root = [
            {"type": "dir", "name": "filters", "url": "https://api/filters"},
        ]
        mock_cat = [
            {"type": "dir", "name": "blur_plugin", "url": "https://api/blur"},
        ]
        mock_files = [
            {"type": "file", "name": "__init__.py", "download_url": "https://raw/init", "path": "filters/blur_plugin/__init__.py"},
            {"type": "file", "name": "blur.py", "download_url": "https://raw/blur", "path": "filters/blur_plugin/blur.py"},
        ]

        def fake_get(url):
            if "contents" in url:
                return mock_root
            elif "filters" in url and "blur" not in url:
                return mock_cat
            else:
                return mock_files

        worker = FetchPluginListWorker()
        results = []
        worker.result_ready.connect(results.append)

        with patch("Imervue.plugin.plugin_downloader._github_get", side_effect=fake_get):
            worker.run()

        assert len(results) == 1
        data = results[0]
        assert len(data) == 1
        cat, name, files = data[0]
        assert cat == "filters"
        assert name == "blur_plugin"
        assert len(files) == 2


# ===========================
# plugin_downloader: DownloadPluginWorker
# ===========================

class TestDownloadPluginWorker:
    def test_download_creates_files(self, tmp_path):
        from Imervue.plugin.plugin_downloader import DownloadPluginWorker

        file_infos = [
            {"name": "__init__.py", "download_url": "https://example.com/init"},
            {"name": "main.py", "download_url": "https://example.com/main"},
        ]

        worker = DownloadPluginWorker("test_plugin", file_infos)
        finished_names = []
        worker.result_ready.connect(finished_names.append)
        progress_log = []
        worker.progress.connect(lambda c, t: progress_log.append((c, t)))

        def fake_urlopen(req, timeout=30):
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=b"# code")))
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        with patch("Imervue.plugin.plugin_downloader._get_plugin_dir", return_value=tmp_path):
            with patch("Imervue.plugin.plugin_downloader.urllib.request.urlopen", fake_urlopen):
                worker.run()

        assert finished_names == ["test_plugin"]
        assert (tmp_path / "test_plugin" / "__init__.py").exists()
        assert (tmp_path / "test_plugin" / "main.py").exists()
        assert progress_log == [(1, 2), (2, 2)]

    def test_download_emits_error_on_failure(self, tmp_path):
        from Imervue.plugin.plugin_downloader import DownloadPluginWorker

        file_infos = [
            {"name": "__init__.py", "download_url": "https://example.com/init"},
        ]

        worker = DownloadPluginWorker("fail_plugin", file_infos)
        errors = []
        worker.error.connect(errors.append)

        with patch("Imervue.plugin.plugin_downloader._get_plugin_dir", return_value=tmp_path):
            with patch("Imervue.plugin.plugin_downloader.urllib.request.urlopen", side_effect=Exception("timeout")):
                worker.run()

        assert len(errors) == 1
        assert "timeout" in errors[0]


# ===========================
# Multiple plugin directories
# ===========================

class TestMultiplePluginDirs:
    def test_load_from_multiple_dirs(self, tmp_path):
        from Imervue.plugin.plugin_manager import PluginManager

        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"

        code1 = textwrap.dedent("""\
            from Imervue.plugin.plugin_base import ImervuePlugin
            class P1(ImervuePlugin):
                plugin_name = "Plugin1"
            plugin_class = P1
        """)
        code2 = textwrap.dedent("""\
            from Imervue.plugin.plugin_base import ImervuePlugin
            class P2(ImervuePlugin):
                plugin_name = "Plugin2"
            plugin_class = P2
        """)

        _create_plugin_package(dir1, "p1", code1)
        _create_plugin_package(dir2, "p2", code2)

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([dir1, dir2])

        names = {p.plugin_name for p in pm.plugins}
        assert names == {"Plugin1", "Plugin2"}


# ===========================
# Real shipped plugins (smoke test)
# ===========================

class TestShippedPlugins:
    """Smoke tests that verify the actual plugins in <repo>/plugins/ discover
    and load via PluginManager.

    These guard against regressions in the plugin system itself — e.g. an
    `is_frozen()` signature change or an `app_paths` helper rename that would
    silently break plugin imports without any fake-plugin test catching it.
    """

    def _real_plugins_dir(self) -> Path:
        # tests/test_plugin.py → repo root → plugins/
        return Path(__file__).resolve().parent.parent / "plugins"

    def test_shipped_plugin_dir_exists(self):
        d = self._real_plugins_dir()
        assert d.is_dir(), f"plugins dir missing at {d}"

    def test_shipped_plugins_load(self):
        plugins_dir = self._real_plugins_dir()
        if not plugins_dir.is_dir():
            pytest.skip("no plugins dir")

        from Imervue.plugin.plugin_manager import PluginManager

        mw = _make_mock_main_window()
        pm = PluginManager(mw)
        pm.discover_and_load([plugins_dir])

        # Every sub-directory with __init__.py should have produced a plugin.
        expected_plugin_dirs = {
            p.name for p in plugins_dir.iterdir()
            if p.is_dir() and (p / "__init__.py").exists()
        }
        assert len(pm.plugins) == len(expected_plugin_dirs), (
            f"expected {len(expected_plugin_dirs)} plugins "
            f"({expected_plugin_dirs}), got {len(pm.plugins)} "
            f"({[p.plugin_name for p in pm.plugins]})"
        )

        # Each loaded plugin must satisfy the ImervuePlugin contract.
        from Imervue.plugin.plugin_base import ImervuePlugin
        for plugin in pm.plugins:
            assert isinstance(plugin, ImervuePlugin)
            assert plugin.plugin_name and plugin.plugin_name != "Unnamed Plugin"
            assert plugin.plugin_version
            # Each shipped plugin should also return a dict from get_translations
            # (even if empty) — a TypeError here means the plugin broke the API.
            tr = plugin.get_translations()
            assert isinstance(tr, dict)

        pm.unload_all()
        assert pm.plugins == []
