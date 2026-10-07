"""Background autosave writes coherent committed documents and coalesces latest requests."""
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, QThreadPool
from shiboken6 import isValid

from Imervue.paint import auto_save, autosave_jobs
from Imervue.paint.document import PaintDocument
from Imervue.paint.undo_stack import UndoStack
from Imervue.paint.workspace_autosave import AutosaveMixin


class _Canvas:
    def __init__(self, value=17):
        self._document = PaintDocument()
        self._document.load_image(np.full((4, 5, 4), value, dtype=np.uint8))

    def document(self):
        return self._document


class _Host(QObject, AutosaveMixin):
    def __init__(self, directory):
        QObject.__init__(self)
        self._canvas = _Canvas()
        self._autosave_target_dir = directory
        self._tab_dirty = {self._canvas: True}
        self._undo_stacks = {self._canvas: UndoStack(self._canvas.document())}
        self.callback_threads = []
        self.warnings = []
        self.toast = SimpleNamespace(warning=self.warnings.append)

    def _refresh_status_line(self):
        self.callback_threads.append(QThread.currentThread())


def _dispose(host, release):
    jobs = getattr(host, "_autosave_jobs", None)
    if jobs is not None and isValid(jobs):
        jobs.close()
    release.set()
    QThreadPool.globalInstance().waitForDone(10000)
    if isValid(host):
        host.deleteLater()


def _blocked_writer(monkeypatch, *, observe=None):
    entered, release = Event(), Event()
    write = autosave_jobs.write_snapshot

    def blocked(document, **kwargs):
        if observe is not None:
            observe(document)
        entered.set()
        if not release.wait(10):
            raise TimeoutError("writer was not released")
        return write(document, **kwargs)

    monkeypatch.setattr(autosave_jobs, "write_snapshot", blocked)
    return entered, release


def test_tick_never_reads_mutating_live_pixels_on_worker(qapp, tmp_path, pump_until, monkeypatch):
    entered, release = Event(), Event()
    write = autosave_jobs.write_snapshot
    threads = []

    def blocked(document, **kwargs):
        threads.append(QThread.currentThread())
        entered.set()
        if not release.wait(10):
            raise TimeoutError("writer was not released")
        return write(document, **kwargs)

    monkeypatch.setattr(autosave_jobs, "write_snapshot", blocked)
    host = _Host(tmp_path)
    try:
        host._on_autosave_tick()
        assert pump_until(entered.is_set)
        # A subsequent in-progress stroke mutates both layers and selection;
        # the writer owns the earlier immutable committed version.
        live = host._canvas.document()
        live.active_layer().image.fill(99)
        live.set_selection(np.ones(live.shape, dtype=bool))
        release.set()
        assert pump_until(lambda: bool(host.callback_threads))
        snapshots = auto_save.list_snapshots(tmp_path)
        restored = auto_save.recover_snapshot(snapshots[0])
        np.testing.assert_array_equal(restored.active_layer().image,
                                      np.full((4, 5, 4), 17, dtype=np.uint8))
        assert restored.selection() is None
        assert threads[0] != host.thread()
        assert host.callback_threads == [host.thread()]
    finally:
        _dispose(host, release)


def test_busy_writer_keeps_only_latest_pending_document_version(
    qapp, tmp_path, pump_until, monkeypatch,
):
    entered, release = Event(), Event()
    write = autosave_jobs.write_snapshot
    values = []

    def blocked(document, **kwargs):
        values.append(int(document.active_layer().image[0, 0, 0]))
        if len(values) == 1:
            entered.set()
            if not release.wait(10):
                raise TimeoutError("writer was not released")
        return write(document, **kwargs)

    monkeypatch.setattr(autosave_jobs, "write_snapshot", blocked)
    host = _Host(tmp_path)
    try:
        host._on_autosave_tick()
        assert pump_until(entered.is_set)
        host._on_autosave_tick()
        assert not host._autosave_jobs._pending
        for value in (31, 64):
            host._canvas.document().active_layer().image.fill(value)
            host._undo_stacks[host._canvas].commit()
            host._on_autosave_tick()
        assert len(host._autosave_jobs._pending) == 1
        release.set()
        assert pump_until(lambda: len(host.callback_threads) == 2)
        assert values == [17, 64]
        restored = auto_save.recover_snapshot(auto_save.list_snapshots(tmp_path)[0])
        assert restored.active_layer().image[0, 0, 0] == 64
    finally:
        _dispose(host, release)


def test_closing_tab_cancels_late_write_without_leaving_recovery_file(
    qapp, tmp_path, pump_until, monkeypatch,
):
    entered, release = _blocked_writer(monkeypatch)
    host = _Host(tmp_path)
    try:
        host._on_autosave_tick()
        assert pump_until(entered.is_set)
        assert host.discard_canvas_autosaves(host._canvas) == 0
        release.set()
        assert pump_until(lambda: host._autosave_jobs._active is None)
        assert not auto_save.list_snapshots(tmp_path)
        assert not host.callback_threads
    finally:
        _dispose(host, release)


