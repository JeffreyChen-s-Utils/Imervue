"""Tests for batch_ops: rename, move / copy and rotate."""
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
    """The Move / Copy dialog: nothing in the destination is overwritten."""

    @staticmethod
    def _dialog(qapp, paths, dest, *, move):
        from types import SimpleNamespace

        from Imervue.gpu_image_view.actions.batch_ops import BatchMoveDialog
        toasts = []
        gui = SimpleNamespace(
            main_window=None, model=SimpleNamespace(images=list(paths)), tile_cache={},
            selected_tiles=set(paths), tile_selection_mode=True,
            clear_tile_grid=lambda: None, load_tile_grid_async=lambda _imgs: None,
        )
        dlg = BatchMoveDialog(gui, list(paths))
        dlg._gui.main_window = SimpleNamespace(toast=SimpleNamespace(  # noqa: SLF001
            info=toasts.append, success=toasts.append))
        dlg._dest.setText(str(dest))  # noqa: SLF001
        (dlg._move_radio if move else dlg._copy_radio).setChecked(True)  # noqa: SLF001
        return dlg, gui, toasts

    @pytest.fixture(autouse=True)
    def _no_gl(self, monkeypatch):
        from Imervue.gpu_image_view import tile_textures
        monkeypatch.setattr(tile_textures, "free_tile_textures", lambda *_a: None)

    def test_move_renames_instead_of_overwriting(self, qapp, tmp_path):
        """Moving a card's IMG_0001.JPG replaced the album's own IMG_0001.JPG."""
        card, album = tmp_path / "card", tmp_path / "album"
        card.mkdir()
        album.mkdir()
        (card / "IMG_0001.JPG").write_text("new", encoding="utf-8")
        (album / "IMG_0001.JPG").write_text("kept", encoding="utf-8")
        dlg, gui, toasts = self._dialog(qapp, [str(card / "IMG_0001.JPG")], album, move=True)
        try:
            dlg._apply()  # noqa: SLF001
        finally:
            dlg.deleteLater()
        assert (album / "IMG_0001.JPG").read_text(encoding="utf-8") == "kept"
        assert (album / "IMG_0001_1.JPG").read_text(encoding="utf-8") == "new"
        assert gui.model.images == []
        assert toasts == ["Moved 1/1 file(s)"]

    def test_a_file_that_failed_to_move_stays_in_the_grid(self, qapp, tmp_path):
        album = tmp_path / "album"
        album.mkdir()
        good = tmp_path / "good.jpg"
        good.write_text("g", encoding="utf-8")
        missing = str(tmp_path / "missing.jpg")
        dlg, gui, toasts = self._dialog(qapp, [str(good), missing], album, move=True)
        try:
            dlg._apply()  # noqa: SLF001
        finally:
            dlg.deleteLater()
        assert gui.model.images == [missing]
        assert toasts == ["Moved 1/2 file(s)"]

    def test_copy_keeps_the_sources(self, qapp, tmp_path):
        album = tmp_path / "album"
        album.mkdir()
        src = tmp_path / "a.jpg"
        src.write_text("a", encoding="utf-8")
        dlg, gui, _toasts = self._dialog(qapp, [str(src)], album, move=False)
        try:
            dlg._apply()  # noqa: SLF001
        finally:
            dlg.deleteLater()
        assert src.exists() and (album / "a.jpg").exists()
        assert gui.model.images == [str(src)]

    @pytest.mark.parametrize(("move", "expected"), [
        (True, "已移動 1/1 個檔案"), (False, "已複製 1/1 個檔案")])
    def test_result_toast_and_count_follow_the_ui_language(self, qapp, tmp_path, move, expected):
        """The toast and the "N file(s) selected" label stayed English in every language."""
        from PySide6.QtWidgets import QLabel

        from Imervue.multi_language.language_wrapper import language_wrapper
        album = tmp_path / "album"
        album.mkdir()
        src = tmp_path / "a.jpg"
        src.write_text("a", encoding="utf-8")
        previous = language_wrapper.language
        language_wrapper.reset_language("Traditional_Chinese")
        try:
            dlg, _gui, toasts = self._dialog(qapp, [str(src)], album, move=move)
            try:
                labels = [w.text() for w in dlg.findChildren(QLabel)]
                dlg._apply()  # noqa: SLF001
            finally:
                dlg.deleteLater()
        finally:
            language_wrapper.reset_language(previous)
        assert "已選取 1 個檔案" in labels
        assert toasts == [expected]


