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
            {"name": "external editor", "executable": "/usr/bin/gimp"})
        assert e is not None
        assert e.name == "external editor"
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
    @pytest.mark.parametrize("platform", ["win32", "linux"])
    @pytest.mark.parametrize("arguments", [
        "", "   ", "--flag", '--title "two words"',
        "--open={path} {path}", '--title "{path}"',
        "--flag ; & | > $(echo)",
    ])
    def test_argument_contract(self, editors_mod, monkeypatch, platform, arguments):
        import shlex

        monkeypatch.setattr(editors_mod.sys, "platform", platform)
        image = "/my pics/a b.jpg"
        entry = editors_mod.EditorEntry("E", "/bin/e", arguments)
        tokens = shlex.split(arguments.strip(), posix=platform != "win32")
        expected = [token.replace("{path}", image) for token in tokens]
        if "{path}" not in arguments:
            expected.append(image)
        assert editors_mod._build_argv(entry, image) == ["/bin/e", *expected]

    def test_unclosed_quote_raises(self, editors_mod):
        entry = editors_mod.EditorEntry("E", "/bin/e", '"unfinished')
        with pytest.raises(ValueError, match="No closing quotation"):
            editors_mod._build_argv(entry, "/img.jpg")

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
    @pytest.mark.parametrize("raw", [None, {}, "invalid", [], [None, 1]])
    def test_empty_or_invalid_settings(self, editors_mod, monkeypatch, raw):
        monkeypatch.setitem(editors_mod.user_setting_dict, "external_editors", raw)
        assert editors_mod.load_editors() == []

    def test_save_preserves_fields_and_schedules_persistence(self, editors_mod, monkeypatch):
        saved = []
        monkeypatch.setattr(editors_mod, "schedule_save", lambda: saved.append(True))
        monkeypatch.setattr(editors_mod, "user_setting_dict", {})
        entry = editors_mod.EditorEntry("Editor", "/bin/editor", "--open={path}")
        editors_mod.save_editors([entry])
        assert editors_mod.user_setting_dict["external_editors"] == [entry.to_dict()]
        assert editors_mod.load_editors() == [entry]
        assert saved == [True]

    def test_save_then_load(self, editors_mod):
        entries = [
            editors_mod.EditorEntry("Editor A", "/usr/bin/editor-a"),
            editors_mod.EditorEntry("Editor B", "/usr/bin/editor-b", "--canvas-only"),
        ]
        editors_mod.save_editors(entries)
        loaded = editors_mod.load_editors()
        assert len(loaded) == 2
        assert loaded[0].name == "Editor A"
        assert loaded[1].arguments == "--canvas-only"

    def test_load_drops_invalid_entries(self, editors_mod):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        user_setting_dict["external_editors"] = [
            {"name": "external editor", "executable": "/usr/bin/gimp"},
            {"name": "", "executable": "/bad"},  # invalid
            "garbage",
            {"nope": True},
        ]
        loaded = editors_mod.load_editors()
        assert len(loaded) == 1 and loaded[0].name == "external editor"


class TestLaunchGuards:
    def test_missing_file_returns_false(self, editors_mod, tmp_path):
        e = editors_mod.EditorEntry("E", sys.executable)
        assert editors_mod.launch_editor(e, str(tmp_path / "nope.jpg")) is False

    def test_missing_executable_returns_false(self, editors_mod, tmp_path):
        image = tmp_path / "a.jpg"
        image.write_bytes(b"")
        e = editors_mod.EditorEntry("E", str(tmp_path / "not-an-exe"))
        assert editors_mod.launch_editor(e, str(image)) is False

    def test_launch_preserves_configured_program_and_arguments(
        self, editors_mod, monkeypatch, tmp_path,
    ):
        from unittest.mock import Mock

        monkeypatch.chdir(tmp_path)
        image = tmp_path / "image ; &.jpg"
        image.touch()
        executable = tmp_path / "my editor.exe"
        executable.touch()
        process = Mock()
        launch = Mock(return_value=process)
        monkeypatch.setattr(editors_mod.subprocess, "Popen", launch)
        entry = editors_mod.EditorEntry("Editor", executable.name, "--open={path} ; &")

        assert editors_mod.launch_editor(entry, str(image)) is True
        launch.assert_called_once_with(
            [executable.name, f"--open={image}", ";", "&"], shell=False,
        )
        process.wait.assert_not_called()
        process.communicate.assert_not_called()

    def test_launch_error_is_logged_without_retry(
        self, editors_mod, monkeypatch, tmp_path, caplog,
    ):
        from unittest.mock import Mock

        image = tmp_path / "image.jpg"
        image.touch()
        executable = tmp_path / "editor.exe"
        executable.touch()
        launch = Mock(side_effect=OSError("elevation required"))
        monkeypatch.setattr(editors_mod.subprocess, "Popen", launch)
        entry = editors_mod.EditorEntry("Editor", str(executable))
        assert editors_mod.launch_editor(entry, str(image)) is False
        launch.assert_called_once_with([str(executable), str(image)], shell=False)
        assert "Failed to launch Editor: elevation required" in caplog.text
