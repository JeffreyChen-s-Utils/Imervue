"""The file tree's Open in Explorer and Open Containing Folder go through ``reveal_or_warn``."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QFileSystemModel, QMenu

from Imervue.gui import file_tree_view as mod
from Imervue.multi_language.language_wrapper import language_wrapper


@pytest.fixture
def revealed(monkeypatch):
    calls: list = []
    monkeypatch.setattr(mod, "reveal_or_warn",
                        lambda path, *, select=True: calls.append((path, select)))
    return calls


@pytest.fixture
def tree(qapp, tmp_path):
    view = mod._FileTreeView(None)  # noqa: SLF001
    model = QFileSystemModel(view)
    model.setRootPath(str(tmp_path))
    view.setModel(model)
    yield view
    view.deleteLater()


def _choose(monkeypatch, key: str) -> None:
    """Make the tree's context menus pick the action labelled by *key* instead of opening."""
    class _PickingMenu(QMenu):
        def exec(self, *_args):
            text = language_wrapper.language_word_dict[key]
            next(action for action in self.actions() if action.text() == text).trigger()

    monkeypatch.setattr(mod, "QMenu", _PickingMenu)


def test_open_in_explorer_selects_the_file(tree, tmp_path, monkeypatch, revealed):
    photo = tmp_path / "a.png"
    photo.write_bytes(b"x")
    _choose(monkeypatch, "tree_open_in_explorer")
    tree._show_single_context_menu(str(photo), QPoint())  # noqa: SLF001
    assert revealed == [(str(photo), True)]


def test_open_containing_folder_opens_the_parent(tree, tmp_path, monkeypatch, revealed):
    photo = tmp_path / "a.png"
    photo.write_bytes(b"x")
    _choose(monkeypatch, "tree_open_folder")
    tree._show_single_context_menu(str(photo), QPoint())  # noqa: SLF001
    assert revealed == [(str(tmp_path), False)]


def test_a_multi_selection_reveals_its_first_path(tree, tmp_path, monkeypatch, revealed):
    paths = [str(tmp_path / "a.png"), str(tmp_path / "b.png")]
    _choose(monkeypatch, "tree_open_in_explorer")
    tree._show_multi_context_menu(paths, QPoint())  # noqa: SLF001
    assert revealed == [(paths[0], True)]
