"""The deflicker worker must always emit finished_with_count.

mkdir and the luminance/gain computation ran outside the narrow inner except, so
a read-only output folder or a compute failure escaped run(), the completion
signal never fired, and the dialog hung. run() now wraps everything.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from Imervue.gui import deflicker_dialog
from Imervue.gui.deflicker_dialog import DeflickerWorker
from Imervue.image.deflicker import DeflickerOptions


def _frames(tmp_path, n=2):
    paths = []
    for i in range(n):
        p = tmp_path / f"f{i}.png"
        Image.fromarray(np.zeros((4, 4, 4), dtype=np.uint8), mode="RGBA").save(str(p))
        paths.append(str(p))
    return paths


def _opts():
    return DeflickerOptions(rolling_window=9, target_mode="rolling")


def test_worker_emits_finished_even_when_processing_raises(tmp_path, qapp, monkeypatch):
    paths = _frames(tmp_path)

    def _boom(_frames):
        raise MemoryError("out of memory")

    monkeypatch.setattr(deflicker_dialog, "frame_luminance_means", _boom)
    results: list = []
    worker = DeflickerWorker(paths, _opts())
    worker.finished_with_count.connect(results.append)
    worker.run()
    assert results == [0]           # reported despite the failure, not hung


def test_worker_writes_and_reports_on_success(tmp_path, qapp):
    paths = _frames(tmp_path)
    results: list = []
    worker = DeflickerWorker(paths, _opts())
    worker.finished_with_count.connect(results.append)
    worker.run()
    assert results == [2]
    assert (tmp_path / "deflickered").is_dir()


def test_load_frames_keeps_index_alignment_for_unreadable_input(tmp_path, qapp):
    """An undecodable file becomes None instead of shifting later frames."""
    paths = _frames(tmp_path, n=2)
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")
    ordered = [paths[0], str(broken), paths[1]]

    progress: list = []
    worker = DeflickerWorker(ordered, _opts())
    worker.progress.connect(progress.append)
    frames = worker._load_frames()

    assert len(frames) == 3
    assert frames[1] is None                    # the placeholder holds the slot
    assert frames[0] is not None and frames[2] is not None
    assert progress == [1, 2, 3]                # progress still counts every path


def test_write_corrected_skips_none_frames(tmp_path, qapp):
    paths = _frames(tmp_path, n=2)
    worker = DeflickerWorker(paths, _opts())
    frames = worker._load_frames()

    assert worker._write_corrected([frames[0], None]) == 1
    assert worker._write_corrected([None, None]) == 0


def test_write_corrected_returns_zero_when_nothing_decoded(tmp_path, qapp):
    worker = DeflickerWorker([str(tmp_path / "missing.png")], _opts())
    assert worker._write_corrected([None]) == 0


def test_write_one_reports_failure_instead_of_raising(tmp_path, qapp, monkeypatch):
    """A read-only destination skips the frame; the run must not abort."""
    paths = _frames(tmp_path, n=1)
    worker = DeflickerWorker(paths, _opts())
    frame = worker._load_frames()[0]

    def _deny(*_a, **_k):
        raise OSError("read-only volume")

    monkeypatch.setattr(deflicker_dialog.Path, "mkdir", _deny)
    assert worker._write_one(paths[0], frame) is False
    assert worker._write_corrected([frame]) == 0


def test_jpeg_time_lapse_is_written_as_jpeg_with_its_exif(tmp_path, qapp):
    """Every JPEG frame failed: an RGBA array can't be saved under a .jpg name."""
    from PIL import Image
    paths = []
    for index, level in enumerate((100, 140, 90)):
        exif = Image.Exif()
        exif.get_ifd(0x8769)[0x9003] = f"2020:01:02 03:04:0{index}"
        path = tmp_path / f"f{index}.jpg"
        Image.new("RGB", (16, 8), (level,) * 3).save(path, quality=95, exif=exif)
        paths.append(str(path))
    worker = DeflickerWorker(paths, _opts())
    assert worker._write_corrected(worker._load_frames()) == 3
    for index in range(3):
        with Image.open(tmp_path / "deflickered" / f"f{index}.jpg") as out:
            assert out.format == "JPEG"
            assert out.getexif().get_ifd(0x8769)[0x9003] == f"2020:01:02 03:04:0{index}"


def test_raw_frames_are_developed_and_written_as_png(tmp_path, qapp, monkeypatch):
    import numpy as np
    from PIL import Image

    from Imervue.gpu_image_view.images import image_loader
    monkeypatch.setattr(image_loader, "_load_raw",
                        lambda _p, thumbnail: np.full((30, 50, 3), 90, dtype=np.uint8))
    paths = [str(tmp_path / f"f{i}.cr2") for i in range(2)]
    worker = DeflickerWorker(paths, _opts())
    assert worker._write_corrected(worker._load_frames()) == 2
    with Image.open(tmp_path / "deflickered" / "f0.png") as out:
        assert out.size == (50, 30)


def test_tagged_frames_are_corrected_upright(tmp_path, qapp):
    from PIL import Image

    from _decode_samples import tagged_portrait
    paths = [str(tagged_portrait(tmp_path / f"f{i}.png")) for i in range(2)]
    worker = DeflickerWorker(paths, _opts())
    worker._write_corrected(worker._load_frames())
    with Image.open(tmp_path / "deflickered" / "f0.png") as out:
        assert out.size == (20, 40)
