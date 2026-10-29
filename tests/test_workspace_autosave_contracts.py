"""Contract tests for the Paint autosave mixin's timer, queue, recovery and cleanup paths.

Qt-light: the mixin runs on plain stand-ins (a ``QObject`` host only where the timer
needs a parent), so no GL widget is built and the file runs on CI.
"""
from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QObject

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import auto_save
from Imervue.paint.document_status import document_status
from Imervue.paint.workspace_autosave import AutosaveMixin


class _Canvas:
    """Hashable canvas stand-in returning one fixed document."""

    def __init__(self, document=None):
        self._document = document if document is not None else object()

    def document(self):
        return self._document


class _DeadCanvas:
    """A canvas whose C++ object is gone."""

    def document(self):
        raise RuntimeError("deleted")


class _Toast:
    def __init__(self):
        self.calls = []

    def warning(self, message, **kwargs):
        self.calls.append((message, kwargs))


class _Tabs:
    def __init__(self, canvases, texts):
        self._canvases, self.texts = list(canvases), list(texts)

    def indexOf(self, canvas):  # noqa: N802 - Qt naming
        return self._canvases.index(canvas) if canvas in self._canvases else -1

    def tabText(self, index):  # noqa: N802 - Qt naming
        return self.texts[index]

    def setTabText(self, index, text):  # noqa: N802 - Qt naming
        self.texts[index] = text


class _Jobs:
    def __init__(self):
        self.cancelled, self.discarded, self.cancel_all_calls = [], [], 0

    def cancel(self, document_id):
        self.cancelled.append(document_id)

    def cancel_all(self):
        self.cancel_all_calls += 1

    def discard_result(self, snapshot):
        self.discarded.append(snapshot)


class _Host(AutosaveMixin):
    def __init__(self, canvas=None):
        self._canvas = canvas if canvas is not None else _Canvas()
        self.refreshed = []

    def _refresh_tab_title(self, canvas):
        self.refreshed.append(canvas)


class _QHost(QObject, AutosaveMixin):
    def __init__(self):
        super().__init__()
        self._canvas = _Canvas()


def _snapshot(name, *, document_id="", source="", project="p"):
    path = Path(name)
    return auto_save.AutoSaveSnapshot(path, path.with_suffix(".json"), 0.0, project,
                                      source, document_id=document_id)


# --- timer ---------------------------------------------------------------------------


def test_start_autosave_reuses_one_timer_with_a_one_second_floor(qapp, tmp_path):
    host = _QHost()
    try:
        host.start_autosave(interval_sec=0, target_dir=tmp_path)
        timer = host._autosave_timer
        assert host._autosave_target_dir == tmp_path
        assert timer.isActive()
        from Imervue.paint.auto_save import DEFAULT_INTERVAL_SEC
        assert timer.interval() == max(1000, DEFAULT_INTERVAL_SEC * 1000)
        host.start_autosave(interval_sec=0.5)
        assert host._autosave_timer is timer
        assert timer.interval() == 1000
        assert host._autosave_target_dir is None
        host.start_autosave(interval_sec=3)
        assert timer.interval() == 3000
        host.stop_autosave()
        assert not timer.isActive()
    finally:
        host.stop_autosave()
        host.deleteLater()


# --- explicit snapshot / title / identity --------------------------------------------


def test_title_comes_from_the_tab_without_the_dirty_star():
    host = _Host()
    assert host._autosave_title(host._canvas) == "Untitled"
    host._tabs = _Tabs([host._canvas], ["Poster *"])
    assert host._autosave_title(host._canvas) == "Poster"
    assert host._autosave_title(_Canvas()) == "Untitled"


def test_record_is_stable_until_the_document_changes_and_cancels_the_old_job():
    host = _Host()
    host._autosave_jobs = jobs = _Jobs()
    host._autosave_last_by_canvas = {host._canvas: 1.0}
    first = host._autosave_record(host._canvas)
    assert first[0] is host._canvas.document()
    assert jobs.cancelled == []
    assert host._autosave_last_by_canvas == {}
    assert host._autosave_record(host._canvas) is first
    host._canvas._document = object()
    second = host._autosave_record(host._canvas)
    assert second[1] != first[1]
    assert jobs.cancelled == [first[1]]


