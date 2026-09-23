"""Tests for ``reveal_in_file_manager``: the command each platform runs."""
from __future__ import annotations

import os
import sys

import pytest

from Imervue.system import file_manager as fm


@pytest.fixture
def popen(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(fm.subprocess, "Popen", lambda args, **_kw: calls.append(args))
    return calls


@pytest.mark.parametrize("select", [True, False])
def test_windows_selects_a_file_or_opens_the_folder(monkeypatch, popen, tmp_path, select):
    monkeypatch.setattr(sys, "platform", "win32")
    target = tmp_path / "a.png"
    target.write_bytes(b"")
    fm.reveal_in_file_manager(str(target), select=select)
    expected = ["explorer", "/select,", os.path.normpath(str(target))] if select else         ["explorer", os.path.normpath(str(target))]
    assert popen == [expected]


def test_windows_opens_a_folder_even_when_selecting(monkeypatch, popen, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    fm.reveal_in_file_manager(str(tmp_path))
    assert popen == [["explorer", os.path.normpath(str(tmp_path))]]


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


def test_right_click_reveal_logs_a_failure(monkeypatch, caplog, tmp_path):
    from Imervue.menu import right_click_menu

    def missing(*_a, **_k):
        raise FileNotFoundError("explorer")

    monkeypatch.setattr(fm.subprocess, "Popen", missing)
    with caplog.at_level("DEBUG", logger="Imervue"):
        right_click_menu._open_in_explorer(str(tmp_path / "a.png"))  # noqa: SLF001
    assert [r.levelname for r in caplog.records if "reveal" in r.getMessage()] == ["WARNING"]


def test_plugin_folder_is_opened_not_selected(monkeypatch, tmp_path):
    from Imervue.menu import plugin_menu
    calls = []
    monkeypatch.setattr(plugin_menu, "_get_plugin_dir", lambda: tmp_path / "plugins")
    monkeypatch.setattr(plugin_menu, "reveal_in_file_manager",
                        lambda path, *, select=True: calls.append((path, select)))
    plugin_menu._open_plugin_folder()  # noqa: SLF001
    assert calls == [(str(tmp_path / "plugins"), False)]
    assert (tmp_path / "plugins").is_dir()
