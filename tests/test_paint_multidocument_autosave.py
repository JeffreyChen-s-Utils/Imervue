"""Multi-document autosave and restart recovery without GL widgets."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.paint import auto_save
from Imervue.paint.document import PaintDocument
from Imervue.paint.manga_panels import panel_grid, panel_layout_from_dict, panel_layout_to_dict
from Imervue.paint.workspace_autosave import AutosaveMixin


class _Canvas:
    def __init__(self, value=0):
        self.set_document(PaintDocument())
        self._doc.load_image(np.full((3, 4, 4), value, dtype=np.uint8))

    def document(self):
        return self._doc

    def set_document(self, document):
        self._doc = document


class _Host(AutosaveMixin):
    def __init__(self, directory):
        self._autosave_target_dir = directory
        self._canvas = _Canvas(17)
        self._tab_dirty = {self._canvas: True}
        self.canvases = [self._canvas]
        self.warnings = []
        self.toast = SimpleNamespace(warning=self.warnings.append)

    def _refresh_status_line(self):
        pass

    def new_tab(self, **_kwargs):
        self._canvas = _Canvas()
        self.canvases.append(self._canvas)
        self._tab_dirty[self._canvas] = False
        return self._canvas

    def _set_tab_dirty(self, canvas, dirty):
        self._tab_dirty[canvas] = dirty


def test_tick_preserves_dirty_background_tab_without_switching(tmp_path):
    host = _Host(tmp_path)
    edited = host._canvas
    viewing = host.new_tab()
    host._on_autosave_tick()
    snapshots = auto_save.list_snapshots(tmp_path)
    assert len(snapshots) == 1
    assert host._canvas is viewing
    assert host._tab_dirty == {edited: True, viewing: False}
    recovered = auto_save.recover_snapshot(snapshots[0])
    np.testing.assert_array_equal(recovered.active_layer().image, edited.document().active_layer().image)


def test_simultaneous_snapshots_and_retention_are_per_document(tmp_path, monkeypatch):
    monkeypatch.setattr(auto_save.time, "time", lambda: 1234567890.5)
    host = _Host(tmp_path)
    first = host._canvas
    second = host.new_tab()
    second.document().active_layer().image.fill(99)
    host._set_tab_dirty(second, True)
    for _ in range(auto_save.AUTOSAVE_KEEP_MAX + 3):
        host._on_autosave_tick()
    snapshots = auto_save.list_snapshots(tmp_path)
    assert len(snapshots) == auto_save.AUTOSAVE_KEEP_MAX * 2
    counts = {s.document_id: sum(x.document_id == s.document_id for x in snapshots) for s in snapshots}
    assert sorted(counts.values()) == [auto_save.AUTOSAVE_KEEP_MAX] * 2
    assert len({s.bundle_path for s in snapshots}) == len(snapshots)
    assert host._canvas is second
    assert first is not second


def test_restart_recovers_latest_versions_in_new_dirty_tabs(tmp_path):
    original = _Host(tmp_path)
    original._on_autosave_tick()
    original._canvas.document().active_layer().image.fill(31)
    original._on_autosave_tick()
    original.new_tab().document().active_layer().image.fill(64)
    original._set_tab_dirty(original._canvas, True)
    original._on_autosave_tick()
    restarted = _Host(tmp_path)
    existing = restarted._canvas
    assert restarted.restore_all_autosaves(target_dir=tmp_path) == 2
    assert len(restarted.canvases) == 3
    assert existing.document().active_layer().image[0, 0, 0] == 17
    assert sorted(c.document().active_layer().image[0, 0, 0] for c in restarted.canvases[1:]) == [31, 64]
    assert all(restarted._tab_dirty[c] for c in restarted.canvases)
    assert restarted.restore_all_autosaves(target_dir=tmp_path) == 0
    restarted.discard_own_autosaves()
    assert auto_save.list_snapshots(tmp_path) == []


def test_recovery_falls_back_when_newest_bundle_is_damaged(tmp_path):
    host = _Host(tmp_path)
    host._on_autosave_tick()
    host._on_autosave_tick()
    latest = auto_save.list_snapshots(tmp_path)[0]
    latest.bundle_path.write_bytes(b"broken bundle")
    restarted = _Host(tmp_path)
    assert restarted.restore_all_autosaves(target_dir=tmp_path) == 1
    assert restarted._canvas.document().active_layer().image[0, 0, 0] == 17


def test_replacing_document_does_not_share_retention_identity(tmp_path):
    host = _Host(tmp_path)
    host.take_autosave_snapshot_now()
    host._canvas.set_document(_Canvas(51).document())
    host.take_autosave_snapshot_now()
    assert len({s.document_id for s in auto_save.list_snapshots(tmp_path)}) == 2


def test_close_tab_discards_only_that_documents_snapshots(tmp_path):
    host = _Host(tmp_path)
    first = host._canvas
    host._on_autosave_tick()
    host.new_tab()
    host._set_tab_dirty(host._canvas, True)
    host._on_autosave_tick()
    assert host.discard_canvas_autosaves(first) == 2
    remaining = auto_save.list_snapshots(tmp_path)
    assert len(remaining) == 1
    assert first not in host._autosave_records


@pytest.mark.parametrize("error", [OSError("disk full"), PermissionError("read only")])
def test_failed_document_does_not_block_another_dirty_tab(tmp_path, monkeypatch, error):
    host = _Host(tmp_path)
    failed_doc = host._canvas.document()
    active = host.new_tab()
    host._set_tab_dirty(active, True)
    write = auto_save.write_snapshot

    def selective_failure(document, **kwargs):
        if document is failed_doc:
            raise error
        return write(document, **kwargs)

    monkeypatch.setattr(auto_save, "write_snapshot", selective_failure)
    host._on_autosave_tick()
    assert len(auto_save.list_snapshots(tmp_path)) == 1
    assert host.warnings
    assert host._canvas is active


def test_metadata_failure_keeps_previous_valid_snapshot(tmp_path, monkeypatch):
    document = _Canvas(12).document()
    good = auto_save.write_snapshot(document, directory=tmp_path, document_id="a")

    def fail(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(auto_save, "write_text_atomically", fail)
    with pytest.raises(OSError, match="disk full"):
        auto_save.write_snapshot(document, directory=tmp_path, document_id="a")
    assert auto_save.list_snapshots(tmp_path) == [good]
    assert list(tmp_path.glob("*.imervue")) == [good.bundle_path]


def test_autosave_preserves_manga_panel_clipping(tmp_path):
    document = _Canvas().document()
    document.panel_layout = panel_grid(4, 3, 1, 2, gutter=0, border_width=1)
    snapshot = auto_save.write_snapshot(document, directory=tmp_path, document_id="manga")
    restored = auto_save.recover_snapshot(snapshot)
    assert restored.panel_layout == document.panel_layout
    assert panel_layout_from_dict(panel_layout_to_dict(document.panel_layout)) == document.panel_layout
    assert panel_layout_from_dict(None) is None
    assert panel_layout_to_dict(None) is None


@pytest.mark.parametrize("raw", [[], {}, {"width": -1, "height": 4, "gutter": 0,
                                        "border_width": 1, "cells": []},
                               {"width": 4, "height": 3, "gutter": 0,
                                "border_width": 1, "cells": [{"x": 3, "y": 0, "w": 2, "h": 1}]}])
def test_invalid_panel_metadata_is_rejected(raw):
    with pytest.raises(ValueError):
        panel_layout_from_dict(raw)


def test_recovery_fork_keeps_separate_quota_and_ownership(tmp_path):
    host = _Host(tmp_path)
    first = host._canvas
    host.take_autosave_snapshot_now()
    assert host.restore_all_autosaves() == 1
    restored = host._canvas
    restored.document().active_layer().image.fill(98)
    for _ in range(auto_save.AUTOSAVE_KEEP_MAX + 1):
        host.take_autosave_snapshot_now()
    assert len({s.document_id for s in auto_save.list_snapshots(tmp_path)}) == 2
    assert host.discard_canvas_autosaves(restored) == auto_save.AUTOSAVE_KEEP_MAX
    remaining = auto_save.list_snapshots(tmp_path)
    assert len(remaining) == 1
    assert remaining[0].document_id == host._autosave_records[first][1]


def test_recovery_from_other_directory_is_cleaned_after_discard(tmp_path):
    source = _Host(tmp_path / "crashed")
    source.take_autosave_snapshot_now()
    restarted = _Host(tmp_path / "current")
    assert restarted.restore_all_autosaves(target_dir=tmp_path / "crashed") == 1
    assert restarted.discard_canvas_autosaves(restarted._canvas) == 1
    assert auto_save.list_snapshots(tmp_path / "crashed") == []
