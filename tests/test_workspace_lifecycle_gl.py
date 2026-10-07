"""Real windows preserve editing/recovery and retire resources through complete user flows."""
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest
from OpenGL import GL
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QMessageBox
from shiboken6 import isValid

from Imervue.Imervue_main_window import ImervueMainWindow
from Imervue.paint import auto_save, autosave_jobs

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture
def windows(qapp, monkeypatch, pump_until, record_property):
    # These flows use the core workspaces; loading a user's optional plugins or
    # onboarding would add unrelated dependencies/modal interactions.
    monkeypatch.setattr("Imervue.Imervue_main_window._init_plugin_system_example", lambda _: None)
    monkeypatch.setattr(ImervueMainWindow, "_maybe_show_whats_new", lambda _: None)
    opened = []

    def create():
        window = ImervueMainWindow()
        opened.append(window)
        window.show()
        assert pump_until(window.viewer.isValid)
        window.viewer.makeCurrent()
        try:
            record_property("gl_renderer", GL.glGetString(GL.GL_RENDERER).decode())
            assert GL.glGetError() == GL.GL_NO_ERROR
        finally:
            window.viewer.doneCurrent()
        return window

    yield create
    assert QThreadPool.globalInstance().waitForDone(10000)
    for window in reversed(opened):
        if not isValid(window):
            continue
        paint = getattr(window, "_paint", None)
        if paint is not None:
            paint.stop_autosave()
            jobs = getattr(paint, "_autosave_jobs", None)
            if jobs is not None and isValid(jobs):
                jobs.close()
        window._release_for_close()
        ImervueMainWindow._live_windows.discard(window)
        window.hide()
        window.deleteLater()


def _edit(workspace, value):
    workspace.canvas().document().layer_at(0).image.fill(value)
    workspace._on_dispatcher_commit()


def test_edit_switch_autosave_recover_and_cancel_close(windows, tmp_path, pump_until, monkeypatch):
    window = windows()
    window._main_tabs.setCurrentIndex(2)
    workspace = window.paint_workspace
    workspace.load_image(np.full((6, 7, 4), 17, dtype=np.uint8))
    first = workspace.canvas()
    first.document().add_layer(name="Overlay")
    first.document().add_layer_mask(0, fill=71)
    _edit(workspace, 31)
    first_stack = workspace._undo_stack
    second = workspace.new_tab(width=7, height=6)
    _edit(workspace, 99)
    documents = [first.document(), second.document()]
    workspace._autosave_target_dir = tmp_path
    for index in (0, 1, 0, 2):
        window._main_tabs.setCurrentIndex(index)
    assert [first.document(), second.document()] == documents
    workspace._tabs.setCurrentIndex(0)
    assert workspace._undo_stack is first_stack
    assert first_stack.undo() and first_stack.redo()
    assert first.document().layer_count == 2
    assert np.all(first.document().layer_at(0).mask == 71)
    window._main_tabs.setCurrentIndex(0)
    workspace._on_autosave_tick()
    assert pump_until(lambda: len(getattr(workspace, "_autosave_written", ())) == 2)
    assert workspace.canvas() is first
    assert sorted(int(auto_save.recover_snapshot(s).layer_at(0).image[0, 0, 0])
                  for s in workspace.pending_autosaves()) == [31, 99]
    monkeypatch.setattr(QMessageBox, "exec", lambda _: QMessageBox.StandardButton.Cancel)
    assert workspace.close_tab(0) is False
    assert workspace.tab_count() == 2 and workspace._tab_dirty[first]
    assert workspace.restore_all_autosaves() == 2
    assert workspace.tab_count() == 4 and first.document() is documents[0]


