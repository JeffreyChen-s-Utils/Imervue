"""Contracts of the Tags & Albums dialog and its right-click submenus.

Pins the visible state of both tabs (row labels, counts, greyed missing files,
selection kept after removing images), every create / rename / delete answer
path, what reaches the viewer from "Show in Viewer" / "View Album" and the
double-click opener, and the checked state, separator and toast of each
context-menu action, so the dialog can be split into sibling modules without
changing what the user sees.
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QListWidgetItem, QMenu

from Imervue.gui import tag_album_dialog as mod
from Imervue.user_settings.user_setting_dict import user_setting_dict

_ROLE = Qt.ItemDataRole.UserRole


class _Viewer:
    """Records what the dialog asks of the image viewer."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.toasts: list[str] = []
        self.main_window = SimpleNamespace(
            toast=SimpleNamespace(info=self.toasts.append))

    def clear_tile_grid(self) -> None:
        self.calls.append(("clear",))

    def load_tile_grid_async(self, images) -> None:
        self.calls.append(("load", list(images)))


@pytest.fixture
def store(monkeypatch):
    for key in ("image_tags", "albums"):
        monkeypatch.setitem(user_setting_dict, key, {})
    return user_setting_dict


@pytest.fixture
def dialog(qapp, store, monkeypatch):
    viewer = _Viewer()
    monkeypatch.setattr(mod.TagAlbumDialog, "close", lambda self: viewer.calls.append(("close",)))
    dlg = mod.TagAlbumDialog(SimpleNamespace(
        main_window=None, clear_tile_grid=viewer.clear_tile_grid,
        load_tile_grid_async=viewer.load_tile_grid_async))
    yield dlg, viewer
    dlg.deleteLater()


def _answer(monkeypatch, text: str, ok: bool = True) -> list:
    asked = []

    def fake(*args, **kwargs):
        asked.append((args, kwargs))
        return text, ok
    monkeypatch.setattr(QInputDialog, "getText", fake)
    return asked


def _confirm(monkeypatch, answer: bool) -> list:
    """Answer the shared yes/no question wherever the dialog's modules import it."""
    questions = []
    for name in ("tag_album_dialog", "tag_album_tags", "tag_album_albums"):
        try:
            module = importlib.import_module(f"Imervue.gui.{name}")
        except ImportError:
            continue
        if hasattr(module, "confirm"):
            monkeypatch.setattr(module, "confirm",
                                lambda _p, title, q: questions.append((title, q)) or answer)
    return questions


def _rows(widget) -> list[tuple[str, str]]:
    return [(widget.item(i).text(), widget.item(i).data(_ROLE)) for i in range(widget.count())]


def _select(widget, name: str) -> None:
    widget.setCurrentRow(next(i for i in range(widget.count())
                              if widget.item(i).data(_ROLE) == name))


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_the_dialog_lists_both_collections_sorted_with_counts(qapp, store):
    store["image_tags"] = {"b": ["1", "2"], "A": []}
    store["albums"] = {"Trip": ["x"]}
    dlg = mod.TagAlbumDialog(SimpleNamespace(main_window=None))
    try:
        assert dlg.windowTitle() == "Tags & Albums"
        assert dlg._tabs.count() == 2  # noqa: SLF001
        assert [dlg._tabs.tabText(i) for i in range(2)] == ["Tags", "Albums"]  # noqa: SLF001
        assert _rows(dlg._tag_list) == [("A  (0)", "A"), ("b  (2)", "b")]  # noqa: SLF001
        assert dlg._tag_count.text() == "2 tag(s)"  # noqa: SLF001
        assert _rows(dlg._album_list) == [("Trip  (1)", "Trip")]  # noqa: SLF001
        assert dlg._album_count.text() == "1 album(s)"  # noqa: SLF001
        assert dlg._tag_image_list.count() == 0  # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_the_tab_mixins_come_before_qdialog():
    from PySide6.QtWidgets import QDialog

    from Imervue.gui.tag_album_albums import AlbumTabMixin
    from Imervue.gui.tag_album_tags import TagTabMixin
    mro = mod.TagAlbumDialog.__mro__
    assert mro.index(TagTabMixin) < mro.index(AlbumTabMixin) < mro.index(QDialog)


def test_the_submenu_builders_are_reexported():
    from Imervue.gui import tag_album_menus
    for name in ("build_tag_submenu", "build_album_submenu", "build_batch_tag_album_submenu"):
        assert getattr(mod, name) is getattr(tag_album_menus, name)
        assert name in mod.__all__


