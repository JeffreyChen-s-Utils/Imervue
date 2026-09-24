"""Tests for batch_ops helper functions (non-GUI parts)."""
import shutil
from pathlib import Path

import pytest



class TestBatchRename:
    """Test file renaming logic outside the GUI."""

    def test_rename_files(self, image_folder):
        """Files in folder can be renamed via pathlib."""
        folder = Path(image_folder)
        original = list(folder.glob("*.png"))
        assert len(original) >= 1
        src = original[0]
        dst = src.with_name("renamed_image.png")
        src.rename(dst)
        assert dst.exists()
        assert not src.exists()


class TestBatchMoveCopy:
    """Test move/copy file operations."""

    def test_copy_file(self, image_folder, tmp_path):
        folder = Path(image_folder)
        src = next(iter(folder.glob("*.png")))
        dst_dir = tmp_path / "dest"
        dst_dir.mkdir()
        dst = dst_dir / src.name
        shutil.copy2(str(src), str(dst))
        assert dst.exists()
        assert src.exists()  # original still present

    def test_move_file(self, image_folder, tmp_path):
        folder = Path(image_folder)
        src = next(iter(folder.glob("*.png")))
        dst_dir = tmp_path / "dest"
        dst_dir.mkdir()
        dst = dst_dir / src.name
        shutil.move(str(src), str(dst))
        assert dst.exists()
        assert not src.exists()


class TestBatchRotate:
    class _Toast:
        def __init__(self):
            self.calls = []

        def info(self, msg):
            self.calls.append(("info", msg))

        def success(self, msg):
            self.calls.append(("success", msg))

    def _gui(self, images):
        from types import SimpleNamespace
        return SimpleNamespace(
            tile_cache={}, selected_tiles=set(images), tile_selection_mode=True,
            clear_tile_grid=lambda: None, load_tile_grid_async=lambda _imgs: None,
            model=SimpleNamespace(images=list(images)),
            main_window=SimpleNamespace(toast=self._Toast()),
        )

    @pytest.fixture(autouse=True)
    def _no_gl(self, monkeypatch):
        from Imervue.gpu_image_view import tile_textures
        monkeypatch.setattr(tile_textures, "free_tile_textures", lambda *_a: None)

    def test_rotates_readable_files_and_counts_failures(self, tmp_path):
        from PIL import Image

        from Imervue.gpu_image_view.actions.batch_ops import batch_rotate
        good = tmp_path / "good.png"
        Image.new("RGB", (4, 2)).save(good)
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not a png")
        gui = self._gui([str(good), str(bad)])
        batch_rotate(gui, [str(good), str(bad), str(tmp_path / "gone.png")], 90)
        with Image.open(good) as img:
            assert img.size == (2, 4)
        assert gui.main_window.toast.calls == [("info", "Rotated 1/3 file(s)")]

    def test_tagged_photo_turns_from_what_is_shown(self, tmp_path):
        """Rotating the stored pixels while the re-save dropped the tag cancelled out."""
        from PIL import Image

        from Imervue.gpu_image_view.actions.batch_ops import batch_rotate
        from Imervue.image.shown import as_shown
        exif = Image.Exif()
        exif[0x0112] = 6   # 40x20 stored, shown 20x40
        path = tmp_path / "p.jpg"
        Image.new("RGB", (40, 20)).save(path, exif=exif)
        batch_rotate(self._gui([str(path)]), [str(path)], 90)
        with Image.open(path) as img:
            assert as_shown(img).size == (40, 20)   # a real quarter turn of the 20x40 shown

    def test_result_toast_follows_the_ui_language(self, tmp_path):
        from PIL import Image

        from Imervue.gpu_image_view.actions.batch_ops import batch_rotate
        from Imervue.multi_language.language_wrapper import language_wrapper
        good = tmp_path / "good.png"
        Image.new("RGB", (4, 2)).save(good)
        gui = self._gui([str(good)])
        previous = language_wrapper.language
        language_wrapper.reset_language("Traditional_Chinese")
        try:
            batch_rotate(gui, [str(good)], 90)
        finally:
            language_wrapper.reset_language(previous)
        assert gui.main_window.toast.calls == [("success", "已旋轉 1/1 個檔案")]

    def test_unexpected_error_propagates(self, tmp_path, monkeypatch):
        from Imervue.gpu_image_view.actions import batch_ops

        def boom(_path):
            raise RuntimeError("bug")

        monkeypatch.setattr(batch_ops.Image, "open", boom)
        with pytest.raises(RuntimeError):
            batch_ops.batch_rotate(self._gui([]), [str(tmp_path / "a.png")], 90)
