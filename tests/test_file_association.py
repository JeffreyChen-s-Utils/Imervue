"""Tests for Windows file-association helpers.

The module's registry writes are Windows-only; on other platforms the public
entry points short-circuit, so we test cross-platform behaviour plus the
pure-python command builder and extension list.
"""
from __future__ import annotations

import sys

import pytest

from Imervue.system import file_association as fa


class TestAssocExtensions:
    def test_covers_core_raster_formats(self):
        for ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"):
            assert ext in fa.ASSOC_EXTENSIONS

    def test_covers_raw_formats(self):
        for ext in (".cr2", ".nef", ".arw", ".dng", ".raf", ".orf"):
            assert ext in fa.ASSOC_EXTENSIONS

    def test_all_extensions_start_with_dot(self):
        assert all(e.startswith(".") for e in fa.ASSOC_EXTENSIONS)

    def test_no_duplicates(self):
        assert len(fa.ASSOC_EXTENSIONS) == len(set(fa.ASSOC_EXTENSIONS))


class TestBuildCommand:
    def test_dev_uses_python_plus_main_or_module(self, monkeypatch):
        monkeypatch.setattr(fa, "is_frozen", lambda: False)
        cmd = fa._build_command()
        assert sys.executable in cmd
        assert cmd.endswith('"%1"')
        assert "Imervue" in cmd

    def test_frozen_uses_exe_directly(self, monkeypatch):
        monkeypatch.setattr(fa, "is_frozen", lambda: True)
        monkeypatch.setattr(sys, "executable", r"C:\fake\Imervue.exe")
        cmd = fa._build_command()
        assert cmd == '"C:\\fake\\Imervue.exe" "%1"'


class TestPlatformGuards:
    def test_register_non_windows_returns_error(self, monkeypatch):
        if sys.platform == "win32":
            pytest.skip("Windows-only guard test")
        ok, msg = fa.register_file_association()
        assert (ok, msg) == (False, "Only supported on Windows")

    def test_unregister_non_windows_returns_error(self, monkeypatch):
        if sys.platform == "win32":
            pytest.skip("Windows-only guard test")
        ok, msg = fa.unregister_file_association()
        assert (ok, msg) == (False, "Only supported on Windows")

    def test_register_fake_non_windows_platform(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        ok, msg = fa.register_file_association()
        assert ok is False
        assert msg == "Only supported on Windows"

    def test_unregister_fake_non_windows_platform(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        ok, msg = fa.unregister_file_association()
        assert ok is False
        assert msg == "Only supported on Windows"


class TestConstants:
    def test_app_id_is_namespaced(self):
        assert "." in fa._APP_ID
        assert fa._APP_ID.startswith("Imervue.")

    def test_shell_label_is_human_readable(self):
        assert "Imervue" in fa._SHELL_LABEL