@pytest.mark.parametrize("error", [OSError("disk full"), PermissionError("read only")])
def test_failed_autosave_and_damaged_open_preserve_live_edits(
        windows, tmp_path, pump_until, monkeypatch, error):
    window = windows()
    window._main_tabs.setCurrentIndex(2)
    workspace = window.paint_workspace
    workspace.load_image(np.full((4, 5, 4), 7, dtype=np.uint8))
    _edit(workspace, 7)
    canvas, document = workspace.canvas(), workspace.canvas().document()
    workspace._autosave_target_dir = tmp_path / "snapshots"
    assert workspace.take_autosave_snapshot_now() is not None
    _edit(workspace, 42)
    warnings = []
    workspace.toast = SimpleNamespace(warning=warnings.append)

    def failed_write(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(autosave_jobs, "write_snapshot", failed_write)
    workspace._on_autosave_tick()
    assert pump_until(lambda: bool(warnings))
    assert canvas.document() is document and workspace._tab_dirty[canvas]
    assert int(document.layer_at(0).image[0, 0, 0]) == 42
    assert int(auto_save.recover_snapshot(workspace.pending_autosaves()[0])
               .layer_at(0).image[0, 0, 0]) == 7
    damaged = tmp_path / "damaged.png"
    damaged.write_bytes(b"broken image")
    window.viewer.model.images = [str(damaged)]
    window.viewer.current_index = 0
    errors = []
    window.toast = SimpleNamespace(error=errors.append)
    window._bind_paint_workspace_to_current_image()
    assert errors and workspace.canvas() is canvas
    assert workspace.tab_count() == 1 and canvas.document() is document
    assert workspace._tab_dirty[canvas]


def test_closing_tab_during_write_keeps_other_document_and_discards_late_output(
        windows, tmp_path, pump_until, monkeypatch):
    window = windows()
    window._main_tabs.setCurrentIndex(2)
    workspace = window.paint_workspace
    workspace.load_image(np.full((4, 5, 4), 17, dtype=np.uint8))
    _edit(workspace, 17)
    first = workspace.canvas()
    second = workspace.new_tab(width=5, height=4)
    _edit(workspace, 99)
    workspace._autosave_target_dir = tmp_path
    entered, release = Event(), Event()
    write = autosave_jobs.write_snapshot

    def blocked(document, **kwargs):
        entered.set()
        if not release.wait(10):
            raise TimeoutError("write was not released")
        return write(document, **kwargs)

    monkeypatch.setattr(autosave_jobs, "write_snapshot", blocked)
    try:
        workspace._on_autosave_tick()
        assert pump_until(entered.is_set)
        assert workspace.close_tab(0, force=True)
        release.set()
        assert pump_until(lambda: workspace._autosave_jobs._active is None)
        assert workspace.tab_count() == 1 and workspace.canvas() is second
        assert first not in workspace._autosave_records
        pending = workspace.pending_autosaves()
        assert len(pending) == 1
        assert int(auto_save.recover_snapshot(pending[0]).layer_at(0).image[0, 0, 0]) == 99
        for index in (1, 0, 2):
            window._main_tabs.setCurrentIndex(index)
        assert workspace.canvas() is second and workspace._tab_dirty[second]
    finally:
        release.set()
        assert QThreadPool.globalInstance().waitForDone(10000)


def test_secondary_window_close_releases_only_its_real_gl_textures(
        windows, pump_until, monkeypatch):
    first, second = windows(), windows()
    handles = []
    for index, window in enumerate((first, second)):
        viewer = window.viewer
        pixels = np.full((16, 16, 4), 80 + index * 10, dtype=np.uint8)
        with viewer._current_gl_context():
            assert viewer._ensure_tile_texture("fixture", pixels)
            texture = viewer.tile_textures["fixture"]
            assert GL.glIsTexture(texture)
            handles.append(texture)

    def unexpected_exit(_code):
        raise AssertionError("closing a secondary window must not terminate the app")

    monkeypatch.setattr("os._exit", unexpected_exit)
    first.close()
    assert pump_until(lambda: not isValid(first))
    assert second.isVisible() and second.viewer.isValid()
    with second.viewer._current_gl_context():
        assert GL.glIsTexture(handles[1])
        assert second.viewer.tile_textures["fixture"] == handles[1]
        second.viewer._delete_all_tile_textures()
        assert not GL.glIsTexture(handles[1])
        assert GL.glGetError() == GL.GL_NO_ERROR
