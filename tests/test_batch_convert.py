"""
Tests for batch format conversion — scanning, worker logic, format handling.

Core logic tests are pure Python (no Qt needed for the scan function).
Worker tests call .run() directly (no thread) and require ``qapp``.
"""
from __future__ import annotations

import os

import numpy as np
import pytest
from PIL import Image

from Imervue.gui.batch_convert_dialog import _scan_folder, _ConvertWorker

_rng = np.random.default_rng(seed=0xC0FFEE)


# ---------------------------------------------------------------------------
# Folder scanning
# ---------------------------------------------------------------------------

class TestScanFolder:
    def test_finds_images(self, image_folder):
        paths = _scan_folder(image_folder)
        assert len(paths) == 4
        names = {os.path.basename(p) for p in paths}
        assert "alpha.png" in names
        assert "beta.jpg" in names

    def test_ignores_non_image_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "data.json").write_text("{}")
        arr = np.full((10, 10, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(str(tmp_path / "img.png"))
        paths = _scan_folder(str(tmp_path))
        assert len(paths) == 1

    def test_empty_folder(self, tmp_path):
        paths = _scan_folder(str(tmp_path))
        assert paths == []

    def test_sorted_by_name(self, tmp_path):
        for name in ["c.png", "a.png", "b.png"]:
            arr = np.full((10, 10, 3), 128, dtype=np.uint8)
            Image.fromarray(arr).save(str(tmp_path / name))
        paths = _scan_folder(str(tmp_path))
        names = [os.path.basename(p) for p in paths]
        assert names == ["a.png", "b.png", "c.png"]


# ---------------------------------------------------------------------------
# Convert worker
# ---------------------------------------------------------------------------

class TestConvertWorker:
    def test_png_to_jpeg(self, tmp_path):
        """Convert a PNG file to JPEG."""
        src = tmp_path / "src"
        src.mkdir()
        arr = np.full((32, 32, 3), 100, dtype=np.uint8)
        Image.fromarray(arr).save(str(src / "test.png"), format="PNG")

        out = tmp_path / "out"
        out.mkdir()

        worker = _ConvertWorker(
            paths=[str(src / "test.png")],
            output_dir=str(out),
            fmt="JPEG",
            quality=85,
            delete_originals=False,
            skip_same_fmt=True,
        )
        results = []
        worker.result_ready.connect(lambda s, f, sk: results.append((s, f, sk)))
        worker.run()

        assert len(results) == 1
        success, failed, _ = results[0]
        assert success == 1
        assert failed == 0
        # Output file exists
        out_files = list(out.iterdir())
        assert len(out_files) == 1
        assert out_files[0].suffix == ".jpg"

    def test_interruption_breaks_before_processing(self, tmp_path):
        """When the thread is interrupted (closeEvent requests it), the loop
        stops at its next per-image check without converting more files."""
        src = tmp_path / "src"
        src.mkdir()
        arr = np.full((16, 16, 3), 100, dtype=np.uint8)
        for name in ("a.png", "b.png"):
            Image.fromarray(arr).save(str(src / name), format="PNG")
        out = tmp_path / "out"
        out.mkdir()

        class _InterruptedWorker(_ConvertWorker):
            def isInterruptionRequested(self):   # noqa: N802 - Qt override
                return True

        worker = _InterruptedWorker(
            paths=[str(src / "a.png"), str(src / "b.png")],
            output_dir=str(out), fmt="JPEG", quality=85,
            delete_originals=False, skip_same_fmt=False,
        )
        progress, results = [], []
        worker.progress.connect(lambda *a: progress.append(a))
        worker.result_ready.connect(lambda s, f, sk: results.append((s, f, sk)))
        worker.run()

        assert progress == []                 # broke before the first image
        assert results == [(0, 0, 0)]         # still reported so the UI resets
        assert list(out.iterdir()) == []      # nothing converted

    def test_skip_same_format(self, tmp_path):
        """Should skip files already in the target format."""
        src = tmp_path / "src"
        src.mkdir()
        arr = np.full((32, 32, 3), 100, dtype=np.uint8)
        Image.fromarray(arr).save(str(src / "test.png"), format="PNG")

        out = tmp_path / "out"
        out.mkdir()

        worker = _ConvertWorker(
            paths=[str(src / "test.png")],
            output_dir=str(out),
            fmt="PNG",
            quality=100,
            delete_originals=False,
            skip_same_fmt=True,
        )
        results = []
        worker.result_ready.connect(lambda s, f, sk: results.append((s, f, sk)))
        worker.run()

        assert results
        _, _, skipped = results[0]
        assert skipped == 1

    def test_delete_originals(self, tmp_path):
        """When delete_originals is True, source file should be removed."""
        src = tmp_path / "src"
        src.mkdir()
        src_path = src / "test.png"
        arr = np.full((32, 32, 3), 100, dtype=np.uint8)
        Image.fromarray(arr).save(str(src_path), format="PNG")

        out = tmp_path / "out"
        out.mkdir()

        worker = _ConvertWorker(
            paths=[str(src_path)],
            output_dir=str(out),
            fmt="JPEG",
            quality=85,
            delete_originals=True,
            skip_same_fmt=True,
        )
        worker.run()
        assert not src_path.exists()

    def test_multiple_files(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        paths = []
        for i in range(5):
            p = src / f"img{i}.png"
            arr = _rng.integers(0, 256, (16, 16, 3), dtype=np.uint8)
            Image.fromarray(arr).save(str(p), format="PNG")
            paths.append(str(p))

        out = tmp_path / "out"
        out.mkdir()

        worker = _ConvertWorker(
            paths=paths,
            output_dir=str(out),
            fmt="WebP",
            quality=80,
            delete_originals=False,
            skip_same_fmt=True,
        )
        results = []
        worker.result_ready.connect(lambda s, f, sk: results.append((s, f, sk)))
        worker.run()

        success, _, _ = results[0]
        assert success == 5
        out_files = list(out.iterdir())
        assert len(out_files) == 5
        assert all(f.suffix == ".webp" for f in out_files)


def _tagged_portrait(path):
    """40x20 stored pixels tagged 6, so shown (and expected out) as 20x40."""
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", (40, 20)).save(path, exif=exif)
    return str(path)


def test_converted_tagged_photo_is_upright(tmp_path):
    """The orientation tag is not carried, so the turn has to be in the pixels."""
    src = _tagged_portrait(tmp_path / "p.jpg")
    out = tmp_path / "out"
    out.mkdir()
    worker = _ConvertWorker(paths=[src], output_dir=str(out), fmt="PNG", quality=85,
                            delete_originals=False, skip_same_fmt=True)
    worker._convert_one(src, ".png")
    with Image.open(out / "p.png") as saved:
        assert saved.size == (20, 40)


def _worker(paths, out, fmt="JPEG", delete=False):
    worker = _ConvertWorker(paths=[str(p) for p in paths], output_dir=str(out), fmt=fmt,
                            quality=90, delete_originals=delete, skip_same_fmt=False)
    results = []
    worker.result_ready.connect(lambda s, f, sk: results.append((s, f, sk)))
    return worker, results


class TestConvertKeepsWhatItShould:
    def test_originals_go_to_the_recycle_bin_in_one_batch(self, tmp_path, os_trash):
        """The tooltip promised the recycle bin; the code called os.remove."""
        paths = []
        for index in range(3):
            path = tmp_path / f"a{index}.png"
            Image.new("RGB", (8, 8), (index, 0, 0)).save(path)
            paths.append(path)
        out = tmp_path / "out"
        out.mkdir()
        worker, results = _worker(paths, out, delete=True)
        worker.run()
        assert results == [(3, 0, 0)]
        assert sorted(os_trash) == sorted(str(p) for p in paths)

    def test_exif_is_carried_without_the_orientation(self, tmp_path):
        """A converted file lost the camera, capture date and location for good."""
        exif = Image.Exif()
        exif[0x010F] = "Canon"
        exif[0x0112] = 6
        exif.get_ifd(0x8769)[0x9003] = "2020:01:02 03:04:05"
        exif.get_ifd(0x8825)[1] = "N"
        src = tmp_path / "p.jpg"
        Image.new("RGB", (40, 20)).save(src, exif=exif)
        out = tmp_path / "out"
        out.mkdir()
        worker, _results = _worker([src], out, fmt="PNG")
        worker.run()
        with Image.open(out / "p.png") as saved:
            written = saved.getexif()
            assert saved.size == (20, 40)
            assert written[0x010F] == "Canon"
            assert 0x0112 not in written
            assert written.get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"
            assert written.get_ifd(0x8825)[1] == "N"

    def test_raw_is_developed_at_full_size_and_then_trashed(self, tmp_path, monkeypatch, os_trash):
        """A CR2 became a small preview-sized JPEG, and the RAW was then deleted."""
        from Imervue.gpu_image_view.images import image_loader
        monkeypatch.setattr(image_loader, "_load_raw",
                            lambda _p, thumbnail: np.full((30, 50, 3), 90, dtype=np.uint8))
        raw = tmp_path / "shot.cr2"
        Image.new("RGB", (5, 3)).save(raw, format="TIFF")          # how Pillow sees a RAW
        out = tmp_path / "out"
        out.mkdir()
        worker, results = _worker([raw], out, delete=True)
        worker.run()
        assert results == [(1, 0, 0)]
        with Image.open(out / "shot.jpg") as saved:
            assert saved.size == (50, 30)
        assert os_trash == [str(raw)]

    def test_animated_original_is_kept(self, tmp_path, os_trash):
        anim = tmp_path / "anim.gif"
        frames = [Image.new("RGB", (8, 4), c) for c in ((255, 0, 0), (0, 255, 0))]
        frames[0].save(anim, save_all=True, append_images=frames[1:])
        out = tmp_path / "out"
        out.mkdir()
        worker, results = _worker([anim], out, fmt="PNG", delete=True)
        worker.run()
        assert results == [(1, 0, 0)]
        assert anim.exists() and os_trash == []

    def test_unreadable_file_is_counted_and_kept(self, tmp_path, os_trash):
        """A corrupt RAW raised libraw's own error and took the worker thread down."""
        bad_raw = tmp_path / "broken.cr2"
        bad_raw.write_bytes(b"not a raw" * 20)
        bad_png = tmp_path / "broken.png"
        bad_png.write_bytes(b"not a png")
        out = tmp_path / "out"
        out.mkdir()
        worker, results = _worker([bad_raw, bad_png], out, delete=True)
        worker.run()
        assert results == [(0, 2, 0)]
        assert bad_raw.exists() and bad_png.exists() and os_trash == []

    def test_a_replaced_original_hands_its_saved_data_to_the_conversion(self, tmp_path, os_trash):
        """Its rating and tags stayed keyed to the trashed original's path."""
        src = tmp_path / "a.png"
        Image.new("RGB", (4, 4)).save(src)
        out = tmp_path / "out"
        out.mkdir()
        worker, _results = _worker([src], out, delete=True)
        replaced = []
        worker.originals_replaced.connect(replaced.append)
        worker.run()
        assert replaced == [{str(src): str(out / "a.jpg")}]

    def test_kept_or_untrashable_originals_hand_nothing_over(self, tmp_path, monkeypatch):
        from Imervue.system import trash_ops
        src = tmp_path / "a.png"
        Image.new("RGB", (4, 4)).save(src)
        out = tmp_path / "out"
        out.mkdir()
        replaced = []
        kept, _results = _worker([src], out, delete=False)
        kept.originals_replaced.connect(replaced.append)
        kept.run()
        monkeypatch.setattr(trash_ops, "trash_batch", lambda paths: ([], list(paths)))
        refused, _results = _worker([src], out, delete=True)
        refused.originals_replaced.connect(replaced.append)
        refused.run()
        assert replaced == []

    def test_the_dialog_moves_the_saved_data_to_the_conversion(self, qapp, tmp_path):
        from types import SimpleNamespace

        from Imervue.gui.batch_convert_dialog import BatchConvertDialog
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        src, conversion = str(tmp_path / "a.cr2"), str(tmp_path / "a.jpg")
        user_setting_dict["image_ratings"] = {src: 5}
        dlg = BatchConvertDialog(SimpleNamespace(main_window=None))
        try:
            dlg._on_originals_replaced({src: conversion})  # noqa: SLF001
        finally:
            dlg.deleteLater()
        assert user_setting_dict["image_ratings"] == {conversion: 5}

    def test_failed_trash_is_logged(self, tmp_path, monkeypatch, caplog):
        from Imervue.system import trash_ops
        src = tmp_path / "a.png"
        Image.new("RGB", (4, 4)).save(src)
        out = tmp_path / "out"
        out.mkdir()
        monkeypatch.setattr(trash_ops, "trash_batch", lambda paths: ([], list(paths)))
        worker, _results = _worker([src], out, delete=True)
        with caplog.at_level("WARNING", logger="Imervue"):
            worker.run()
        assert src.exists()
        assert any("Could not move the converted original" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(("name", "deletable"), [
    ("a.svg", False), ("a.mp4", False), ("a.txt", False), ("a.png", True),
])
def test_only_raster_stills_are_trashed(tmp_path, name, deletable):
    """An SVG or a video comes out as one raster frame; its original must stay."""
    src = tmp_path / name
    Image.new("RGB", (4, 4)).save(tmp_path / "real.png")
    src.write_bytes((tmp_path / "real.png").read_bytes())
    worker, _results = _worker([src], tmp_path / "out", delete=True)
    assert worker._may_delete(str(src), str(tmp_path / "out" / "a.jpg")) is deletable  # noqa: SLF001


def test_nothing_is_trashed_when_the_output_replaced_the_source(tmp_path):
    src = tmp_path / "a.jpg"
    Image.new("RGB", (4, 4)).save(src)
    worker, _results = _worker([src], tmp_path, delete=True)
    assert worker._may_delete(str(src), str(src)) is False  # noqa: SLF001


@pytest.mark.parametrize("name", ["download.jfif", "photo.jpe", "old.jif"])
def test_a_jpeg_under_any_name_is_listed_and_skipped_as_already_jpeg(tmp_path, name):
    Image.new("RGB", (4, 4)).save(tmp_path / name, format="JPEG")
    assert _scan_folder(str(tmp_path)) == [str(tmp_path / name)]
    worker = _ConvertWorker(paths=[], output_dir=str(tmp_path), fmt="JPEG", quality=90,
                            delete_originals=False, skip_same_fmt=True)
    assert worker._should_skip(str(tmp_path / name), ".jpg")
