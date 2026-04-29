"""Tests for the recursive file-tree watchdog."""
from __future__ import annotations

import time
from unittest.mock import MagicMock


def _fake_model() -> MagicMock:
    """Create a stand-in for QFileSystemModel.

    We only need the ``setRootPath`` slot — using ``MagicMock`` lets us match
    Qt's camelCase API without defining a method that violates our snake_case
    naming rule. The mock records each call's arguments via ``call_args_list``.
    """
    return MagicMock(spec=["setRootPath"])


def test_watch_no_op_for_nonexistent_path(qapp):
    from Imervue.system.file_tree_watcher import FileTreeWatchdog
    wd = FileTreeWatchdog()
    try:
        assert wd.watch("/path/that/does/not/exist") is False
        assert wd.watched_path == ""
    finally:
        wd.stop()


def test_watch_no_op_for_empty_string(qapp):
    from Imervue.system.file_tree_watcher import FileTreeWatchdog
    wd = FileTreeWatchdog()
    try:
        assert wd.watch("") is False
    finally:
        wd.stop()


def test_watch_starts_observer_on_real_dir(qapp, tmp_path):
    from Imervue.system.file_tree_watcher import FileTreeWatchdog
    wd = FileTreeWatchdog()
    try:
        ok = wd.watch(str(tmp_path))
        # Watchdog is in the requirements list so this should succeed
        assert ok is True
        assert wd.watched_path == str(tmp_path)
    finally:
        wd.stop()


def test_stop_is_idempotent(qapp, tmp_path):
    from Imervue.system.file_tree_watcher import FileTreeWatchdog
    wd = FileTreeWatchdog()
    wd.watch(str(tmp_path))
    wd.stop()
    wd.stop()  # second call must not raise
    assert wd.watched_path == ""


def test_watch_replaces_previous_root(qapp, tmp_path):
    from Imervue.system.file_tree_watcher import FileTreeWatchdog
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    wd = FileTreeWatchdog()
    try:
        wd.watch(str(a))
        wd.watch(str(b))
        assert wd.watched_path == str(b)
    finally:
        wd.stop()


def test_change_triggers_debounced_emit(qapp, tmp_path):
    """A real file change inside the watched root triggers _on_change."""
    from Imervue.system.file_tree_watcher import FileTreeWatchdog

    seen = {"count": 0}

    wd = FileTreeWatchdog()
    wd._changed.connect(lambda: seen.update(count=seen["count"] + 1))

    try:
        assert wd.watch(str(tmp_path)) is True
        # Create a file inside the watched root
        (tmp_path / "new_file.txt").write_text("hello")
        # Pump the Qt event loop briefly so cross-thread signals deliver
        deadline = time.monotonic() + 2.0
        while seen["count"] == 0 and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.05)
        assert seen["count"] >= 1
    finally:
        wd.stop()


def test_bind_model_is_optional(qapp, tmp_path):
    """No model bound → _do_refresh is a no-op even after a change."""
    from Imervue.system.file_tree_watcher import FileTreeWatchdog
    wd = FileTreeWatchdog()
    try:
        wd.watch(str(tmp_path))
        # Manually invoke _do_refresh — it must not raise without a model
        wd._do_refresh()
    finally:
        wd.stop()


def test_refresh_calls_set_root_path(qapp, tmp_path):
    """When a model is bound, _do_refresh re-roots it."""
    from Imervue.system.file_tree_watcher import FileTreeWatchdog

    model = _fake_model()
    wd = FileTreeWatchdog()
    wd.bind_model(model)
    try:
        wd.watch(str(tmp_path))
        wd._do_refresh()
    finally:
        wd.stop()
    # Implementation does setRootPath("") then setRootPath(path)
    actual = [c.args[0] for c in model.setRootPath.call_args_list]
    assert actual == ["", str(tmp_path)]


def test_debounce_collapses_many_events_into_one_refresh(qapp, tmp_path):
    """Bursts of events should fire _do_refresh at most once per debounce window."""
    from Imervue.system.file_tree_watcher import FileTreeWatchdog

    model = _fake_model()
    wd = FileTreeWatchdog()
    wd.bind_model(model)
    try:
        wd.watch(str(tmp_path))
        # Simulate a burst of 50 changes — debounce should collapse them
        for i in range(50):
            (tmp_path / f"f_{i}.txt").write_text("x")
        # Wait long enough for debounce + a margin
        deadline = time.monotonic() + 2.0
        while model.setRootPath.call_count == 0 and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.05)
        # Pump a bit more to catch any over-fire
        for _ in range(20):
            qapp.processEvents()
            time.sleep(0.02)
    finally:
        wd.stop()

    # Each refresh writes 2 entries (setRootPath("") + setRootPath(path)).
    # 50 distinct create events should NOT produce 50 refreshes — debounce
    # must collapse them. Allow up to ~5 refreshes total to be safe across OSes.
    assert 0 < model.setRootPath.call_count <= 10


def test_watch_replaces_model_safely(qapp, tmp_path):
    """Re-binding a model mid-watch must not crash on the next event."""
    from Imervue.system.file_tree_watcher import FileTreeWatchdog

    a, b = _fake_model(), _fake_model()
    wd = FileTreeWatchdog()
    try:
        wd.bind_model(a)
        wd.watch(str(tmp_path))
        wd.bind_model(b)
        # Manually trigger refresh — should target b, not a
        wd._do_refresh()
        assert b.setRootPath.call_count == 2  # setRootPath("") + setRootPath(path)
        assert a.setRootPath.call_count == 0
    finally:
        wd.stop()


def test_watchdog_handler_swallows_emitter_errors(qapp):
    """A failing signal emitter must NOT crash watchdog's poller thread."""
    from Imervue.system.file_tree_watcher import _WatchdogHandler

    def boom():
        raise RuntimeError("simulated")

    handler = _WatchdogHandler(boom)
    # Pass a fake event — it just gets ignored
    handler.on_any_event(object())  # must not raise
