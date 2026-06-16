"""Tests for the file-tree folder-thumbnail model.

``folder_preview_path`` is pure; the worker / model get qapp smoke tests. Plain
QFileSystemModel (a QObject, not a QOpenGLWidget) → no headless-CI skip.
"""
from __future__ import annotations

import pytest
from PIL import Image
from PySide6.QtGui import QImage

from Imervue.gui.folder_thumbnail_model import (
    MAX_ICON_SIZE,
    MIN_ICON_SIZE,
    FolderThumbnailModel,
    _PreviewWorker,
    clamp_icon_size,
    folder_preview_path,
)


def _png(path, size=(8, 8)):
    Image.new("RGB", size, (120, 60, 30)).save(path)
    return str(path)


class TestFolderPreviewPath:
    def test_returns_first_image_name_sorted(self, tmp_path):
        _png(tmp_path / "b.png")
        _png(tmp_path / "a.jpg")
        (tmp_path / "notes.txt").write_text("x")
        assert folder_preview_path(str(tmp_path)) == str(tmp_path / "a.jpg")

    def test_none_when_no_images(self, tmp_path):
        (tmp_path / "notes.txt").write_text("x")
        assert folder_preview_path(str(tmp_path)) is None

    def test_raw_is_skipped_by_default(self, tmp_path):
        # .cr2 isn't QImage-decodable, so the default preview exts exclude it.
        (tmp_path / "a.cr2").write_bytes(b"rawdata")
        assert folder_preview_path(str(tmp_path)) is None

    def test_missing_directory_returns_none(self, tmp_path):
        assert folder_preview_path(str(tmp_path / "nope")) is None

    def test_custom_exts(self, tmp_path):
        (tmp_path / "a.cr2").write_bytes(b"raw")
        assert folder_preview_path(str(tmp_path), {".cr2"}) == str(tmp_path / "a.cr2")


class TestPreviewWorker:
    def test_emits_scaled_thumbnail_for_folder_with_image(self, qapp, tmp_path):
        folder = tmp_path / "f"
        folder.mkdir()
        _png(folder / "a.png", size=(40, 40))
        captured = []
        worker = _PreviewWorker(str(folder), {".png"}, 16)
        worker.signals.done.connect(lambda fp, img: captured.append((fp, img)))
        worker.run()
        assert len(captured) == 1
        path, thumb = captured[0]
        assert path == str(folder)
        assert not thumb.isNull()
        assert thumb.width() <= 16 and thumb.height() <= 16

    def test_emits_null_for_empty_folder(self, qapp, tmp_path):
        folder = tmp_path / "empty"
        folder.mkdir()
        captured = []
        worker = _PreviewWorker(str(folder), {".png"}, 16)
        worker.signals.done.connect(lambda _fp, img: captured.append(img))
        worker.run()
        assert captured and captured[0].isNull()


class TestFolderThumbnailModel:
    def test_request_preview_is_idempotent(self, qapp, monkeypatch):
        model = FolderThumbnailModel()
        started = []
        monkeypatch.setattr(model._pool, "start", lambda worker: started.append(worker))
        model._request_preview("/some/folder")
        model._request_preview("/some/folder")  # already pending → no second worker
        assert len(started) == 1

    def test_on_preview_ready_caches_icon_and_none(self, qapp):
        model = FolderThumbnailModel()
        model._pending.update({"/has", "/none"})
        model._on_preview_ready("/has", QImage(8, 8, QImage.Format.Format_RGB888))
        model._on_preview_ready("/none", QImage())  # null → no preview
        assert model._cache["/has"] is not None
        assert model._cache["/none"] is None
        assert "/has" not in model._pending


class TestDynamicIconSize:
    @pytest.mark.parametrize("raw,expected", [
        (5, MIN_ICON_SIZE), (16, 16), (50, 50), (128, MAX_ICON_SIZE), (999, MAX_ICON_SIZE),
    ])
    def test_clamp_icon_size(self, raw, expected):
        assert clamp_icon_size(raw) == expected

    def test_set_icon_size_changes_and_clears_cache(self, qapp):
        model = FolderThumbnailModel(icon_size=32)
        model._cache["/x"] = None
        model._pending.add("/y")
        model.set_icon_size(64)
        assert model.icon_size() == 64
        assert model._cache == {}
        assert model._pending == set()

    def test_set_icon_size_clamps(self, qapp):
        model = FolderThumbnailModel()
        model.set_icon_size(9999)
        assert model.icon_size() == MAX_ICON_SIZE

    def test_request_preview_uses_current_icon_size(self, qapp, monkeypatch):
        model = FolderThumbnailModel(icon_size=64)
        captured = []
        monkeypatch.setattr(model._pool, "start", lambda worker: captured.append(worker))
        model._request_preview("/f")
        assert captured[0]._size == 64

    def test_tree_set_thumbnail_size_syncs_view_and_model(self, qapp):
        from types import SimpleNamespace

        from Imervue.gui.file_tree_view import _FileTreeView
        tree = _FileTreeView(SimpleNamespace())
        model = FolderThumbnailModel()
        tree.setModel(model)
        tree.set_thumbnail_size(64)
        assert tree.iconSize().width() == 64
        assert model.icon_size() == 64

    def test_tree_set_thumbnail_size_clamps(self, qapp):
        from types import SimpleNamespace

        from Imervue.gui.file_tree_view import _FileTreeView
        tree = _FileTreeView(SimpleNamespace())
        tree.setModel(FolderThumbnailModel())
        tree.set_thumbnail_size(9999)
        assert tree.iconSize().width() == MAX_ICON_SIZE
