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
