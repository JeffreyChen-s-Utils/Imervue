"""Tests for the external editor config model + argv builder."""
from __future__ import annotations

import sys

import pytest


@pytest.fixture
def editors_mod():
    from Imervue.external import editors as m
    return m


class TestEditorEntry:
    def test_from_dict_valid(self, editors_mod):
        e = editors_mod.EditorEntry.from_dict(
            {"name": "GIMP", "executable": "/usr/bin/gimp"})
        assert e is not None
        assert e.name == "GIMP"
        assert e.executable == "/usr/bin/gimp"
        assert e.arguments == ""

    def test_from_dict_missing_fields(self, editors_mod):
        assert editors_mod.EditorEntry.from_dict({}) is None
        assert editors_mod.EditorEntry.from_dict({"name": ""}) is None
        assert editors_mod.EditorEntry.from_dict({"name": "x"}) is None

    def test_from_dict_strips_whitespace(self, editors_mod):
        e = editors_mod.EditorEntry.from_dict(
            {"name": "  Paint  ", "executable": " paint.exe "})
        assert e.name == "Paint"
        assert e.executable == "paint.exe"

    def test_from_dict_rejects_non_dict(self, editors_mod):
        assert editors_mod.EditorEntry.from_dict("x") is None
        assert editors_mod.EditorEntry.from_dict(42) is None


class TestBuildArgv:
    def test_no_extra_args_appends_path(self, editors_mod):
        e = editors_mod.EditorEntry(name="E", executable="/bin/e")
        argv = editors_mod._build_argv(e, "/img.jpg")
        assert argv == ["/bin/e", "/img.jpg"]

    def test_placeholder_substitution(self, editors_mod):
        e = editors_mod.EditorEntry(
            name="E", executable="/bin/e", arguments="--edit {path}")
        argv = editors_mod._build_argv(e, "/img.jpg")
        assert argv == ["/bin/e", "--edit", "/img.jpg"]

    def test_no_placeholder_appends_path_last(self, editors_mod):
        e = editors_mod.EditorEntry(
            name="E", executable="/bin/e", arguments="--flag")
        argv = editors_mod._build_argv(e, "/img.jpg")
        assert argv == ["/bin/e", "--flag", "/img.jpg"]

    def test_path_with_spaces_preserved(self, editors_mod):
        e = editors_mod.EditorEntry(
            name="E", executable="/bin/e", arguments="--open {path}")
        argv = editors_mod._build_argv(e, "/my pics/a b.jpg")
        assert argv == ["/bin/e", "--open", "/my pics/a b.jpg"]


class TestLoadSaveRoundTrip:
    def test_save_then_load(self, editors_mod):
        entries = [
            editors_mod.EditorEntry("GIMP", "/usr/bin/gimp"),
            editors_mod.EditorEntry("Krita", "/usr/bin/krita", "--canvas-only"),
        ]
        editors_mod.save_editors(entries)
        loaded = editors_mod.load_editors()
        assert len(loaded) == 2
        assert loaded[0].name == "GIMP"
        assert loaded[1].arguments == "--canvas-only"

    def test_load_drops_invalid_entries(self, editors_mod):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        user_setting_dict["external_editors"] = [
            {"name": "GIMP", "executable": "/usr/bin/gimp"},
            {"name": "", "executable": "/bad"},  # invalid
            "garbage",
            {"nope": True},
        ]
        loaded = editors_mod.load_editors()
        assert len(loaded) == 1 and loaded[0].name == "GIMP"


class TestLaunchGuards:
    def test_missing_file_returns_false(self, editors_mod, tmp_path):
        e = editors_mod.EditorEntry("E", sys.executable)
        assert editors_mod.launch_editor(e, str(tmp_path / "nope.jpg")) is False

    def test_missing_executable_returns_false(self, editors_mod, tmp_path):
        image = tmp_path / "a.jpg"
        image.write_bytes(b"")
        e = editors_mod.EditorEntry("E", str(tmp_path / "not-an-exe"))
        assert editors_mod.launch_editor(e, str(image)) is False
