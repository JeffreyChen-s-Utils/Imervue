"""Tests for ``reveal_in_file_manager`` (the command each platform runs) and ``reveal_or_warn``."""
from __future__ import annotations

import os
import sys

import pytest

from Imervue.system import file_manager as fm


@pytest.fixture
def popen(monkeypatch):
    calls: list = []
    monkeypatch.setattr(fm.subprocess, "Popen", lambda args, **_kw: calls.append(args))
    return calls


@pytest.mark.parametrize("select", [True, False])
def test_windows_selects_a_file_or_opens_the_folder(monkeypatch, popen, tmp_path, select):
    monkeypatch.setattr(sys, "platform", "win32")
    target = tmp_path / "a.png"
    target.write_bytes(b"")
    fm.reveal_in_file_manager(str(target), select=select)
    path = os.path.normpath(str(target))
    assert popen == [f'explorer /select,"{path}"' if select else f'explorer "{path}"']


def test_windows_opens_a_folder_even_when_selecting(monkeypatch, popen, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    fm.reveal_in_file_manager(str(tmp_path))
    assert popen == [f'explorer "{os.path.normpath(str(tmp_path))}"']


@pytest.mark.parametrize("name", ["trip,day1", "a=b", "with space"])
def test_windows_quotes_a_path_explorer_would_split(monkeypatch, popen, tmp_path, name):
    """Explorer splits at commas and '=': an unquoted C:/trip,day1/a.jpg opened the wrong folder."""
    monkeypatch.setattr(sys, "platform", "win32")
    folder = tmp_path / name
    folder.mkdir()
    target = folder / "a.jpg"
    target.write_bytes(b"")
    fm.reveal_in_file_manager(str(target))
    assert popen == [f'explorer /select,"{os.path.normpath(str(target))}"']


def test_explorer_command_quotes_the_path():
    file_path, folder = os.path.normpath("C:/trip,day1/a.jpg"), os.path.normpath("C:/trip,day1")
    assert fm.explorer_command("C:/trip,day1/a.jpg", select=True) == f'explorer /select,"{file_path}"'
    assert fm.explorer_command("C:/trip,day1", select=False) == f'explorer "{folder}"'


def test_linux_opens_the_parent_folder_of_a_file(monkeypatch, popen, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    target = tmp_path / "a.png"
    target.write_bytes(b"")
    fm.reveal_in_file_manager(str(target))
    fm.reveal_in_file_manager(str(tmp_path))
    assert popen == [["xdg-open", str(tmp_path)], ["xdg-open", str(tmp_path)]]


@pytest.mark.parametrize("select, expected", [(True, ["open", "-R"]), (False, ["open"])])
def test_macos_reveal_or_open(monkeypatch, popen, tmp_path, select, expected):
    """``open "" <path>`` used to be run for select=False; the empty argument made it fail."""
    monkeypatch.setattr(sys, "platform", "darwin")
    fm.reveal_in_file_manager(str(tmp_path), select=select)
    assert popen == [[*expected, str(tmp_path)]]


@pytest.mark.parametrize("error", [FileNotFoundError("explorer"), ValueError("embedded null character")])
def test_reveal_or_warn_logs_a_file_manager_that_wont_start(monkeypatch, caplog, tmp_path, error):
    def fail(*_a, **_k):
        raise error

    monkeypatch.setattr(fm.subprocess, "Popen", fail)
    with caplog.at_level("DEBUG", logger="Imervue"):
        fm.reveal_or_warn(str(tmp_path / "a.png"))
    (record,) = [r for r in caplog.records if "reveal" in r.getMessage()]
    assert record.levelname == "WARNING" and record.exc_info[1] is error


def test_reveal_or_warn_lets_a_bug_through(monkeypatch, tmp_path):
    def bug(*_a, **_k):
        raise RuntimeError("bug")

    monkeypatch.setattr(fm.subprocess, "Popen", bug)
    with pytest.raises(RuntimeError):
        fm.reveal_or_warn(str(tmp_path))


def test_reveal_or_warn_passes_select_through(monkeypatch, popen, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    fm.reveal_or_warn(str(tmp_path), select=False)
    assert popen == [["open", str(tmp_path)]]


def test_plugin_folder_is_opened_not_selected(monkeypatch, tmp_path):
    from Imervue.menu import plugin_menu
    calls = []
    monkeypatch.setattr(plugin_menu, "_get_plugin_dir", lambda: tmp_path / "plugins")
    monkeypatch.setattr(plugin_menu, "reveal_or_warn",
                        lambda path, *, select=True: calls.append((path, select)))
    plugin_menu._open_plugin_folder()  # noqa: SLF001
    assert calls == [(str(tmp_path / "plugins"), False)]
    assert (tmp_path / "plugins").is_dir()


def test_a_plugin_folder_the_file_manager_cant_open_is_logged(monkeypatch, caplog, tmp_path):
    from Imervue.menu import plugin_menu

    def missing(*_a, **_k):
        raise FileNotFoundError("explorer")

    monkeypatch.setattr(plugin_menu, "_get_plugin_dir", lambda: tmp_path / "plugins")
    monkeypatch.setattr(fm.subprocess, "Popen", missing)
    with caplog.at_level("DEBUG", logger="Imervue"):
        plugin_menu._open_plugin_folder()  # noqa: SLF001
    assert [r.levelname for r in caplog.records if "reveal" in r.getMessage()] == ["WARNING"]
