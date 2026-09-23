"""Tests for revealing a path in the OS file manager from the file tree."""
from __future__ import annotations

import os
import sys

import pytest

from Imervue.gui import file_tree_view as mod


@pytest.fixture
def popen(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(mod.subprocess, "Popen", lambda args, **_kw: calls.append(args))
    return calls


@pytest.mark.parametrize("select", [True, False])
def test_windows_selects_a_file_or_opens_the_folder(monkeypatch, popen, tmp_path, select):
    monkeypatch.setattr(sys, "platform", "win32")
    target = tmp_path / "a.png"
    target.write_bytes(b"")
    mod._reveal_in_file_manager(str(target), select)  # noqa: SLF001
    expected = ["explorer", "/select,", os.path.normpath(str(target))] if select else \
        ["explorer", os.path.normpath(str(target))]
    assert popen == [expected]


def test_linux_opens_the_parent_folder_of_a_file(monkeypatch, popen, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    target = tmp_path / "a.png"
    target.write_bytes(b"")
    mod._reveal_in_file_manager(str(target), True)  # noqa: SLF001
    mod._reveal_in_file_manager(str(tmp_path), True)  # noqa: SLF001
    assert popen == [["xdg-open", str(tmp_path)], ["xdg-open", str(tmp_path)]]


def test_missing_file_manager_is_logged_not_raised(monkeypatch, caplog, tmp_path):
    def missing(*_a, **_k):
        raise FileNotFoundError("explorer")

    monkeypatch.setattr(mod.subprocess, "Popen", missing)
    with caplog.at_level("DEBUG", logger="Imervue"):
        mod._FileTreeView._open_in_explorer(str(tmp_path))  # noqa: SLF001
    (record,) = [r for r in caplog.records if "reveal" in r.getMessage()]
    assert record.levelname == "WARNING" and record.exc_info[0] is FileNotFoundError


def test_unexpected_error_propagates(monkeypatch, tmp_path):
    def bug(*_a, **_k):
        raise RuntimeError("bug")

    monkeypatch.setattr(mod.subprocess, "Popen", bug)
    with pytest.raises(RuntimeError):
        mod._FileTreeView._open_in_explorer(str(tmp_path))  # noqa: SLF001


@pytest.mark.parametrize("select, expected", [(True, ["open", "-R"]), (False, ["open"])])
def test_macos_reveal_or_open(monkeypatch, popen, tmp_path, select, expected):
    """``open "" <path>`` used to be run for select=False; the empty argument made it fail."""
    monkeypatch.setattr(sys, "platform", "darwin")
    mod._reveal_in_file_manager(str(tmp_path), select)  # noqa: SLF001
    assert popen == [[*expected, str(tmp_path)]]
