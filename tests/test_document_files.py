"""Native save/close flow with real Qt tabs and real document bundles, without GL."""
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTabWidget, QWidget

from Imervue.paint import document_io
from Imervue.paint.document import PaintDocument
from Imervue.paint.document_files import native_path
from Imervue.paint.document_status import document_status
from Imervue.paint.file_menu import _FileMenuBridge
from Imervue.paint.workspace_tabs import TabManagerMixin


class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self._doc = PaintDocument()
        self._doc.load_image(np.full((3, 4, 4), 31, dtype=np.uint8))

    def document(self):
        return self._doc

    def set_document(self, doc):
        self._doc = doc


class Host(QWidget, TabManagerMixin):
    def __init__(self):
        QWidget.__init__(self)
        self._tabs = QTabWidget(self)
        self._tab_dirty = {}
        self.toasts = []
        self.toast = SimpleNamespace(success=self.toasts.append, error=self.toasts.append)
        self.new_tab()
        self._file_menu_bridge = _FileMenuBridge(self)
        self._file_menu_bridge.refresh_recent_menu = lambda: None

    def new_tab(self, **_kwargs):
        self._canvas = Canvas()
        self._tabs.addTab(self._canvas, f"Untitled-{self._tabs.count() + 1}")
        self._tabs.setCurrentWidget(self._canvas)
        self._tab_dirty[self._canvas] = True
        return self._canvas

    def canvas(self):
        return self._canvas

    def _refresh_status_line(self):
        pass

    def _ensure_undo_stack(self):
        pass


@pytest.fixture
def host(qapp):
    workspace = Host()
    yield workspace
    workspace.deleteLater()


@pytest.mark.parametrize(("path", "expected"), [
    ("paint", "paint.imervue"), ("paint.jpg", "paint.jpg.imervue"),
    ("paint.IMERVUE", "paint.IMERVUE"),
])
def test_native_suffix_does_not_destroy_raster_source(path, expected):
    assert native_path(path) == expected


def test_save_all_preserves_layers_masks_selection_and_active_tab(host, tmp_path, monkeypatch):
    first = host.canvas()
    first.document().add_layer(name="Overlay")
    first.document().add_layer_mask(0, fill=71)
    first.document().set_selection(np.ones((3, 4), dtype=bool))
    second = host.new_tab()
    paths = iter([str(tmp_path / "first"), str(tmp_path / "second.imervue")])
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: (next(paths), ""))
    assert host._file_menu_bridge.save_all_documents()
    assert host.canvas() is second and host._tabs.currentWidget() is second
    assert not host._has_unsaved_tabs()
    saved = document_io.load_document(tmp_path / "first.imervue")
    assert saved.layer_count == 2 and np.all(saved.layer_at(0).mask == 71)
    assert saved.selection() is not None
    assert document_status(first).saved_format == "imervue"
    assert "first.imervue" in host._tabs.tabToolTip(0)
    # Resaving to the known native destination never prompts again.
    host._set_tab_dirty(first, True)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: pytest.fail("unexpected picker"))
    assert host._file_menu_bridge.save_document(first)


@pytest.mark.parametrize("failure", ["cancel", "disk", "permission", "invalid", "memory"])
def test_save_all_stops_after_partial_success_without_closing_remaining_tabs(
        host, tmp_path, monkeypatch, failure):
    first, second = host.canvas(), host.new_tab()
    paths = iter([str(tmp_path / "first.imervue"),
                  "" if failure == "cancel" else str(tmp_path / "second.imervue")])
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: (next(paths), ""))
    write = document_io.save_document

    def save(doc, path):
        if doc is second.document():
            errors = {"disk": OSError("disk full"), "permission": PermissionError("read only"),
                      "invalid": ValueError("invalid document"), "memory": MemoryError("memory")}
            raise errors[failure]
        write(doc, path)

    monkeypatch.setattr(document_io, "save_document", save)
    assert not host._file_menu_bridge.save_all_documents()
    assert not host._tab_dirty[first] and host._tab_dirty[second]
    assert host._tabs.count() == 2 and host.canvas() is second
    assert (tmp_path / "first.imervue").exists()
    assert not document_status(second).saved_path


def test_duplicate_destination_cannot_replace_another_open_document(host, tmp_path, monkeypatch):
    first = host.canvas()
    host.new_tab()
    target = str(tmp_path / "one.imervue")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: (target, ""))
    assert not host._file_menu_bridge.save_all_documents()
    assert not host._tab_dirty[first] and host._tab_dirty[host.canvas()]
    assert host.toasts


@pytest.mark.parametrize("all_tabs", [False, True])
def test_close_save_targets_non_active_tab_or_all_dirty_documents(host, tmp_path, monkeypatch, all_tabs):
    first, second = host.canvas(), host.new_tab()
    picked = iter([str(tmp_path / "first.imervue"), str(tmp_path / "second.imervue")])
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: (next(picked), ""))
    monkeypatch.setattr(QMessageBox, "exec", lambda _: 0)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda box: box.buttons()[0])
    if all_tabs:
        assert host._confirm_discard_all_unsaved()
        assert not host._has_unsaved_tabs()
    else:
        assert host._confirm_discard_unsaved(first)
        assert not host._tab_dirty[first] and host._tab_dirty[second]
    assert host.canvas() is second and host._tabs.count() == 2


def test_open_native_preserves_existing_edits_and_failed_open_creates_no_tab(host, tmp_path):
    first = host.canvas()
    target = tmp_path / "original.imervue"
    document_io.save_document(first.document(), target)
    assert host._file_menu_bridge.open_document_at(str(target))
    second = host.canvas()
    assert second is not first and host._tab_dirty[first] and not host._tab_dirty[second]
    assert document_status(second).source == str(target)
    assert not host._file_menu_bridge.open_document_at(str(tmp_path / "missing.imervue"))
    assert host._tabs.count() == 2 and host.canvas() is second


def test_empty_document_and_picker_cancel_do_not_claim_saved(host, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_: ("", ""))
    assert not host._file_menu_bridge.open_document()
    host.canvas().set_document(PaintDocument())
    assert not host._file_menu_bridge.save_document()
    assert host._tab_dirty[host.canvas()] and not document_status(host.canvas()).saved_path


@pytest.mark.parametrize("error", [OSError("read error"), ValueError("damaged"), MemoryError("memory")])
def test_open_failure_never_changes_existing_document(host, monkeypatch, error):
    canvas = host.canvas()

    def fail(_path):
        raise error

    monkeypatch.setattr(document_io, "load_document", fail)
    assert not host._file_menu_bridge.open_document_at("damaged.imervue")
    assert host.canvas() is canvas and host._tabs.count() == 1 and host._tab_dirty[canvas]
    assert str(error) in host.toasts[-1]


def test_save_as_selects_new_destination_and_never_changes_source(host, tmp_path, monkeypatch):
    state = document_status(host.canvas())
    state.source = "camera.jpg"
    state.saved_path, state.saved_format = str(tmp_path / "previous.imervue"), "imervue"
    target = str(tmp_path / "new.imervue")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: (target, ""))
    assert host._file_menu_bridge.save_document_as()
    assert state.saved_path == target and state.source == "camera.jpg"
    assert not (tmp_path / "previous.imervue").exists()
