"""Paint handoff preserves edits, using real documents without GL widgets."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.Imervue_main_window import ImervueMainWindow
from Imervue.gpu_image_view.images import image_loader
from Imervue.paint.document import PaintDocument
from Imervue.paint.undo_stack import UndoStack


class _Workspace:
    """A document host whose replacement semantics match PaintWorkspace."""

    def __init__(self):
        self.documents = []
        self.new_tab(width=8, height=8)
        self.dirty = True

    def new_tab(self, *, width, height):
        self.document = PaintDocument()
        self.document.load_image(np.zeros((height, width, 4), dtype=np.uint8))
        self.documents.append(self.document)
        self.stack = UndoStack(self.document)

    def load_image(self, arr, *, source_path=""):
        self.source_path = source_path
        self.document = PaintDocument()
        self.document.load_image(
            np.zeros((8, 8, 4), dtype=np.uint8) if arr is None else arr,
        )
        self.documents[-1] = self.document
        self.stack = UndoStack(self.document)
        self.dirty = False


class _Window:
    _on_main_tab_changed = ImervueMainWindow._on_main_tab_changed
    _bind_paint_workspace_to_current_image = (
        ImervueMainWindow._bind_paint_workspace_to_current_image
    )
    _navigate_paint_image = ImervueMainWindow._navigate_paint_image

    def __init__(self, images, index=0):
        self.viewer = SimpleNamespace(model=SimpleNamespace(images=images), current_index=index)
        self.paint_workspace = _Workspace()
        self._folder_tab_shortcuts = []
        self._build_optional_tab_on_open = lambda _idx: None
        self.exif_sidebar = SimpleNamespace(update_info=lambda: None, schedule_update=lambda: None)
        self._main_tabs = SimpleNamespace(setCurrentIndex=lambda idx: self.tab_changes.append(idx))
        self.tab_changes = []
        self.errors = []
        self.toast = SimpleNamespace(error=self.errors.append)


@pytest.fixture
def window(tmp_path):
    return _Window([str(tmp_path / "a.png"), str(tmp_path / "b.png")])


def test_returning_to_paint_after_browsing_keeps_document_and_history(window, monkeypatch):
    monkeypatch.setattr(image_loader, "decode_image_file",
                        lambda _path: np.ones((8, 8, 4), dtype=np.uint8))
    workspace = window.paint_workspace
    document = workspace.document
    document.add_layer(name="drawing")
    stack = workspace.stack = UndoStack(document)
    document.active_layer().image[1, 2] = (20, 30, 40, 255)
    stack.commit()
    window._on_main_tab_changed(0)
    window.viewer.current_index = 1
    window._on_main_tab_changed(2)
    assert workspace.document is document
    assert workspace.stack is stack
    assert workspace.dirty is True
    assert document.layer_count == 2
    np.testing.assert_array_equal(document.active_layer().image[1, 2], (20, 30, 40, 255))
    assert stack.undo() is True
    np.testing.assert_array_equal(document.active_layer().image[1, 2], (0, 0, 0, 0))


def test_explicit_handoff_opens_a_new_document(window, monkeypatch):
    image = np.full((6, 10, 4), 123, dtype=np.uint8)
    monkeypatch.setattr(image_loader, "decode_image_file", lambda _path: image)
    original = window.paint_workspace.document
    window._bind_paint_workspace_to_current_image()
    workspace = window.paint_workspace
    assert workspace.document is not original
    assert len(workspace.documents) == 2
    np.testing.assert_array_equal(workspace.document.layer_at(0).image, image)
    assert workspace.documents[0] is original
    assert window.tab_changes == [2]
    assert workspace.source_path == window.viewer.model.images[0]


@pytest.mark.parametrize(("images", "index"), [([], 0), (["a.png"], -1), (["a.png"], 1)])
def test_missing_current_image_does_not_reset_paint(images, index):
    window = _Window(images, index)
    original, stack = window.paint_workspace.document, window.paint_workspace.stack
    window._bind_paint_workspace_to_current_image()
    assert window.paint_workspace.document is original
    assert window.paint_workspace.stack is stack
    assert window.paint_workspace.dirty is True
    assert window.tab_changes == []


def test_failed_decode_preserves_paint_and_reports_error(window, monkeypatch):
    def fail(_path):
        raise OSError("unreadable image")

    monkeypatch.setattr(image_loader, "decode_image_file", fail)
    original, stack = window.paint_workspace.document, window.paint_workspace.stack
    window._bind_paint_workspace_to_current_image()
    assert window.paint_workspace.document is original
    assert window.paint_workspace.stack is stack
    assert window.paint_workspace.dirty is True
    assert window.tab_changes == []
    assert len(window.errors) == 1
    assert "unreadable image" in window.errors[0]


@pytest.mark.parametrize("direction", [-1, 1])
def test_paint_navigation_keeps_the_previous_document(window, monkeypatch, direction):
    from Imervue.gpu_image_view.actions import select

    def navigate(*, main_gui):
        main_gui.current_index = 1

    monkeypatch.setattr(select, "switch_to_next_image", navigate)
    monkeypatch.setattr(select, "switch_to_previous_image", navigate)
    monkeypatch.setattr(image_loader, "decode_image_file",
                        lambda _path: np.ones((8, 8, 4), dtype=np.uint8))
    original = window.paint_workspace.document
    window._navigate_paint_image(direction)
    assert window.paint_workspace.documents[0] is original
    assert window.paint_workspace.document is not original


def test_paint_handoff_menu_calls_the_window(qapp):
    from PySide6.QtWidgets import QMenu

    from Imervue.menu.file_menu import _add_open_entries
    from Imervue.multi_language.language_wrapper import language_wrapper

    calls = []
    window = SimpleNamespace(_bind_paint_workspace_to_current_image=lambda: calls.append("paint"))
    menu = QMenu()
    _add_open_entries(window, menu, language_wrapper.language_word_dict)
    action = next(a for a in menu.actions() if a.objectName() == "file.open_in_paint")
    action.trigger()
    assert calls == ["paint"]