def test_open_tag_album_dialog_execs_the_dialog(monkeypatch):
    built = []

    class _Fake:
        def __init__(self, gui):
            built.append(gui)

        def exec(self):
            built.append("exec")
    monkeypatch.setattr(mod, "TagAlbumDialog", _Fake)
    mod.open_tag_album_dialog("gui")
    assert built == ["gui", "exec"]


# ---------------------------------------------------------------------------
# Tags tab
# ---------------------------------------------------------------------------

def test_selecting_a_tag_lists_its_images_and_greys_missing_ones(dialog, store, tmp_path):
    dlg, _viewer = dialog
    kept = tmp_path / "kept.jpg"
    kept.write_bytes(b"x")
    gone = str(tmp_path / "gone.jpg")
    store["image_tags"] = {"T": [str(kept), gone]}
    dlg._refresh_tags()  # noqa: SLF001
    _select(dlg._tag_list, "T")  # noqa: SLF001
    images = dlg._tag_image_list  # noqa: SLF001
    assert [images.item(i).text() for i in range(images.count())] == [str(kept), gone]
    assert images.item(1).foreground().color() == Qt.GlobalColor.gray
    assert images.item(0).foreground().color() != Qt.GlobalColor.gray
    dlg._on_tag_selected(None, None)  # noqa: SLF001
    assert images.count() == 0


@pytest.mark.parametrize(("text", "ok"), [("", True), ("   ", True), ("New", False)])
def test_create_tag_ignores_blank_or_cancelled_answers(dialog, store, monkeypatch, text, ok):
    dlg, _ = dialog
    _answer(monkeypatch, text, ok)
    dlg._create_tag()  # noqa: SLF001
    assert store["image_tags"] == {}


def test_create_tag_adds_a_stripped_row(dialog, store, monkeypatch):
    dlg, _ = dialog
    _answer(monkeypatch, " Sea ")
    dlg._create_tag()  # noqa: SLF001
    assert _rows(dlg._tag_list) == [("Sea  (0)", "Sea")]  # noqa: SLF001


def test_rename_tag_without_a_selection_asks_nothing(dialog, monkeypatch):
    dlg, _ = dialog
    asked = _answer(monkeypatch, "x")
    dlg._rename_tag()  # noqa: SLF001
    assert asked == []


@pytest.mark.parametrize(("text", "ok"), [("Old", True), ("", True), ("Other", False)])
def test_rename_tag_keeps_the_name_on_same_blank_or_cancel(dialog, store, monkeypatch, text, ok):
    dlg, _ = dialog
    store["image_tags"] = {"Old": ["p"]}
    dlg._refresh_tags()  # noqa: SLF001
    _select(dlg._tag_list, "Old")  # noqa: SLF001
    asked = _answer(monkeypatch, text, ok)
    dlg._rename_tag()  # noqa: SLF001
    assert asked[0][1] == {"text": "Old"}
    assert store["image_tags"] == {"Old": ["p"]}


def test_rename_tag_renames_and_refreshes(dialog, store, monkeypatch):
    dlg, _ = dialog
    store["image_tags"] = {"Old": ["p"]}
    dlg._refresh_tags()  # noqa: SLF001
    _select(dlg._tag_list, "Old")  # noqa: SLF001
    _answer(monkeypatch, " New ")
    dlg._rename_tag()  # noqa: SLF001
    assert store["image_tags"] == {"New": ["p"]}
    assert _rows(dlg._tag_list) == [("New  (1)", "New")]  # noqa: SLF001


@pytest.mark.parametrize("answer", [True, False])
def test_delete_tag_follows_the_confirmation(dialog, store, monkeypatch, answer):
    dlg, _ = dialog
    store["image_tags"] = {"T": []}
    dlg._refresh_tags()  # noqa: SLF001
    _select(dlg._tag_list, "T")  # noqa: SLF001
    questions = _confirm(monkeypatch, answer)
    dlg._delete_tag()  # noqa: SLF001
    assert questions == [("Delete Tag", "Delete tag 'T'?")]
    assert ("T" in store["image_tags"]) is not answer
    assert dlg._tag_list.count() == (0 if answer else 1)  # noqa: SLF001


def test_delete_tag_without_a_selection_asks_nothing(dialog, monkeypatch):
    dlg, _ = dialog
    questions = _confirm(monkeypatch, True)
    dlg._delete_tag()  # noqa: SLF001
    assert questions == []