class TestBatchRenameDialog:
    """The Batch Rename dialog's result toast."""

    def _dialog(self, qapp, paths):
        from types import SimpleNamespace

        from Imervue.gpu_image_view.actions.batch_ops import BatchRenameDialog
        toasts = []
        gui = SimpleNamespace(
            main_window=None, model=SimpleNamespace(images=list(paths)), tile_cache={},
            selected_tiles=set(paths), tile_selection_mode=True,
            clear_tile_grid=lambda: None, load_tile_grid_async=lambda _imgs: None,
        )
        dlg = BatchRenameDialog(gui, list(paths))
        gui.main_window = SimpleNamespace(toast=SimpleNamespace(
            info=lambda m: toasts.append(("info", m)),
            success=lambda m: toasts.append(("success", m))))
        return dlg, gui, toasts

    @pytest.fixture(autouse=True)
    def _no_gl(self, monkeypatch):
        from Imervue.gpu_image_view import tile_textures
        monkeypatch.setattr(tile_textures, "free_tile_textures", lambda *_a: None)

    def test_toast_counts_renamed_and_failed(self, qapp, tmp_path):
        a = tmp_path / "a.jpg"
        a.write_text("a", encoding="utf-8")
        taken = tmp_path / "b.jpg"
        taken.write_text("b", encoding="utf-8")
        (tmp_path / "shot_2.jpg").write_text("already here", encoding="utf-8")
        dlg, gui, toasts = self._dialog(qapp, [str(a), str(taken)])
        dlg._template.setText("shot_{n}{ext}")  # noqa: SLF001
        try:
            dlg._apply()  # noqa: SLF001
        finally:
            dlg.deleteLater()
        assert (tmp_path / "shot_1.jpg").read_text(encoding="utf-8") == "a"
        assert (tmp_path / "shot_2.jpg").read_text(encoding="utf-8") == "already here"
        assert gui.model.images == [str(tmp_path / "shot_1.jpg"), str(taken)]
        assert toasts == [("info", "Renamed 1/2 file(s)")]

    def test_swapped_names_keep_each_tile_on_its_file(self, qapp, tmp_path):
        """Two files swapping names: the grid pointed both slots at the same path."""
        a, b = tmp_path / "shot_2.jpg", tmp_path / "shot_1.jpg"
        a.write_text("a", encoding="utf-8")
        b.write_text("b", encoding="utf-8")
        dlg, gui, toasts = self._dialog(qapp, [str(a), str(b)])
        dlg._template.setText("shot_{n}{ext}")  # noqa: SLF001
        try:
            dlg._apply()  # noqa: SLF001
        finally:
            dlg.deleteLater()
        assert (tmp_path / "shot_1.jpg").read_text(encoding="utf-8") == "a"
        assert (tmp_path / "shot_2.jpg").read_text(encoding="utf-8") == "b"
        assert gui.model.images == [str(tmp_path / "shot_1.jpg"), str(tmp_path / "shot_2.jpg")]
        assert toasts == [("success", "Renamed 2/2 file(s)")]

    def test_renamed_files_keep_their_rating_and_sidecars(self, qapp, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        raw, jpeg = tmp_path / "IMG.CR2", tmp_path / "IMG.JPG"
        raw.write_text("raw", encoding="utf-8")
        jpeg.write_text("jpg", encoding="utf-8")
        (tmp_path / "IMG.xmp").write_text("edits", encoding="utf-8")
        user_setting_dict["image_ratings"] = {str(raw): 5, str(jpeg): 3}
        dlg, _gui, _toasts = self._dialog(qapp, [str(raw), str(jpeg)])
        dlg._template.setText("shot_{n}{ext}")  # noqa: SLF001
        try:
            dlg._apply()  # noqa: SLF001
        finally:
            dlg.deleteLater()
        assert user_setting_dict["image_ratings"] == {
            str(tmp_path / "shot_1.CR2"): 5, str(tmp_path / "shot_2.JPG"): 3}
        # The pair shared IMG.xmp: each renamed file gets its own copy.
        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "shot_1.CR2", "shot_1.xmp", "shot_2.JPG", "shot_2.xmp"]

    def test_toast_follows_the_ui_language(self, qapp, tmp_path):
        from Imervue.multi_language.language_wrapper import language_wrapper
        a = tmp_path / "a.jpg"
        a.write_text("a", encoding="utf-8")
        dlg, _gui, toasts = self._dialog(qapp, [str(a)])
        dlg._template.setText("shot_{n}{ext}")  # noqa: SLF001
        previous = language_wrapper.language
        language_wrapper.reset_language("Traditional_Chinese")
        try:
            dlg._apply()  # noqa: SLF001
        finally:
            language_wrapper.reset_language(previous)
            dlg.deleteLater()
        assert toasts == [("success", "已重新命名 1/1 個檔案")]


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

    def test_raw_and_animated_files_are_skipped_untouched(self, tmp_path):
        from PIL import Image

        from Imervue.gpu_image_view.actions.batch_ops import batch_rotate
        raw = tmp_path / "shot.nef"
        Image.new("RGB", (30, 20)).save(raw, format="TIFF")   # how Pillow sees a RAW
        anim = tmp_path / "anim.gif"
        frames = [Image.new("RGB", (8, 4), c) for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
        frames[0].save(anim, save_all=True, append_images=frames[1:])
        before = {p: p.read_bytes() for p in (raw, anim)}
        gui = self._gui([str(raw), str(anim)])
        batch_rotate(gui, [str(raw), str(anim)], 90)
        assert {p: p.read_bytes() for p in (raw, anim)} == before
        assert gui.main_window.toast.calls == [("info", "Rotated 0/2 file(s)")]

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

        def boom(_path, clockwise):
            raise RuntimeError("bug")

        monkeypatch.setattr(batch_ops, "lossless_rotate", boom)
        with pytest.raises(RuntimeError):
            batch_ops.batch_rotate(self._gui([]), [str(tmp_path / "a.png")], 90)

    def test_jpeg_keeps_its_pixels_and_exif(self, tmp_path):
        """The batch re-encoded every JPEG at quality 75 and dropped its camera, date and GPS."""
        from PIL import Image

        from Imervue.gpu_image_view.actions.batch_ops import batch_rotate
        exif = Image.Exif()
        exif[0x010F] = "Canon"
        exif.get_ifd(0x8769)[0x9003] = "2020:01:02 03:04:05"
        path = tmp_path / "p.jpg"
        Image.new("RGB", (40, 20), (10, 200, 30)).save(path, quality=97, exif=exif)
        before = path.read_bytes()
        batch_rotate(self._gui([str(path)]), [str(path)], -90)
        after = path.read_bytes()
        scan = b"\xff\xda"                                      # the compressed pixels
        assert after[after.index(scan):] == before[before.index(scan):]
        with Image.open(path) as img:
            assert img.getexif()[0x0112] == 8                   # counter-clockwise
            assert img.getexif()[0x010F] == "Canon"
            assert img.getexif().get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"
