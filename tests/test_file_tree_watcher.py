"""Tests for the recursive file-tree watchdog."""
from __future__ import annotations

import time


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

    calls: list[str] = []

    class FakeModel:
        def setRootPath(self, p):
            calls.append(p)

    wd = FileTreeWatchdog()
    wd.bind_model(FakeModel())
    try:
        wd.watch(str(tmp_path))
        wd._do_refresh()
    finally:
        wd.stop()
    # Implementation does setRootPath("") then setRootPath(path)
    assert calls == ["", str(tmp_path)]