def test_removing_images_from_a_tag_keeps_it_selected(dialog, store):
    dlg, _ = dialog
    store["image_tags"] = {"A": ["z"], "T": ["1", "2", "3"]}
    dlg._refresh_tags()  # noqa: SLF001
    _select(dlg._tag_list, "T")  # noqa: SLF001
    dlg._tag_image_list.item(0).setSelected(True)  # noqa: SLF001
    dlg._tag_image_list.item(2).setSelected(True)  # noqa: SLF001
    dlg._remove_image_from_tag()  # noqa: SLF001
    assert store["image_tags"]["T"] == ["2"]
    assert dlg._tag_list.currentItem().data(_ROLE) == "T"  # noqa: SLF001
    assert dlg._tag_image_list.count() == 1  # noqa: SLF001


def test_removing_the_last_image_drops_the_tag_and_the_selection(dialog, store):
    dlg, _ = dialog
    store["image_tags"] = {"T": ["1"]}
    dlg._refresh_tags()  # noqa: SLF001
    _select(dlg._tag_list, "T")  # noqa: SLF001
    dlg._tag_image_list.item(0).setSelected(True)  # noqa: SLF001
    dlg._remove_image_from_tag()  # noqa: SLF001
    assert store["image_tags"] == {}
    assert dlg._tag_list.currentItem() is None  # noqa: SLF001


def test_remove_and_filter_need_a_selected_tag(dialog, store):
    dlg, viewer = dialog
    store["image_tags"] = {"T": ["1"]}
    dlg._refresh_tags()  # noqa: SLF001
    dlg._remove_image_from_tag()  # noqa: SLF001
    dlg._filter_by_tag()  # noqa: SLF001
    assert store["image_tags"] == {"T": ["1"]} and viewer.calls == []


def test_show_in_viewer_loads_only_existing_files_then_closes(dialog, store, tmp_path):
    dlg, viewer = dialog
    kept = tmp_path / "kept.jpg"
    kept.write_bytes(b"x")
    store["image_tags"] = {"T": [str(tmp_path / "gone.jpg"), str(kept)], "Empty": ["nope"]}
    dlg._refresh_tags()  # noqa: SLF001
    _select(dlg._tag_list, "Empty")  # noqa: SLF001
    dlg._filter_by_tag()  # noqa: SLF001
    assert viewer.calls == []
    _select(dlg._tag_list, "T")  # noqa: SLF001
    dlg._filter_by_tag()  # noqa: SLF001
    assert viewer.calls == [("clear",), ("load", [str(kept)]), ("close",)]


@pytest.mark.parametrize("opener", ["_open_tag_image", "_open_album_image"])
def test_double_click_opens_only_an_existing_file(dialog, monkeypatch, tmp_path, opener):
    dlg, viewer = dialog
    from Imervue.gpu_image_view.images import image_loader
    opened = []
    monkeypatch.setattr(image_loader, "open_path",
                        lambda main_gui, path: opened.append((main_gui, path)))
    getattr(dlg, opener)(QListWidgetItem(str(tmp_path / "gone.jpg")))
    assert opened == [] and viewer.calls == []
    kept = tmp_path / "kept.jpg"
    kept.write_bytes(b"x")
    getattr(dlg, opener)(QListWidgetItem(str(kept)))
    assert opened == [(dlg.main_gui, str(kept))]
    assert viewer.calls == [("clear",), ("close",)]


# ---------------------------------------------------------------------------
# Albums tab
# ---------------------------------------------------------------------------

def test_selecting_an_album_lists_its_images_and_greys_missing_ones(dialog, store, tmp_path):
    dlg, _ = dialog
    kept = tmp_path / "kept.jpg"
    kept.write_bytes(b"x")
    gone = str(tmp_path / "gone.jpg")
    store["albums"] = {"A": [gone, str(kept)]}
    dlg._refresh_albums()  # noqa: SLF001
    _select(dlg._album_list, "A")  # noqa: SLF001
    images = dlg._album_image_list  # noqa: SLF001
    assert [images.item(i).text() for i in range(images.count())] == [gone, str(kept)]
    assert images.item(0).foreground().color() == Qt.GlobalColor.gray
    dlg._on_album_selected(None, None)  # noqa: SLF001
    assert images.count() == 0


