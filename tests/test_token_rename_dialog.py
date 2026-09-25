"""Tests for the Token Batch Rename dialog."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QDialog, QWidget

from Imervue.gui.token_rename_dialog import TokenRenameDialog
from Imervue.multi_language.language_wrapper import language_wrapper


class _FakeUi(QWidget):
    def __init__(self, images):
        super().__init__()
        self.toasts: list[tuple[str, str]] = []
        self.toast = SimpleNamespace(
            info=lambda msg: self.toasts.append(("info", msg)),
            success=lambda msg: self.toasts.append(("success", msg)))
        self.viewer = SimpleNamespace(
            model=SimpleNamespace(images=list(images)),
            clear_tile_grid=lambda: None, load_tile_grid_async=lambda _images: None)


@pytest.fixture
def photos(tmp_path):
    paths = []
    for name in ("a.jpg", "b.jpg"):
        path = tmp_path / name
        path.write_bytes(b"x")
        paths.append(str(path))
    return paths


def _dialog(ui, paths, template):
    dlg = TokenRenameDialog(ui, paths)
    dlg._template_edit.setText(template)  # noqa: SLF001
    return dlg


def test_apply_renames_and_reports_in_the_ui_language(qapp, photos, tmp_path):
    """Formatting the toast with failed= raised KeyError: every translation says {f}."""
    ui = _FakeUi(photos)
    dlg = _dialog(ui, photos, "shot_{counter:02}{ext}")
    try:
        dlg._apply()  # noqa: SLF001
        assert dlg.result() == QDialog.DialogCode.Accepted
    finally:
        dlg.deleteLater()
    assert ui.viewer.model.images == [str(tmp_path / "shot_01.jpg"), str(tmp_path / "shot_02.jpg")]
    assert ui.toasts == [("success", "Renamed 2, failed 0")]


def test_a_failed_rename_keeps_its_old_path_in_the_grid(qapp, photos, tmp_path, monkeypatch):
    real_rename = os.rename

    def refuse_b(src, dst):
        if src.endswith("b.jpg"):
            raise PermissionError("in use")
        real_rename(src, dst)

    monkeypatch.setattr(os, "rename", refuse_b)
    ui = _FakeUi(photos)
    dlg = _dialog(ui, photos, "shot_{counter:02}{ext}")
    try:
        dlg._apply()  # noqa: SLF001
    finally:
        dlg.deleteLater()
    assert ui.viewer.model.images == [str(tmp_path / "shot_01.jpg"), photos[1]]
    assert ui.toasts == [("info", "Renamed 1, failed 1")]


def test_status_column_follows_the_ui_language(qapp, photos):
    previous = language_wrapper.language
    language_wrapper.reset_language("Traditional_Chinese")
    ui = _FakeUi(photos)
    try:
        dlg = _dialog(ui, photos, "same{ext}")      # both want same.jpg
        statuses = [dlg._table.item(row, 2).text() for row in range(2)]  # noqa: SLF001
        dlg._apply()  # noqa: SLF001
        dlg.deleteLater()
    finally:
        language_wrapper.reset_language(previous)
    assert statuses == ["可重新命名", "衝突"]
    assert ui.toasts == [("info", "已重新命名 1，失敗 1")]
