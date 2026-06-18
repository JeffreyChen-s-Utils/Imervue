"""Tests for cross-platform file-association helpers.

The registry / desktop-entry writes are platform-specific, but the decisions
(MIME mapping, launch command, desktop-entry text) are pure and tested here,
along with the Linux desktop-entry writer (against a temp directory) and the
platform dispatch.
"""
from __future__ import annotations

import sys

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


class TestPureHelpers:
    def test_mime_mapping_dedupes_jpeg(self):
        assert fa.mime_types_for_extensions(
            [".jpg", ".jpeg", ".png"]) == ["image/jpeg", "image/png"]

    def test_mime_mapping_ignores_unknown(self):
        assert fa.mime_types_for_extensions([".xyz"]) == []

    def test_launch_command_frozen_quotes_token(self):
        assert fa.launch_command("/a/app", None, True, '"%1"') == '"/a/app" "%1"'

    def test_launch_command_dev_with_main(self):
        assert fa.launch_command(
            "/usr/bin/python", "/p/__main__.py", False, "%f",
        ) == '"/usr/bin/python" "/p/__main__.py" %f'

    def test_launch_command_dev_module_fallback(self):
        assert fa.launch_command("/py", None, False, "%f") == '"/py" -m Imervue %f'

    def test_desktop_entry_has_exec_icon_mimetypes(self):
        content = fa.desktop_entry_content(
            "app %f", "/i.png", ["image/png", "image/jpeg"])
        assert "[Desktop Entry]" in content
        assert "Exec=app %f" in content
        assert "Icon=/i.png" in content
        assert "MimeType=image/png;image/jpeg;" in content


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
        assert fa._build_command() == '"C:\\fake\\Imervue.exe" "%1"'


class TestDispatch:
    def test_macos_is_documented_noop(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        assert fa.register_file_association() == (False, "macos_use_bundle")
        assert fa.unregister_file_association() == (False, "macos_use_bundle")

    def test_unsupported_platform(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "sunos5")
        assert fa.register_file_association() == (False, "unsupported_platform")

    def test_linux_dispatches_to_linux_register(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(fa, "_register_linux", lambda: (True, "/x/imervue.desktop"))
        assert fa.register_file_association() == (True, "/x/imervue.desktop")


class TestLinuxRegister:
    def test_register_writes_desktop_file(self, tmp_path):
        ok, path = fa._register_linux(tmp_path)
        assert ok is True
        desktop = tmp_path / "imervue.desktop"
        assert desktop.is_file()
        body = desktop.read_text(encoding="utf-8")
        assert "[Desktop Entry]" in body
        assert "MimeType=" in body
        assert path.endswith("imervue.desktop")

    def test_unregister_removes_desktop_file(self, tmp_path):
        fa._register_linux(tmp_path)
        ok, _ = fa._unregister_linux(tmp_path)
        assert ok is True
        assert not (tmp_path / "imervue.desktop").exists()

    def test_unregister_missing_is_noop(self, tmp_path):
        assert fa._unregister_linux(tmp_path) == (True, "OK")


class TestConstants:
    def test_app_id_is_namespaced(self):
        assert "." in fa._APP_ID
        assert fa._APP_ID.startswith("Imervue.")

    def test_shell_label_is_human_readable(self):
        assert "Imervue" in fa._SHELL_LABEL