@pytest.mark.parametrize(("text", "ok", "expected"), [
    (" Trip ", True, {"Trip": []}), ("  ", True, {}), ("Trip", False, {}),
])
def test_create_album(dialog, store, monkeypatch, text, ok, expected):
    dlg, _ = dialog
    _answer(monkeypatch, text, ok)
    dlg._create_album()  # noqa: SLF001
    assert store["albums"] == expected
    assert dlg._album_count.text() == f"{len(expected)} album(s)"  # noqa: SLF001


def test_rename_album_paths(dialog, store, monkeypatch):
    dlg, _ = dialog
    asked = _answer(monkeypatch, "x")
    dlg._rename_album()  # noqa: SLF001
    assert asked == []
    store["albums"] = {"Old": []}
    dlg._refresh_albums()  # noqa: SLF001
    _select(dlg._album_list, "Old")  # noqa: SLF001
    _answer(monkeypatch, "Old")
    dlg._rename_album()  # noqa: SLF001
    assert store["albums"] == {"Old": []}
    _answer(monkeypatch, "New", ok=False)
    dlg._rename_album()  # noqa: SLF001
    assert store["albums"] == {"Old": []}
    _answer(monkeypatch, " New ")
    dlg._rename_album()  # noqa: SLF001
    assert store["albums"] == {"New": []}


@pytest.mark.parametrize("answer", [True, False])
def test_delete_album_follows_the_confirmation(dialog, store, monkeypatch, answer):
    dlg, _ = dialog
    store["albums"] = {"A": []}
    dlg._refresh_albums()  # noqa: SLF001
    questions = _confirm(monkeypatch, answer)
    dlg._delete_album()  # noqa: SLF001
    assert questions == []
    _select(dlg._album_list, "A")  # noqa: SLF001
    dlg._delete_album()  # noqa: SLF001
    assert questions == [("Delete Album", "Delete album 'A'?")]
    assert ("A" in store["albums"]) is not answer


def test_removing_images_from_an_album_keeps_it_selected(dialog, store):
    dlg, _ = dialog
    store["albums"] = {"A": ["1", "2"], "B": []}
    dlg._refresh_albums()  # noqa: SLF001
    dlg._remove_image_from_album()  # noqa: SLF001
    assert store["albums"]["A"] == ["1", "2"]
    _select(dlg._album_list, "A")  # noqa: SLF001
    for i in range(2):
        dlg._album_image_list.item(i).setSelected(True)  # noqa: SLF001
    dlg._remove_image_from_album()  # noqa: SLF001
    assert store["albums"] == {"A": [], "B": []}
    assert dlg._album_list.currentItem().data(_ROLE) == "A"  # noqa: SLF001
    assert _rows(dlg._album_list) == [("A  (0)", "A"), ("B  (0)", "B")]  # noqa: SLF001


def test_view_album_loads_only_existing_files_then_closes(dialog, store, tmp_path):
    dlg, viewer = dialog
    dlg._view_album()  # noqa: SLF001
    kept = tmp_path / "kept.jpg"
    kept.write_bytes(b"x")
    store["albums"] = {"A": [str(kept), str(tmp_path / "gone.jpg")], "Gone": ["nope"]}
    dlg._refresh_albums()  # noqa: SLF001
    _select(dlg._album_list, "Gone")  # noqa: SLF001
    dlg._view_album()  # noqa: SLF001
    assert viewer.calls == []
    _select(dlg._album_list, "A")  # noqa: SLF001
    dlg._view_album()  # noqa: SLF001
    assert viewer.calls == [("clear",), ("load", [str(kept)]), ("close",)]


# ---------------------------------------------------------------------------
# Context-menu helpers
# ---------------------------------------------------------------------------

def _actions(menu: QMenu) -> list[tuple[str, bool, bool]]:
    return [(a.text(), a.isCheckable(), a.isChecked()) for a in menu.actions()]


def test_tag_submenu_checks_the_image_tags_and_toggles(qapp, store):
    store["image_tags"] = {"b": ["p"], "a": []}
    viewer = _Viewer()
    parent = QMenu()
    mod.build_tag_submenu(viewer, "p", parent)
    sub = parent.actions()[0].menu()
    assert parent.actions()[0].text() == "Tags"
    assert _actions(sub) == [("a", True, False), ("b", True, True), ("", False, False),
                             ("+ New Tag...", False, False)]
    assert sub.actions()[2].isSeparator()
    sub.actions()[1].trigger()
    sub.actions()[0].trigger()
    assert store["image_tags"] == {"a": ["p"]}
    assert viewer.toasts == ["Removed from 'b'", "Tagged 'a'"]
    parent.deleteLater()