def test_explicit_snapshot_failure_reports_and_returns_none(caplog):
    host = _Host(_DeadCanvas())
    host.toast = _Toast()
    with caplog.at_level(logging.WARNING, logger="Imervue"):
        assert host.take_autosave_snapshot_now() is None
    assert "Paint autosave failed: deleted" in caplog.text
    assert host.toast.calls[0][0] == language_wrapper.language_word_dict.get(
        "paint_autosave_failed", "Autosave failed: {error}").format(error="deleted")


def test_explicit_snapshot_with_nothing_to_save_records_nothing(monkeypatch):
    host = _Host()
    monkeypatch.setattr(auto_save, "write_snapshot", lambda *_a, **_k: None)
    assert host.take_autosave_snapshot_now() is None
    assert not hasattr(host, "_autosave_written")
    assert not hasattr(host, "_last_autosave_at")


def test_explicit_snapshot_records_ownership_for_a_background_canvas(monkeypatch):
    host = _Host()
    other = _Canvas()
    seen = {}

    def fake_write(document, *, directory, document_id, project_name):
        seen.update(document=document, directory=directory, id=document_id, name=project_name)
        return _snapshot("bundle.imervue")

    monkeypatch.setattr(auto_save, "write_snapshot", fake_write)
    host._autosave_target_dir = "dir"
    assert host.take_autosave_snapshot_now(canvas=other) == Path("bundle.imervue")
    assert seen["document"] is other.document()
    assert seen["directory"] == "dir"
    assert seen["name"] == "Untitled"
    assert seen["id"] == host._autosave_records[other][1]
    assert not hasattr(host, "_last_autosave_at")
    assert host._autosave_written == {Path("bundle.imervue")}
    assert host._autosave_paths_by_canvas[other] == {Path("bundle.imervue")}
    assert other in host._autosave_last_by_canvas
    assert document_status(other).autosave == "saved"
    assert host.refreshed == [other]


# --- error reporting -----------------------------------------------------------------


def test_report_error_sets_failed_state_and_tolerates_a_dead_canvas(caplog):
    host = _Host()
    host._report_autosave_error("disk full", canvas=host._canvas)
    state = document_status(host._canvas)
    assert (state.autosave, state.autosave_error) == ("failed", "disk full")
    with caplog.at_level(logging.DEBUG, logger="Imervue"):
        host._report_autosave_error("gone", canvas=_DeadCanvas())
    assert "Autosave status canvas already deleted" in caplog.text


# --- queue ---------------------------------------------------------------------------


def test_tick_on_a_plain_host_snapshots_each_dirty_tab_synchronously():
    calls = []

    class Host(_Host):
        def take_autosave_snapshot_now(self, *, canvas=None):
            calls.append(canvas)

    host = Host()
    other, clean = _Canvas(), _Canvas()
    host._tab_dirty = {host._canvas: True, other: True, clean: False}
    host._on_autosave_tick()
    assert calls == [None, other]


def test_tick_on_a_qobject_host_queues_instead_of_writing(qapp):
    requested = []

    class Host(_QHost):
        def _request_autosave(self, canvas):
            requested.append(canvas)

    host = Host()
    try:
        host._tab_dirty = {host._canvas: True}
        host._on_autosave_tick()
        assert requested == [host._canvas]
    finally:
        host.deleteLater()


def test_async_result_for_an_unknown_document_is_discarded():
    host = _Host()
    host._autosave_jobs = jobs = _Jobs()
    snap = _snapshot("late.imervue")
    host._on_async_autosave_saved("missing", snap, "")
    assert jobs.discarded == [snap]
    host._on_async_autosave_saved("missing", None, "boom")
    assert jobs.discarded == [snap]


def test_async_result_for_a_replaced_or_dead_canvas_is_discarded():
    host = _Host()
    host._autosave_jobs = jobs = _Jobs()
    dead = _DeadCanvas()
    host._autosave_records = {host._canvas: (object(), "a"), dead: (object(), "b")}
    host._on_async_autosave_saved("a", _snapshot("a.imervue"), "")
    host._on_async_autosave_saved("b", _snapshot("b.imervue"), "")
    assert [s.bundle_path for s in jobs.discarded] == [Path("a.imervue"), Path("b.imervue")]


