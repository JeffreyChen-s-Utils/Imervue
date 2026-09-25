"""Tests for UnreadableFileGuard: no save over an unreadable file without a copy of it."""
from __future__ import annotations

import logging
import shutil

import pytest

from Imervue.system.unreadable_guard import UnreadableFileGuard

_LOG = logging.getLogger("Imervue.test_unreadable_guard")


@pytest.fixture
def store(tmp_path):
    path = tmp_path / "store.json"
    path.write_text("{broken", encoding="utf-8")
    return path


def _copies(path):
    return sorted(path.parent.glob(f"{path.name}.unreadable-*"))


def test_a_file_that_was_read_is_saved_over_freely(store):
    guard = UnreadableFileGuard(_LOG)
    assert guard.clear_to_save(store) is True
    assert _copies(store) == []
    assert guard.unreadable_path is None


def test_the_first_save_keeps_a_copy(store, caplog):
    guard = UnreadableFileGuard(_LOG)
    with caplog.at_level(logging.WARNING, logger=_LOG.name):
        guard.note_unreadable(store)
        assert guard.clear_to_save(store) is True
    (copy,) = _copies(store)
    assert copy.read_text(encoding="utf-8") == "{broken"
    assert str(copy) in caplog.text


def test_only_one_copy_is_kept(store):
    guard = UnreadableFileGuard(_LOG)
    guard.note_unreadable(store)
    assert guard.clear_to_save(store) is True
    assert guard.clear_to_save(store) is True
    assert len(_copies(store)) == 1
    assert guard.unreadable_path == store


def test_a_file_gone_by_save_time_needs_no_copy(store):
    guard = UnreadableFileGuard(_LOG)
    guard.note_unreadable(store)
    store.unlink()
    assert guard.clear_to_save(store) is True
    assert _copies(store) == []


def test_no_save_while_the_copy_cannot_be_made(store, monkeypatch, caplog):
    real_copy2 = shutil.copy2
    failing = True

    def copy2(src, dst, **kwargs):
        if failing:
            raise PermissionError("disk full")
        return real_copy2(src, dst, **kwargs)

    monkeypatch.setattr(shutil, "copy2", copy2)
    guard = UnreadableFileGuard(_LOG)
    guard.note_unreadable(store)
    with caplog.at_level(logging.ERROR, logger=_LOG.name):
        assert guard.clear_to_save(store) is False
    assert "not saving over it" in caplog.text
    failing = False
    assert guard.clear_to_save(store) is True
    assert len(_copies(store)) == 1