@pytest.mark.parametrize("error", [OSError("disk full"), PermissionError("read only"),
                                 ValueError("invalid metadata"), MemoryError("allocation failed")])
def test_failed_background_save_reports_error_and_keeps_previous_snapshot(
    qapp, tmp_path, pump_until, monkeypatch, error,
):
    host = _Host(tmp_path)
    valid = host.take_autosave_snapshot_now()

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(autosave_jobs, "write_snapshot", fail)
    try:
        host._on_autosave_tick()
        assert pump_until(lambda: bool(host.warnings))
        assert str(error) in host.warnings[0]
        assert [s.bundle_path for s in auto_save.list_snapshots(tmp_path)] == [valid]
        restored = auto_save.recover_snapshot(auto_save.list_snapshots(tmp_path)[0])
        assert restored.active_layer().image[0, 0, 0] == 17
        assert host._tab_dirty[host._canvas]
    finally:
        _dispose(host, Event())


def test_history_disabled_fallback_copies_before_background_write(
    qapp, tmp_path, pump_until, monkeypatch,
):
    entered, release = _blocked_writer(monkeypatch)
    host = _Host(tmp_path)
    host._undo_stacks[host._canvas] = UndoStack(host._canvas.document(), max_bytes=1)
    try:
        host._on_autosave_tick()
        assert pump_until(entered.is_set)
        host._canvas.document().active_layer().image.fill(99)
        release.set()
        assert pump_until(lambda: bool(host.callback_threads))
        restored = auto_save.recover_snapshot(auto_save.list_snapshots(tmp_path)[0])
        assert restored.active_layer().image[0, 0, 0] == 17
    finally:
        _dispose(host, release)


def test_destroyed_workspace_retains_writer_until_late_cleanup(qapp, tmp_path, pump_until, monkeypatch):
    entered, release = _blocked_writer(monkeypatch)
    host = _Host(tmp_path)
    try:
        host._on_autosave_tick()
        assert pump_until(entered.is_set)
        jobs = host._autosave_jobs
        host.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(host)
        assert isValid(jobs)
        release.set()
        assert pump_until(lambda: jobs._active is None)
        assert not auto_save.list_snapshots(tmp_path)
    finally:
        _dispose(host, release)


def test_cancel_after_worker_completed_discards_undelivered_file(qapp, tmp_path, pump_until):
    host = _Host(tmp_path)
    try:
        host._on_autosave_tick()
        assert QThreadPool.globalInstance().waitForDone(10000)
        assert len(auto_save.list_snapshots(tmp_path)) == 1
        host.discard_canvas_autosaves(host._canvas)
        assert pump_until(lambda: host._autosave_jobs._active is None)
        assert QThreadPool.globalInstance().waitForDone(10000)
        assert not auto_save.list_snapshots(tmp_path)
        assert not host.callback_threads
    finally:
        _dispose(host, Event())


def test_returning_to_active_version_removes_obsolete_pending_save(
    qapp, tmp_path, pump_until, monkeypatch,
):
    entered, release = Event(), Event()
    write = autosave_jobs.write_snapshot
    values = []

    def blocked(document, **kwargs):
        values.append(int(document.active_layer().image[0, 0, 0]))
        entered.set()
        if not release.wait(10):
            raise TimeoutError("writer was not released")
        return write(document, **kwargs)

    monkeypatch.setattr(autosave_jobs, "write_snapshot", blocked)
    host = _Host(tmp_path)
    stack = host._undo_stacks[host._canvas]
    try:
        host._on_autosave_tick()
        assert pump_until(entered.is_set)
        host._canvas.document().active_layer().image.fill(99)
        stack.commit()
        host._on_autosave_tick()
        assert len(host._autosave_jobs._pending) == 1
        assert stack.undo()
        host._on_autosave_tick()
        assert not host._autosave_jobs._pending
        release.set()
        assert pump_until(lambda: bool(host.callback_threads))
        assert values == [17]
    finally:
        _dispose(host, release)


def test_replaced_document_cancels_old_version_and_saves_new_identity(
    qapp, tmp_path, pump_until, monkeypatch,
):
    entered, release = _blocked_writer(monkeypatch)
    host = _Host(tmp_path)
    try:
        host._on_autosave_tick()
        assert pump_until(entered.is_set)
        old_id = host._autosave_records[host._canvas][1]
        host._canvas._document = _Canvas(99).document()
        host._undo_stacks[host._canvas] = UndoStack(host._canvas.document())
        host._on_autosave_tick()
        new_id = host._autosave_records[host._canvas][1]
        assert new_id != old_id
        release.set()
        assert pump_until(lambda: bool(host.callback_threads))
        snapshots = auto_save.list_snapshots(tmp_path)
        assert [snapshot.document_id for snapshot in snapshots] == [new_id]
        assert auto_save.recover_snapshot(snapshots[0]).active_layer().image[0, 0, 0] == 99
    finally:
        _dispose(host, release)


