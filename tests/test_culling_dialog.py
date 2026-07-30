"""Tests for the Culling dialog's reject-delete flow.

Deleting rejects is real disk I/O plus one library-index write per file, so
it runs on a :class:`FilePurgeWorker`. These tests drive the worker body
synchronously (``worker.run()`` via ``_drain``) so the post-delete state can
be asserted without spinning an event loop, and they keep the index in a
temp DB.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox, QWidget

from Imervue.gui.culling_dialog import CullingDialog
from Imervue.library import image_index


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


class _ToastSpy:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def success(self, msg):
        self.calls.append(("success", msg))

    def info(self, msg):
        self.calls.append(("info", msg))


class _FakeViewer:
    def __init__(self, images):
        self.model = type("M", (), {"images": list(images)})()
        self._unfiltered_images = None
        self.cleared = False
        self.loaded: list[str] | None = None

    def clear_tile_grid(self):
        self.cleared = True

    def load_tile_grid_async(self, paths):
        self.loaded = list(paths)


@pytest.fixture
def fake_ui(qapp):
    """A real QWidget that quacks like the main window for the dialog parent."""

    class _FakeUI(QWidget):
        pass

    ui = _FakeUI()
    ui.viewer = _FakeViewer([])
    ui.toast = _ToastSpy()
    ui.progress: list[tuple[int, int]] = []
    ui.show_progress = lambda done, total: ui.progress.append((done, total))
    return ui


def _make_images(tmp_path, count):
    paths = []
    for i in range(count):
        path = tmp_path / f"shot_{i}.png"
        path.write_bytes(b"x")
        paths.append(str(path))
    return paths


def _confirm_yes(monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **kw: QMessageBox.StandardButton.Yes,
    )


def _drain(dlg):
    """Run the pending worker's body inline, then let its slot fire."""
    worker = dlg._worker
    assert worker is not None, "no delete worker was started"
    worker.run()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_delete_rejects_removes_files_and_reloads_the_grid(
        qapp, fake_ui, tmp_path, monkeypatch):
    from pathlib import Path

    paths = _make_images(tmp_path, 4)
    for path in paths[:2]:
        image_index.set_cull_state(path, image_index.CULL_REJECT)
    fake_ui.viewer.model.images = paths
    _confirm_yes(monkeypatch)

    dlg = CullingDialog(fake_ui)
    dlg._delete_rejects()
    _drain(dlg)

    assert not Path(paths[0]).exists()
    assert not Path(paths[1]).exists()
    assert all(Path(p).exists() for p in paths[2:])
    # The grid is rebuilt from what survived.
    assert fake_ui.viewer.loaded == paths[2:]
    assert fake_ui.viewer.cleared is True
    assert fake_ui.viewer._unfiltered_images is None
    assert [kind for kind, _msg in fake_ui.toast.calls] == ["success"]
    dlg.deleteLater()


def test_delete_rejects_clears_the_index_rows(qapp, fake_ui, tmp_path, monkeypatch):
    paths = _make_images(tmp_path, 2)
    for path in paths:
        image_index.set_cull_state(path, image_index.CULL_REJECT)
    fake_ui.viewer.model.images = paths
    _confirm_yes(monkeypatch)

    dlg = CullingDialog(fake_ui)
    dlg._delete_rejects()
    _drain(dlg)

    # Every deleted path is unflagged again, in one transaction.
    assert image_index.filter_by_cull(paths, "reject") == []
    dlg.deleteLater()


def test_delete_rejects_reports_progress(qapp, fake_ui, tmp_path, monkeypatch):
    paths = _make_images(tmp_path, 3)
    for path in paths:
        image_index.set_cull_state(path, image_index.CULL_REJECT)
    fake_ui.viewer.model.images = paths
    _confirm_yes(monkeypatch)

    dlg = CullingDialog(fake_ui)
    dlg._delete_rejects()
    _drain(dlg)

    assert fake_ui.progress[-1] == (3, 3)
    dlg.deleteLater()


# ---------------------------------------------------------------------------
# Guards and edge cases
# ---------------------------------------------------------------------------


def test_no_rejects_starts_no_worker(qapp, fake_ui, tmp_path, monkeypatch):
    fake_ui.viewer.model.images = _make_images(tmp_path, 2)
    seen: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a, **kw: seen.append("info"))

    dlg = CullingDialog(fake_ui)
    dlg._delete_rejects()

    assert dlg._worker is None
    assert seen == ["info"]
    dlg.deleteLater()


def test_declining_the_confirmation_deletes_nothing(
        qapp, fake_ui, tmp_path, monkeypatch):
    from pathlib import Path

    paths = _make_images(tmp_path, 2)
    for path in paths:
        image_index.set_cull_state(path, image_index.CULL_REJECT)
    fake_ui.viewer.model.images = paths
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **kw: QMessageBox.StandardButton.No,
    )

    dlg = CullingDialog(fake_ui)
    dlg._delete_rejects()

    assert dlg._worker is None
    assert all(Path(p).exists() for p in paths)
    dlg.deleteLater()


def test_second_delete_is_ignored_while_one_is_running(
        qapp, fake_ui, tmp_path, monkeypatch):
    paths = _make_images(tmp_path, 2)
    for path in paths:
        image_index.set_cull_state(path, image_index.CULL_REJECT)
    fake_ui.viewer.model.images = paths
    _confirm_yes(monkeypatch)

    dlg = CullingDialog(fake_ui)
    dlg._delete_rejects()
    first = dlg._worker
    dlg._delete_rejects()

    assert dlg._worker is first
    _drain(dlg)
    dlg.deleteLater()


def test_missing_reject_file_does_not_fail_the_batch(
        qapp, fake_ui, tmp_path, monkeypatch):
    from pathlib import Path

    paths = _make_images(tmp_path, 2)
    gone = str(tmp_path / "already_gone.png")
    for path in [*paths, gone]:
        image_index.set_cull_state(path, image_index.CULL_REJECT)
    fake_ui.viewer.model.images = [*paths, gone]
    _confirm_yes(monkeypatch)

    dlg = CullingDialog(fake_ui)
    dlg._delete_rejects()
    _drain(dlg)

    assert all(not Path(p).exists() for p in paths)
    # The vanished path counts as gone too — it must not survive in the grid.
    assert fake_ui.viewer.loaded == []
    assert image_index.filter_by_cull([*paths, gone], "reject") == []
    dlg.deleteLater()


def test_undeletable_reject_keeps_its_tile_and_flag(
        qapp, fake_ui, tmp_path, monkeypatch):
    from pathlib import Path

    paths = _make_images(tmp_path, 1)
    stubborn = tmp_path / "locked_dir"   # a directory can't be unlinked
    stubborn.mkdir()
    rejects = [*paths, str(stubborn)]
    for path in rejects:
        image_index.set_cull_state(path, image_index.CULL_REJECT)
    fake_ui.viewer.model.images = rejects
    _confirm_yes(monkeypatch)

    dlg = CullingDialog(fake_ui)
    dlg._delete_rejects()
    _drain(dlg)

    assert not Path(paths[0]).exists()
    assert stubborn.exists()
    assert fake_ui.viewer.loaded == [str(stubborn)]
    assert image_index.filter_by_cull(rejects, "reject") == [str(stubborn)]
    dlg.deleteLater()
