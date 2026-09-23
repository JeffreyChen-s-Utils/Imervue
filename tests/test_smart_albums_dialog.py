"""Qt smoke tests for Smart Albums export / import wiring."""
from __future__ import annotations

import pytest

from Imervue.library import album_io, image_index, smart_album


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


def _dialog():
    from Imervue.gui.smart_albums_dialog import SmartAlbumsDialog
    # None parent -> top-level dialog; _export / _import don't use self._ui.
    return SmartAlbumsDialog(None)


def test_export_writes_albums_file(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    smart_album.save("Faves", {"min_rating": 4})
    dest = tmp_path / "out.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(dest), "JSON (*.json)"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    dialog = _dialog()
    try:
        dialog._export()
    finally:
        dialog.deleteLater()
    assert dest.exists()
    names = {e["name"] for e in album_io.parse_albums(dest.read_text(encoding="utf-8"))}
    assert names == {"Faves"}


def test_import_loads_albums_and_refreshes_list(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    src = tmp_path / "in.json"
    smart_album.save("Temp", {"min_rating": 3})
    album_io.export_albums(src)
    smart_album.delete("Temp")  # remove so the import re-creates it
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(src), "JSON (*.json)"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    dialog = _dialog()
    try:
        dialog._import()
        names = [dialog._list.item(i).text() for i in range(dialog._list.count())]
    finally:
        dialog.deleteLater()
    assert "Temp" in names
    assert smart_album.get("Temp") is not None


def test_export_cancelled_is_a_no_op(qapp, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    called = {"export": False}
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(
        album_io, "export_albums",
        lambda *a, **k: called.__setitem__("export", True) or 0,
    )
    dialog = _dialog()
    try:
        dialog._export()
    finally:
        dialog.deleteLater()
    assert called["export"] is False


# ---------------------------------------------------------------------------
# Layout characterisation: order, texts, ranges and wiring of every control.
# ---------------------------------------------------------------------------

_ACTIONS = [("Save", "_save"), ("Apply", "_apply"), ("Delete", "_delete"),
            ("Auto by location", "_auto_by_location"), ("Export…", "_export"),
            ("Import…", "_import")]


@pytest.fixture
def english(monkeypatch):
    from Imervue.gui import smart_albums_dialog as mod
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


def _items(layout):
    return [layout.itemAt(i).widget() or layout.itemAt(i).layout() for i in range(layout.count())]


def test_layout_order(qapp, english):
    dialog = _dialog()
    try:
        kinds = [type(x).__name__ for x in _items(dialog.layout())]
        assert kinds == ["QLabel", "QListWidget", "QHBoxLayout", "QLabel", "QLineEdit",
                         "QLineEdit", "QHBoxLayout", "QHBoxLayout", "QLineEdit", "QLineEdit",
                         "QPushButton"]
        items = _items(dialog.layout())
        assert (items[0].text(), items[3].text(), items[10].text()) == (
            "Saved albums", "Rules", "Close")
        assert items[1] is dialog._list
        assert dialog.windowTitle() == "Smart Albums"
        assert (dialog.width(), dialog.height()) == (560, 520)
    finally:
        dialog.deleteLater()


def test_action_row_texts_and_wiring(qapp, english, monkeypatch):
    from Imervue.gui.smart_albums_dialog import SmartAlbumsDialog
    calls = []
    for _text, slot in _ACTIONS:
        monkeypatch.setattr(SmartAlbumsDialog, slot, lambda self, *_a, s=slot: calls.append(s))
    monkeypatch.setattr(SmartAlbumsDialog, "_on_album_clicked",
                        lambda self, item: calls.append(("clicked", item.text())))
    smart_album.save("Faves", {"min_rating": 4})
    dialog = _dialog()
    try:
        row = _items(dialog.layout())[2]
        widgets = _items(row)
        assert widgets[0] is dialog._name_edit
        assert dialog._name_edit.placeholderText() == "Name"
        assert [b.text() for b in widgets[1:]] == [t for t, _s in _ACTIONS]
        for button in widgets[1:]:
            button.click()
        assert calls == [s for _t, s in _ACTIONS]
        dialog._list.itemClicked.emit(dialog._list.item(0))
        assert calls[-1] == ("clicked", "Faves")
    finally:
        dialog.deleteLater()


def test_rule_fields(qapp, english):
    dialog = _dialog()
    try:
        items = _items(dialog.layout())
        assert items[4] is dialog._ext_edit
        assert dialog._ext_edit.placeholderText() == "extensions comma-sep (jpg,png)"
        assert items[5] is dialog._name_contains_edit
        assert dialog._name_contains_edit.placeholderText() == "name contains…"
        assert _items(items[6]) == [dialog._min_w, dialog._min_h, dialog._min_rating]
        spins = [(s.minimum(), s.maximum(), s.prefix()) for s in _items(items[6])]
        assert spins == [(0, 20000, "min w "), (0, 20000, "min h "), (0, 5, "min★ ")]
        assert _items(items[7]) == [dialog._color_combo, dialog._cull_combo, dialog._fav_check]
        color = dialog._color_combo
        assert [(color.itemText(i), color.itemData(i)) for i in range(color.count())] == [
            ("-- any color --", ""), ("Red", "red"), ("Yellow", "yellow"), ("Green", "green"),
            ("Blue", "blue"), ("Purple", "purple")]
        cull = dialog._cull_combo
        assert [(cull.itemText(i), cull.itemData(i)) for i in range(cull.count())] == [
            ("-- any cull --", ""), ("pick", "pick"), ("reject", "reject"),
            ("unflagged", "unflagged")]
        assert dialog._fav_check.text() == "Favorites only"
        assert items[8] is dialog._tags_edit
        assert dialog._tags_edit.placeholderText() == "tags comma-sep (ALL must match)"
        assert items[9] is dialog._place_edit
        assert dialog._place_edit.placeholderText() == "place (City, Country)"
    finally:
        dialog.deleteLater()


def test_close_button_accepts_and_list_is_filled(qapp, english):
    from PySide6.QtWidgets import QDialog
    smart_album.save("B", {})
    smart_album.save("A", {})
    dialog = _dialog()
    try:
        names = [dialog._list.item(i).text() for i in range(dialog._list.count())]
        assert sorted(names) == ["A", "B"]
        _items(dialog.layout())[10].click()
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.deleteLater()
