"""Tests for ``system/wallpaper``: the commands it runs and how it reports failure."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from Imervue.system import wallpaper


def test_macos_passes_the_path_as_an_argument_not_as_script_text(tmp_path):
    hostile = str(tmp_path / 'x" & do shell script "rm -rf ~" & ".png')
    (command,) = wallpaper.wallpaper_commands(hostile, "darwin")
    assert command[0] == "osascript"
    assert command[-1] == os.path.abspath(hostile)
    script = [arg for flag, arg in zip(command[1:-1:2], command[2:-1:2], strict=True) if flag == "-e"]
    assert len(script) == 3
    assert all("rm -rf" not in line for line in script)
    assert "item 1 of argv" in script[1]


def test_gnome_sets_both_light_and_dark_wallpapers_as_file_uris(tmp_path):
    path = tmp_path / "my photo #1.png"
    commands = wallpaper.wallpaper_commands(str(path), "linux")
    uri = Path(os.path.abspath(path)).as_uri()
    assert commands == [
        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
    ]
    assert " " not in uri and "#" not in uri   # percent-encoded, not a broken URI


def test_relative_path_is_made_absolute_so_it_cannot_look_like_an_option():
    (command,) = wallpaper.wallpaper_commands("-rf.png", "darwin")
    assert command[-1] == os.path.abspath("-rf.png")
    assert not command[-1].startswith("-")


@pytest.fixture
def popen_log(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: calls.append(cmd))
    return calls


def test_non_windows_runs_every_command(monkeypatch, popen_log):
    monkeypatch.setattr(sys, "platform", "linux")
    wallpaper.set_desktop_wallpaper("/pics/a.png")
    assert [cmd[3] for cmd in popen_log] == ["picture-uri", "picture-uri-dark"]


def test_missing_helper_is_logged_and_stops(monkeypatch, caplog):
    calls: list = []

    def missing(cmd):
        calls.append(cmd)
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "Popen", missing)
    with caplog.at_level("DEBUG", logger="Imervue"):
        wallpaper.set_desktop_wallpaper("/pics/a.png")
    assert len(calls) == 1
    (record,) = caplog.records
    assert "gsettings" in record.getMessage()
    assert record.exc_info[0] is FileNotFoundError


def test_unexpected_popen_error_propagates(monkeypatch):
    def broken(_cmd):
        raise TypeError("bad argv")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "Popen", broken)
    with pytest.raises(TypeError):
        wallpaper.set_desktop_wallpaper("/pics/a.png")


def _fake_windll(monkeypatch, result):
    import ctypes
    calls: list[tuple] = []

    def spi(*args):
        calls.append(args)
        return result

    monkeypatch.setattr(ctypes, "windll",
                        SimpleNamespace(user32=SimpleNamespace(SystemParametersInfoW=spi)),
                        raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    return calls


def test_windows_calls_system_parameters_info(monkeypatch, caplog, popen_log):
    calls = _fake_windll(monkeypatch, 1)
    with caplog.at_level("DEBUG", logger="Imervue"):
        wallpaper.set_desktop_wallpaper("a.png")
    assert calls == [(0x0014, 0, os.path.abspath("a.png"), 0x03)]
    assert popen_log == []
    assert caplog.records == []


def test_windows_refusal_is_logged(monkeypatch, caplog):
    _fake_windll(monkeypatch, 0)
    with caplog.at_level("DEBUG", logger="Imervue"):
        wallpaper.set_desktop_wallpaper("a.png")
    (record,) = caplog.records
    assert "refused" in record.getMessage()
