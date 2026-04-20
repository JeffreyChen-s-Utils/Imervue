"""Tests for frozen-safe path resolution helpers."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from Imervue.system import app_paths


@pytest.fixture(autouse=True)
def _clear_cache():
    """``app_dir`` is lru_cached — clear between tests that monkeypatch sys."""
    app_paths.app_dir.cache_clear()
    yield
    app_paths.app_dir.cache_clear()


class TestIsFrozen:
    def test_false_in_development(self):
        assert app_paths.is_frozen() is False

    def test_true_when_sys_frozen(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        assert app_paths.is_frozen() is True

    def test_true_when_nuitka_compiled(self, monkeypatch):
        monkeypatch.setitem(app_paths.__dict__, "__compiled__", object())
        assert app_paths.is_frozen() is True


class TestAppDir:
    def test_dev_returns_project_root(self):
        result = app_paths.app_dir()
        assert (result / "Imervue").is_dir()

    def test_frozen_returns_executable_dir(self, monkeypatch, tmp_path):
        fake_exe = tmp_path / "Imervue.exe"
        fake_exe.touch()
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(fake_exe))
        assert app_paths.app_dir() == tmp_path

    def test_is_cached(self):
        a, b = app_paths.app_dir(), app_paths.app_dir()
        assert a is b


class TestDerivedPaths:
    def test_plugins_dir_is_under_app_dir(self):
        assert app_paths.plugins_dir().parent == app_paths.app_dir()
        assert app_paths.plugins_dir().name == "plugins"

    def test_icon_path_uses_exe_subfolder(self):
        p = app_paths.icon_path()
        assert p.name == "Imervue.ico"
        assert p.parent.name == "exe"

    def test_user_settings_path_is_json(self):
        p = app_paths.user_settings_path()
        assert p.suffix == ".json"
        assert p.parent == app_paths.app_dir()

    def test_embedded_python_and_site_packages(self):
        assert app_paths.embedded_python_dir().name == "python_embedded"
        sp = app_paths.frozen_site_packages()
        assert sp.parts[-2:] == ("lib", "site-packages")


class TestEnsureSitePackagesOnPath:
    def test_noop_when_not_frozen(self, monkeypatch):
        before = list(sys.path)
        app_paths.ensure_frozen_site_packages_on_path()
        assert sys.path == before

    def test_inserts_existing_dir_when_frozen(self, monkeypatch, tmp_path):
        fake_exe = tmp_path / "Imervue.exe"
        fake_exe.touch()
        lib_dir = tmp_path / "lib" / "site-packages"
        lib_dir.mkdir(parents=True)

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(fake_exe))
        path_copy = list(sys.path)
        monkeypatch.setattr(sys, "path", path_copy)

        app_paths.ensure_frozen_site_packages_on_path()
        assert str(lib_dir) == sys.path[0]

    def test_idempotent(self, monkeypatch, tmp_path):
        fake_exe = tmp_path / "Imervue.exe"
        fake_exe.touch()
        lib_dir = tmp_path / "lib" / "site-packages"
        lib_dir.mkdir(parents=True)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(fake_exe))
        path_copy = list(sys.path)
        monkeypatch.setattr(sys, "path", path_copy)

        app_paths.ensure_frozen_site_packages_on_path()
        app_paths.ensure_frozen_site_packages_on_path()
        assert sys.path.count(str(lib_dir)) == 1

    def test_missing_dir_is_not_added(self, monkeypatch, tmp_path):
        fake_exe = tmp_path / "Imervue.exe"
        fake_exe.touch()
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(fake_exe))
        path_copy = list(sys.path)
        monkeypatch.setattr(sys, "path", path_copy)

        app_paths.ensure_frozen_site_packages_on_path()
        assert not any(
            Path(p) == tmp_path / "lib" / "site-packages" for p in sys.path
        )
