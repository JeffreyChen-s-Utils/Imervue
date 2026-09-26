"""Tests for the Paint workspace's autosave behaviour and close confirmation.

Qt-free: the mixin methods run on small stand-ins, so this file is not
GL-skipped and runs on CI.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.paint.auto_save import list_snapshots, write_snapshot
from Imervue.paint.document import PaintDocument
from Imervue.paint.file_menu import _FileMenuBridge
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.workspace_autosave import AutosaveMixin


def _document():
    doc = PaintDocument()
    doc.load_image(np.full((6, 6, 4), 120, dtype=np.uint8))
    return doc


class _Canvas:
    """A hashable canvas stand-in (the dirty map is keyed by canvas)."""

    @staticmethod
    def document():
        return _document()


class _Host(AutosaveMixin):
    """Just what the mixin reads: a canvas, its dirty flag and a status refresh."""

    def __init__(self, target, dirty=False):
        canvas = _Canvas()
        self._canvas = canvas
        self._tab_dirty = {canvas: dirty}
        self._autosave_target_dir = target
        self.snapshots = []

    def _refresh_status_line(self):
        pass

    def take_autosave_snapshot_now(self):
        self.snapshots.append(True)
        return super().take_autosave_snapshot_now()


def test_a_tick_snapshots_only_unsaved_work(tmp_path):
    """An untouched canvas is nothing to recover; snapshotting it offered a recovery each launch."""
    clean = _Host(tmp_path, dirty=False)
    clean._on_autosave_tick()  # noqa: SLF001
    assert clean.snapshots == []
    dirty = _Host(tmp_path, dirty=True)
    dirty._on_autosave_tick()  # noqa: SLF001
    assert dirty.snapshots == [True]
    assert len(list_snapshots(tmp_path)) == 1


def test_a_workspace_deletes_only_its_own_snapshots(tmp_path):
    other = write_snapshot(_document(), directory=tmp_path, project_name="other window")
    host = _Host(tmp_path, dirty=True)
    host._on_autosave_tick()  # noqa: SLF001
    assert len(list_snapshots(tmp_path)) == 2
    assert host.discard_own_autosaves() == 1
    remaining = list_snapshots(tmp_path)
    assert [s.bundle_path for s in remaining] == [other.bundle_path]
    assert host.discard_own_autosaves() == 0


class _Closing:
    def __init__(self, unsaved, discard):
        self.log = []
        self._unsaved, self._discard = unsaved, discard

    def _has_unsaved_tabs(self):
        return self._unsaved

    def _confirm_discard_all_unsaved(self):
        self.log.append("asked")
        return self._discard

    def stop_autosave(self):
        self.log.append("stop")

    def discard_own_autosaves(self):
        self.log.append("discard snapshots")

    def _save_dock_state(self):
        self.log.append("save docks")


@pytest.mark.parametrize(("unsaved", "discard", "allowed", "log"), [
    (False, None, True, ["stop", "discard snapshots", "save docks"]),
    (True, True, True, ["asked", "stop", "discard snapshots", "save docks"]),
    (True, False, False, ["asked"]),
])
def test_confirm_close(unsaved, discard, allowed, log):
    host = _Closing(unsaved, discard)
    assert PaintWorkspace.confirm_close(host) is allowed
    assert host.log == log


@pytest.mark.parametrize(("restored", "message"), [
    (True, "Restored the latest autosave"),
    (False, "No autosave to restore"),
])
def test_restore_autosave_from_the_file_menu(restored, message):
    """The recovery toast pointed at File > Restore, which did not exist."""
    shown = []
    workspace = SimpleNamespace(restore_latest_autosave=lambda: restored,
                                toast=SimpleNamespace(info=shown.append))
    assert _FileMenuBridge(workspace).restore_autosave() is restored
    assert shown == [message]