def test_empty_submenus_have_no_separator(qapp, store):
    viewer = _Viewer()
    parent = QMenu()
    mod.build_tag_submenu(viewer, "p", parent)
    mod.build_album_submenu(viewer, "p", parent)
    menus = [a.menu() for a in parent.actions()]
    assert [_actions(m) for m in menus] == [[("+ New Tag...", False, False)],
                                            [("+ New Album...", False, False)]]
    parent.deleteLater()


def test_album_submenu_checks_membership_and_toggles(qapp, store):
    store["albums"] = {"A": ["p"], "B": []}
    viewer = _Viewer()
    parent = QMenu()
    mod.build_album_submenu(viewer, "p", parent)
    sub = parent.actions()[0].menu()
    assert parent.actions()[0].text() == "Albums"
    assert _actions(sub)[:2] == [("A", True, True), ("B", True, False)]
    sub.actions()[0].trigger()
    sub.actions()[1].trigger()
    assert store["albums"] == {"A": [], "B": ["p"]}
    assert viewer.toasts == ["Removed from 'A'", "Added to 'B'"]
    parent.deleteLater()


@pytest.mark.parametrize(("builder", "key", "toast"), [
    ("build_tag_submenu", "image_tags", "Tagged 'New'"),
    ("build_album_submenu", "albums", "Added to 'New'"),
])
def test_new_entry_from_the_submenu(qapp, store, monkeypatch, builder, key, toast):
    viewer = _Viewer()
    parent = QMenu()
    getattr(mod, builder)(viewer, "p", parent)
    new_action = parent.actions()[0].menu().actions()[-1]
    _answer(monkeypatch, "  ")
    new_action.trigger()
    _answer(monkeypatch, "New", ok=False)
    new_action.trigger()
    assert store[key] == {} and viewer.toasts == []
    asked = _answer(monkeypatch, " New ")
    new_action.trigger()
    assert asked[0][0][0] is viewer
    assert store[key] == {"New": ["p"]} and viewer.toasts == [toast]
    parent.deleteLater()


def test_batch_submenu_adds_every_path_and_counts_new_ones(qapp, store, monkeypatch):
    store["image_tags"] = {"T": ["p1"]}
    store["albums"] = {"A": []}
    viewer = _Viewer()
    parent = QMenu()
    mod.build_batch_tag_album_submenu(viewer, ["p1", "p2"], parent)
    tag_menu, album_menu = (a.menu() for a in parent.actions())
    assert [a.text() for a in parent.actions()] == ["Add to Tag", "Add to Album"]
    assert [a.text() for a in tag_menu.actions()] == ["T", "", "+ New Tag..."]
    assert [a.text() for a in album_menu.actions()] == ["A", "", "+ New Album..."]
    assert not tag_menu.actions()[0].isCheckable()
    tag_menu.actions()[0].trigger()
    album_menu.actions()[0].trigger()
    assert store["image_tags"]["T"] == ["p1", "p2"] and store["albums"]["A"] == ["p1", "p2"]
    _answer(monkeypatch, "", ok=True)
    tag_menu.actions()[-1].trigger()
    album_menu.actions()[-1].trigger()
    _answer(monkeypatch, " N ")
    tag_menu.actions()[-1].trigger()
    album_menu.actions()[-1].trigger()
    assert store["image_tags"]["N"] == ["p1", "p2"] and store["albums"]["N"] == ["p1", "p2"]
    assert viewer.toasts == ["Tagged 1 image(s) as 'T'", "Added 2 image(s) to 'A'",
                             "Tagged 2 image(s) as 'N'", "Added 2 image(s) to 'N'"]
    parent.deleteLater()


def test_empty_batch_submenus_have_no_separator(qapp, store):
    parent = QMenu()
    mod.build_batch_tag_album_submenu(_Viewer(), ["p"], parent)
    assert [[a.text() for a in a_.menu().actions()] for a_ in parent.actions()] == [
        ["+ New Tag..."], ["+ New Album..."]]
    parent.deleteLater()


def test_toasts_are_skipped_without_a_toast_widget(qapp, store):
    store["image_tags"] = {"T": []}
    gui = SimpleNamespace(main_window=SimpleNamespace())
    parent = QMenu()
    mod.build_tag_submenu(gui, "p", parent)
    parent.actions()[0].menu().actions()[0].trigger()
    assert store["image_tags"] == {"T": ["p"]}
    parent.deleteLater()
