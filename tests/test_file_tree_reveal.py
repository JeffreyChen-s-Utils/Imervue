"""The file tree reports a failed reveal-in-file-manager instead of dropping it."""
from __future__ import annotations

import pytest

from Imervue.gui import file_tree_view as mod
from Imervue.system import file_manager as fm


def test_missing_file_manager_is_logged_not_raised(monkeypatch, caplog, tmp_path):
    def missing(*_a, **_k):
        raise FileNotFoundError("explorer")

    monkeypatch.setattr(fm.subprocess, "Popen", missing)
    with caplog.at_level("DEBUG", logger="Imervue"):
        mod._FileTreeView._open_in_explorer(str(tmp_path))  # noqa: SLF001
    (record,) = [r for r in caplog.records if "reveal" in r.getMessage()]
    assert record.levelname == "WARNING" and record.exc_info[0] is FileNotFoundError


def test_unexpected_error_propagates(monkeypatch, tmp_path):
    def bug(*_a, **_k):
        raise RuntimeError("bug")

    monkeypatch.setattr(fm.subprocess, "Popen", bug)
    with pytest.raises(RuntimeError):
        mod._FileTreeView._open_in_explorer(str(tmp_path))  # noqa: SLF001
