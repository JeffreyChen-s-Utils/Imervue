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
        worker.signals.done.connect(
            lambda fp, img, had: captured.append((fp, img, had)))
        worker.run()
        assert len(captured) == 1
        path, thumb, had_candidate = captured[0]
        assert path == str(folder)
        assert not thumb.isNull()
        assert thumb.width() <= 16 and thumb.height() <= 16
        assert had_candidate is True

    def test_emits_null_and_no_candidate_for_empty_folder(self, qapp, tmp_path):
        folder = tmp_path / "empty"
        folder.mkdir()
        captured = []
        worker = _PreviewWorker(str(folder), {".png"}, 16)
        worker.signals.done.connect(
            lambda _fp, img, had: captured.append((img, had)))
        worker.run()
        assert captured
        thumb, had_candidate = captured[0]
        assert thumb.isNull()
        assert had_candidate is False

    def test_emits_null_with_candidate_when_decode_fails(self, qapp, tmp_path):
        # A "png" that is not actually decodable — the file is listed as a
        # candidate but QImage can't read it, the transient-failure signature.
        folder = tmp_path / "broken"
        folder.mkdir()
        (folder / "a.png").write_bytes(b"not a real png")
        captured = []
        worker = _PreviewWorker(str(folder), {".png"}, 16)
        worker.signals.done.connect(
            lambda _fp, img, had: captured.append((img, had)))
        worker.run()
        assert captured
        thumb, had_candidate = captured[0]
        assert thumb.isNull()
        assert had_candidate is True


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
        model._on_preview_ready(
            "/has", QImage(8, 8, QImage.Format.Format_RGB888), True)
        model._on_preview_ready("/none", QImage(), False)  # no candidate
        assert model._cache["/has"] is not None
        assert model._cache["/none"] is None
        assert "/has" not in model._pending


class TestTransientDecodeRetry:
    """A candidate image that fails to decode (mid-delete read) must not be
    cached as a permanent "no preview" — it is retried up to the cap."""

    def test_decode_failure_with_candidate_retries_not_caches(self, qapp, monkeypatch):
        from Imervue.gui.folder_thumbnail_model import MAX_PREVIEW_RETRIES
        model = FolderThumbnailModel()
        started = []
        monkeypatch.setattr(model._pool, "start", lambda worker: started.append(worker))
        model._pending.add("/f")
        model._on_preview_ready("/f", QImage(), True)  # null thumb, had candidate
        # Not poisoned with None, and a fresh decode was scheduled.
        assert "/f" not in model._cache
        assert len(started) == 1
        assert model._retry["/f"] == 1
        assert MAX_PREVIEW_RETRIES >= 1

    def test_retry_gives_up_at_cap_and_caches_none(self, qapp, monkeypatch):
        from Imervue.gui.folder_thumbnail_model import MAX_PREVIEW_RETRIES
        model = FolderThumbnailModel()
        started = []
        monkeypatch.setattr(model._pool, "start", lambda worker: started.append(worker))
        model._retry["/f"] = MAX_PREVIEW_RETRIES  # already at the cap
        model._on_preview_ready("/f", QImage(), True)
        assert model._cache["/f"] is None  # falls back to the default icon
        assert started == []                # no further retry
        assert "/f" not in model._retry

    def test_success_clears_pending_retry_counter(self, qapp):
        model = FolderThumbnailModel()
        model._retry["/f"] = 1
        model._on_preview_ready(
            "/f", QImage(8, 8, QImage.Format.Format_RGB888), True)
        assert model._cache["/f"] is not None
        assert "/f" not in model._retry


class TestClearMissingPreviews:
    def test_drops_none_entries_keeps_icons(self, qapp):
        model = FolderThumbnailModel()
        model._on_preview_ready(
            "/has", QImage(8, 8, QImage.Format.Format_RGB888), True)
        model._cache["/none"] = None
        model._retry["/pending"] = 1
        model.clear_missing_previews()
        assert "/has" in model._cache          # decoded preview survives
        assert "/none" not in model._cache     # blank marker dropped → re-scans
        assert model._retry == {}

    def test_empty_cache_is_a_no_op(self, qapp):
        model = FolderThumbnailModel()
        model.clear_missing_previews()
        assert model._cache == {}


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
        model._retry["/z"] = 1
        model.set_icon_size(64)
        assert model.icon_size() == 64
        assert model._cache == {}
        assert model._pending == set()
        assert model._retry == {}

    def test_set_icon_size_clamps(self, qapp):
        model = FolderThumbnailModel()
        model.set_icon_size(9999)
        assert model.icon_size() == MAX_ICON_SIZE

    def test_request_preview_uses_current_icon_size(self, qapp, monkeypatch):
        model = FolderThumbnailModel(icon_size=64)
        captured = []
        monkeypatch.setattr(model._pool, "start", lambda worker: captured.append(worker))
        model._request_preview("/f")
        assert len(captured) == 1
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