def test_async_result_for_the_current_document_reports_then_records():
    host = _Host()
    host._autosave_jobs = _Jobs()
    host._autosave_records = {host._canvas: (host._canvas.document(), "id")}
    host._on_async_autosave_saved("id", _snapshot("ok.imervue"), "metadata failed")
    state = document_status(host._canvas)
    assert state.autosave == "saved"
    assert state.autosave_error == ""
    assert host._autosave_written == {Path("ok.imervue")}
    assert isinstance(host._last_autosave_at, float)
    host._on_async_autosave_saved("id", None, "write failed")
    assert document_status(host._canvas).autosave_error == "write failed"


# --- cleanup -------------------------------------------------------------------------


def test_discard_canvas_cancels_its_job_and_forgets_only_that_canvas(tmp_path):
    host = _Host()
    other = _Canvas()
    host._autosave_jobs = jobs = _Jobs()
    host._autosave_records = {host._canvas: (None, "mine"), other: (None, "theirs")}
    host._autosave_last_by_canvas = {host._canvas: 1.0, other: 2.0}
    mine = write_bundle(tmp_path, "mine")
    host._autosave_paths_by_canvas = {host._canvas: {mine}, other: set()}
    host._autosave_written = {mine}
    assert host.discard_canvas_autosaves(host._canvas) == 1
    assert jobs.cancelled == ["mine"]
    assert list(host._autosave_records) == [other]
    assert list(host._autosave_last_by_canvas) == [other]
    assert host._autosave_written == set()
    assert _Host().discard_canvas_autosaves(other) == 0


def write_bundle(directory, name):
    """Create a bundle + meta pair on disk and return the bundle path."""
    bundle = directory / f"{name}.imervue"
    bundle.write_bytes(b"x")
    bundle.with_suffix(auto_save.AUTOSAVE_META_SUFFIX).write_text("{}", encoding="utf-8")
    return bundle


def test_discard_own_cancels_all_jobs_and_logs_undeletable_files(tmp_path, monkeypatch, caplog):
    host = _Host()
    host._autosave_jobs = jobs = _Jobs()
    good, bad = write_bundle(tmp_path, "good"), write_bundle(tmp_path, "bad")
    host._autosave_written = {good, bad}
    real = auto_save.discard_snapshot

    def flaky(snapshot):
        if snapshot.bundle_path == bad:
            raise OSError("locked")
        return real(snapshot)

    monkeypatch.setattr(auto_save, "discard_snapshot", flaky)
    with caplog.at_level(logging.WARNING, logger="Imervue"):
        assert host.discard_own_autosaves() == 1
    assert jobs.cancel_all_calls == 1
    assert host._autosave_written == {bad}
    assert "Could not remove Paint autosave: locked" in caplog.text
    assert _Host().discard_own_autosaves() == 0


# --- recovery ------------------------------------------------------------------------


def test_recovery_key_prefers_id_then_source_then_name():
    assert AutosaveMixin._recovery_key(_snapshot("a", document_id="i", source="s")) == "i"
    assert AutosaveMixin._recovery_key(_snapshot("a", source="s")) == "s"
    assert AutosaveMixin._recovery_key(_snapshot("a", project="n")) == "n"


def test_pending_autosaves_defaults_to_the_started_directory(monkeypatch):
    host = _Host()
    seen = []
    monkeypatch.setattr(auto_save, "pending_recovery_snapshots",
                        lambda target: seen.append(target) or ["s"])
    assert host.pending_autosaves() == ["s"]
    host._autosave_target_dir = "started"
    host.pending_autosaves()
    host.pending_autosaves(target_dir="given")
    assert seen == [None, "started", "given"]


def test_restore_all_skips_failures_and_already_recovered_documents():
    restored = []

    class Host(_Host):
        def pending_autosaves(self, *, target_dir=None):
            return [_snapshot("1", document_id="a"), _snapshot("2", document_id="a"),
                    _snapshot("3", document_id="bad"), _snapshot("4", document_id="b")]

        def restore_snapshot(self, snapshot):
            restored.append(snapshot.document_id)
            return snapshot.document_id != "bad"

    host = Host()
    assert host.restore_all_autosaves() == 2
    assert restored == ["a", "bad", "b"]
    assert host.restore_all_autosaves() == 0
    assert host._autosave_recovered == {"a", "b"}


def test_restore_latest_uses_the_first_snapshot_or_reports_none():
    picked = []

    class Host(_Host):
        snapshots = []

        def pending_autosaves(self, *, target_dir=None):
            return self.snapshots

        def restore_snapshot(self, snapshot):
            picked.append(snapshot)
            return True

    host = Host()
    assert host.restore_latest_autosave() is False
    host.snapshots = ["newest", "older"]
    assert host.restore_latest_autosave() is True
    assert picked == ["newest"]