def test_background_snapshot_keeps_full_editable_content(qapp, tmp_path, pump_until):
    from Imervue.paint.manga_panels import panel_grid
    host = _Host(tmp_path)
    document = host._canvas.document()
    layer = document.add_layer(name="Masked")
    layer.opacity = .37
    layer.mask = np.full((4, 5), 23, dtype=np.uint8)
    document.create_group("Group", opacity=.5)
    document.set_layer_group(1, group="Group")
    document.set_selection(np.ones((4, 5), dtype=bool))
    document.save_selection("Saved")
    document.set_reference_layer_index(0)
    document.panel_layout = panel_grid(5, 4, 1, 1, gutter=0, border_width=1)
    host._undo_stacks[host._canvas].commit()
    try:
        host._on_autosave_tick()
        assert pump_until(lambda: bool(host.callback_threads))
        restored = auto_save.recover_snapshot(auto_save.list_snapshots(tmp_path)[0])
        assert restored.layer_count == 2
        assert restored.layer_at(1).name == "Masked"
        assert restored.layer_at(1).opacity == .37
        np.testing.assert_array_equal(restored.layer_at(1).mask, layer.mask)
        np.testing.assert_array_equal(restored.selection(), document.selection())
        np.testing.assert_array_equal(restored.named_selection("Saved"), document.named_selection("Saved"))
        assert restored.group("Group").opacity == .5
        assert restored.reference_layer_index() == 0
        assert restored.panel_layout == document.panel_layout
    finally:
        _dispose(host, Event())


def test_empty_dirty_document_finishes_without_claiming_a_save(qapp, tmp_path, pump_until):
    host = _Host(tmp_path)
    host._canvas._document = PaintDocument()
    host._undo_stacks[host._canvas] = UndoStack(host._canvas.document())
    try:
        host._on_autosave_tick()
        assert pump_until(lambda: host._autosave_jobs._active is None)
        assert not host.callback_threads
        assert not host.warnings
        assert not auto_save.list_snapshots(tmp_path)
    finally:
        _dispose(host, Event())


def test_fallback_copy_failure_reports_without_touching_the_document(qapp, tmp_path, monkeypatch):
    from Imervue.paint import workspace_autosave
    host = _Host(tmp_path)
    host._undo_stacks.clear()

    def fail(_document):
        raise MemoryError("snapshot copy failed")

    monkeypatch.setattr(workspace_autosave.copy, "deepcopy", fail)
    try:
        host._on_autosave_tick()
        assert "snapshot copy failed" in host.warnings[0]
        assert host._canvas.document().active_layer().image[0, 0, 0] == 17
        assert not hasattr(host, "_autosave_jobs")
        assert not auto_save.list_snapshots(tmp_path)
    finally:
        _dispose(host, Event())


def test_replacement_without_another_tick_discards_obsolete_result(
    qapp, tmp_path, pump_until, monkeypatch,
):
    entered, release = _blocked_writer(monkeypatch)
    host = _Host(tmp_path)
    try:
        host._on_autosave_tick()
        assert pump_until(entered.is_set)
        host._canvas._document = _Canvas(99).document()
        release.set()
        assert pump_until(lambda: host._autosave_jobs._active is None)
        assert QThreadPool.globalInstance().waitForDone(10000)
        assert not host.callback_threads
        assert not auto_save.list_snapshots(tmp_path)
    finally:
        _dispose(host, release)


def test_deleted_canvas_at_delivery_discards_result(qapp, tmp_path, pump_until, monkeypatch):
    entered, release = _blocked_writer(monkeypatch)
    host = _Host(tmp_path)

    def deleted():
        raise RuntimeError("canvas was deleted")

    try:
        host._on_autosave_tick()
        assert pump_until(entered.is_set)
        monkeypatch.setattr(host._canvas, "document", deleted)
        release.set()
        assert pump_until(lambda: host._autosave_jobs._active is None)
        assert QThreadPool.globalInstance().waitForDone(10000)
        assert not host.callback_threads
        assert not auto_save.list_snapshots(tmp_path)
    finally:
        _dispose(host, release)


def test_failed_first_document_does_not_block_other_dirty_tab(qapp, tmp_path, pump_until, monkeypatch):
    write = autosave_jobs.write_snapshot

    def selective(document, **kwargs):
        if document.active_layer().image[0, 0, 0] == 17:
            raise OSError("first document failed")
        return write(document, **kwargs)

    monkeypatch.setattr(autosave_jobs, "write_snapshot", selective)
    host = _Host(tmp_path)
    background = _Canvas(99)
    host._tab_dirty[background] = True
    host._undo_stacks[background] = UndoStack(background.document())
    active = host._canvas
    try:
        host._on_autosave_tick()
        assert pump_until(lambda: bool(host.callback_threads))
        assert host.warnings
        assert host._canvas is active
        snapshots = auto_save.list_snapshots(tmp_path)
        assert len(snapshots) == 1
        assert snapshots[0].document_id == host._autosave_records[background][1]
        assert auto_save.recover_snapshot(snapshots[0]).active_layer().image[0, 0, 0] == 99
    finally:
        _dispose(host, Event())