def test_restore_snapshot_returns_false_for_an_unreadable_bundle(monkeypatch, caplog):
    host = _Host()

    def broken(_snapshot):
        raise ValueError("corrupt")

    monkeypatch.setattr(auto_save, "recover_snapshot", broken)
    with caplog.at_level(logging.WARNING, logger="Imervue"):
        assert host.restore_snapshot(_snapshot("bad.imervue")) is False
    assert "Could not recover Paint autosave bad.imervue: corrupt" in caplog.text


def test_restore_snapshot_opens_a_dirty_new_tab_and_claims_matching_files(monkeypatch, tmp_path):
    document = object()
    new_canvas = _Canvas()
    new_canvas.set_document = lambda doc: setattr(new_canvas, "doc", doc)
    calls = []

    class Host(_Host):
        def new_tab(self, *, width, height):
            calls.append(("new_tab", width, height))
            self._tabs = _Tabs([new_canvas], ["blank"])
            return new_canvas

        def _set_tab_dirty(self, canvas, dirty):
            calls.append(("dirty", canvas, dirty))

        def _ensure_undo_stack(self):
            calls.append(("undo",))

    host = Host()
    host._layer_dock = SimpleNamespace(set_document=lambda doc: calls.append(("dock", doc)))
    target = tmp_path / "t.imervue"
    sibling = tmp_path / "s.imervue"
    foreign = tmp_path / "f.imervue"
    snap = _snapshot(str(target), document_id="doc", project="Poster")
    listed = [snap, _snapshot(str(sibling), document_id="doc"),
              _snapshot(str(foreign), document_id="other")]
    monkeypatch.setattr(auto_save, "recover_snapshot", lambda _s: document)
    monkeypatch.setattr(auto_save, "list_snapshots",
                        lambda directory: calls.append(("list", directory)) or listed)
    assert host.restore_snapshot(snap) is True
    assert new_canvas.doc is document
    assert host._autosave_records[new_canvas][0] is document
    assert host._autosave_paths_by_canvas[new_canvas] == {target, sibling}
    assert host._autosave_written == {target, sibling}
    assert host._tabs.texts == ["Poster *"]
    assert host.refreshed == [new_canvas]
    assert calls == [("new_tab", 1, 1), ("list", tmp_path), ("dirty", new_canvas, True),
                     ("undo",), ("dock", document)]


def test_claim_skips_files_another_tab_already_owns(monkeypatch):
    host = _Host()
    other, mine = _Canvas(), _Canvas()
    owned = Path("owned.imervue")
    host._autosave_paths_by_canvas = {other: {owned}}
    host._autosave_written = {owned}
    snap = _snapshot("new.imervue", document_id="d")
    monkeypatch.setattr(auto_save, "list_snapshots",
                        lambda _d: [snap, _snapshot("owned.imervue", document_id="d")])
    host._claim_recovery_snapshots(snap, mine)
    assert host._autosave_paths_by_canvas[mine] == {Path("new.imervue")}
    assert host._autosave_written == {owned, Path("new.imervue")}


def test_recovery_offer_prefers_toast_then_status_and_ignores_io_errors():
    class Host(_Host):
        result = []

        def pending_autosaves(self, *, target_dir=None):
            if isinstance(self.result, Exception):
                raise self.result
            return self.result

    host = Host()
    host._status = SimpleNamespace(messages=[])
    host._status.showMessage = lambda msg, ms: host._status.messages.append((msg, ms))
    host._maybe_offer_autosave_recovery()
    host.result = OSError("unreadable")
    host._maybe_offer_autosave_recovery()
    host.result = ValueError("bad")
    host._maybe_offer_autosave_recovery()
    assert host._status.messages == []
    host.result = ["a", "b"]
    host._maybe_offer_autosave_recovery()
    expected = language_wrapper.language_word_dict.get(
        "paint_autosave_recovery_available",
        "{n} autosave snapshot(s) available — File ▸ Restore Autosave",
    ).format(n=2)
    assert host._status.messages == [(expected, 6000)]
    host.toast = _Toast()
    host._maybe_offer_autosave_recovery()
    assert host.toast.calls == [(expected, {"duration_ms": 6000})]
    assert len(host._status.messages) == 1
