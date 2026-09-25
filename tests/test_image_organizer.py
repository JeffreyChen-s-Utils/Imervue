"""
Tests for image organizer — folder scanning, planning logic, worker.

Core planning tests are pure Python (no Qt needed).
Worker tests call .run() directly and require ``qapp``.
"""
from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import pytest
from PIL import Image

from types import SimpleNamespace

from Imervue.gui.image_organizer_dialog import (
    ImageOrganizerDialog,
    _scan_folder,
    plan_organization,
    _OrganizerWorker,
    _get_resolution_bucket,
    _get_type_bucket,
    RULE_DATE,
    RULE_RESOLUTION,
    RULE_TYPE,
    RULE_SIZE,
    RULE_COUNT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def img_folder(tmp_path):
    """Create a folder with a few test images of varying sizes."""
    for name, size in [("a.png", (64, 64)), ("b.jpg", (1920, 1080)),
                       ("c.webp", (4000, 3000)), ("d.bmp", (320, 240))]:
        arr = np.full((*size[::-1], 3), 128, dtype=np.uint8)
        img = Image.fromarray(arr)
        fmt = {"png": "PNG", "jpg": "JPEG", "webp": "WebP", "bmp": "BMP"}
        img.save(str(tmp_path / name), format=fmt[name.rsplit(".", 1)[1]])
    return str(tmp_path)


# ---------------------------------------------------------------------------
# Scan folder
# ---------------------------------------------------------------------------

class TestScanFolder:
    def test_finds_images(self, img_folder):
        paths = _scan_folder(img_folder)
        assert len(paths) == 4

    def test_takes_every_still_format_but_not_video(self, tmp_path):
        """iPhone HEIC and camera RAW photos used to be left behind by the organizer."""
        for name in ("a.heic", "b.cr2", "c.NEF", "d.jxl", "e.avif", "f.png", "g.mp4", "h.txt"):
            (tmp_path / name).write_bytes(b"x")
        names = [os.path.basename(p) for p in _scan_folder(str(tmp_path))]
        assert names == ["a.heic", "b.cr2", "c.NEF", "d.jxl", "e.avif", "f.png"]

    def test_ignores_non_images(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hi")
        arr = np.full((10, 10, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(str(tmp_path / "x.png"))
        assert len(_scan_folder(str(tmp_path))) == 1

    def test_empty_folder(self, tmp_path):
        assert _scan_folder(str(tmp_path)) == []

    def test_sorted(self, tmp_path):
        for n in ["c.png", "a.png", "b.png"]:
            arr = np.full((10, 10, 3), 128, dtype=np.uint8)
            Image.fromarray(arr).save(str(tmp_path / n))
        names = [os.path.basename(p) for p in _scan_folder(str(tmp_path))]
        assert names == ["a.png", "b.png", "c.png"]


# ---------------------------------------------------------------------------
# Plan: by type
# ---------------------------------------------------------------------------

class TestPlanByType:
    def test_groups_by_extension(self, img_folder):
        paths = _scan_folder(img_folder)
        plan = plan_organization(paths, rule=RULE_TYPE)
        assert "PNG" in plan
        assert "JPG" in plan
        assert "WEBP" in plan
        assert "BMP" in plan

    def test_jpg_jpeg_merged(self, tmp_path):
        for ext in ["test.jpg", "test2.jpeg"]:
            arr = np.full((10, 10, 3), 128, dtype=np.uint8)
            Image.fromarray(arr).save(str(tmp_path / ext), format="JPEG")
        paths = _scan_folder(str(tmp_path))
        plan = plan_organization(paths, rule=RULE_TYPE)
        assert "JPG" in plan
        assert len(plan["JPG"]) == 2
        assert "JPEG" not in plan


class TestGetTypeBucket:
    def test_jpg(self):
        assert _get_type_bucket("photo.jpg") == "JPG"

    def test_jpeg(self):
        assert _get_type_bucket("photo.jpeg") == "JPG"

    def test_png(self):
        assert _get_type_bucket("image.png") == "PNG"


# ---------------------------------------------------------------------------
# Plan: by resolution
# ---------------------------------------------------------------------------

class TestPlanByResolution:
    def test_buckets(self, img_folder):
        paths = _scan_folder(img_folder)
        plan = plan_organization(paths, rule=RULE_RESOLUTION)
        # 64x64 → small, 1920x1080 → 1080p+, 4000x3000 → 4K+, 320x240 → small
        assert "small" in plan
        assert "1080p+" in plan
        assert "4K+" in plan

    def test_small_images(self, tmp_path):
        arr = np.full((100, 100, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(str(tmp_path / "tiny.png"))
        paths = _scan_folder(str(tmp_path))
        plan = plan_organization(paths, rule=RULE_RESOLUTION)
        assert "small" in plan


# ---------------------------------------------------------------------------
# Plan: by size
# ---------------------------------------------------------------------------

class TestPlanBySize:
    def test_size_classification(self, img_folder):
        paths = _scan_folder(img_folder)
        plan = plan_organization(paths, rule=RULE_SIZE, large_mb=5, small_mb=1)
        # All test images are small (< 1 MB)
        all_paths = []
        for bucket_paths in plan.values():
            all_paths.extend(bucket_paths)
        assert len(all_paths) == 4

    def test_custom_thresholds(self, tmp_path):
        # Create a small file
        arr = np.full((10, 10, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(str(tmp_path / "small.png"))
        paths = _scan_folder(str(tmp_path))
        plan = plan_organization(paths, rule=RULE_SIZE, large_mb=5, small_mb=1)
        assert "small" in plan


# ---------------------------------------------------------------------------
# Plan: by count
# ---------------------------------------------------------------------------

class TestPlanByCount:
    def test_splits_evenly(self, tmp_path):
        for i in range(10):
            arr = np.full((10, 10, 3), 128, dtype=np.uint8)
            Image.fromarray(arr).save(str(tmp_path / f"img{i:02d}.png"))
        paths = _scan_folder(str(tmp_path))
        plan = plan_organization(paths, rule=RULE_COUNT, count_per_folder=3)
        # 10 images / 3 per folder = 4 folders (3+3+3+1)
        assert len(plan) == 4
        assert len(plan["001"]) == 3
        assert len(plan["004"]) == 1

    def test_single_folder(self, tmp_path):
        for i in range(5):
            arr = np.full((10, 10, 3), 128, dtype=np.uint8)
            Image.fromarray(arr).save(str(tmp_path / f"img{i}.png"))
        paths = _scan_folder(str(tmp_path))
        plan = plan_organization(paths, rule=RULE_COUNT, count_per_folder=100)
        assert len(plan) == 1


# ---------------------------------------------------------------------------
# Plan: by date
# ---------------------------------------------------------------------------

class TestPlanByDate:
    def test_groups_by_mtime(self, tmp_path):
        arr = np.full((10, 10, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(str(tmp_path / "img.png"))
        paths = _scan_folder(str(tmp_path))
        plan = plan_organization(paths, rule=RULE_DATE, year_only=False)
        # Should have at least one bucket with current year-month
        now = datetime.now().strftime("%Y-%m")
        assert now in plan

    def test_year_only(self, tmp_path):
        arr = np.full((10, 10, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(str(tmp_path / "img.png"))
        paths = _scan_folder(str(tmp_path))
        plan = plan_organization(paths, rule=RULE_DATE, year_only=True)
        now = datetime.now().strftime("%Y")
        assert now in plan


# ---------------------------------------------------------------------------
# Worker (copy mode)
# ---------------------------------------------------------------------------

class TestOrganizerWorker:
    def test_copy_creates_subfolders(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        for name in ["a.png", "b.png"]:
            arr = np.full((10, 10, 3), 128, dtype=np.uint8)
            Image.fromarray(arr).save(str(src / name))

        out = tmp_path / "out"
        out.mkdir()

        plan = {"group1": [str(src / "a.png")], "group2": [str(src / "b.png")]}
        worker = _OrganizerWorker(plan, str(out), move=False)
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert results == [(2, 0)]
        assert (out / "group1" / "a.png").exists()
        assert (out / "group2" / "b.png").exists()
        # Source still exists (copy mode)
        assert (src / "a.png").exists()

    def test_an_unwritable_output_folder_is_reported_not_fatal(self, tmp_path):
        """os.makedirs raised outside any try: result_ready never came and the dialog hung."""
        src = tmp_path / "src"
        src.mkdir()
        for name in ["a.png", "b.png"]:
            Image.fromarray(np.full((4, 4, 3), 9, dtype=np.uint8)).save(str(src / name))
        out = tmp_path / "out"
        out.mkdir()
        (out / "blocked").write_bytes(b"a file where the group folder should go")
        plan = {"blocked": [str(src / "a.png")], "fine": [str(src / "b.png")]}
        worker = _OrganizerWorker(plan, str(out), move=False)
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()
        assert results == [(1, 1)]
        assert (out / "fine" / "b.png").exists()

    def test_move_removes_source(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        arr = np.full((10, 10, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(str(src / "img.png"))

        out = tmp_path / "out"
        out.mkdir()

        plan = {"moved": [str(src / "img.png")]}
        worker = _OrganizerWorker(plan, str(out), move=True)
        worker.run()

        assert (out / "moved" / "img.png").exists()
        assert not (src / "img.png").exists()

    def test_move_takes_the_sidecar_and_reports_the_moves(self, tmp_path):
        """The organizer moved IMG.CR2 and left IMG.xmp (and its rating) behind."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "IMG.CR2").write_bytes(b"raw")
        (src / "IMG.xmp").write_text("edits", encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        worker = _OrganizerWorker({"raw": [str(src / "IMG.CR2")]}, str(out), move=True)
        moves = []
        worker.files_moved.connect(moves.append)
        worker.run()
        assert (out / "raw" / "IMG.xmp").read_text(encoding="utf-8") == "edits"
        assert moves == [{str(src / "IMG.CR2"): str(out / "raw" / "IMG.CR2")}]

    def test_copy_copies_the_sidecar_and_reports_no_moves(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "IMG.JPG").write_bytes(b"jpg")
        (src / "IMG.JPG.xmp").write_text("edits", encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        worker = _OrganizerWorker({"jpg": [str(src / "IMG.JPG")]}, str(out), move=False)
        moves = []
        worker.files_moved.connect(moves.append)
        worker.run()
        assert (src / "IMG.JPG.xmp").exists()
        assert (out / "jpg" / "IMG.JPG.xmp").exists()
        assert moves == []

    def test_the_dialog_re_keys_saved_data_on_its_own_thread(
            self, qapp, tmp_path, pump_until, monkeypatch):
        """Settings must not be changed from the worker thread while the GUI reads them."""
        import threading
        from types import SimpleNamespace

        from Imervue.gui import image_organizer_dialog as mod
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.png").write_bytes(b"png")
        out = tmp_path / "out"
        out.mkdir()
        user_setting_dict["image_ratings"] = {str(src / "a.png"): 4}
        threads = []
        real_follow = mod.follow_saved_data

        def follow(moved):
            threads.append(threading.current_thread() is threading.main_thread())
            real_follow(moved)

        monkeypatch.setattr(mod, "follow_saved_data", follow)
        gui = SimpleNamespace(main_window=None, model=SimpleNamespace(folder_path=str(src)))
        dlg = mod.ImageOrganizerDialog(gui, str(src))
        worker = mod._OrganizerWorker({"g": [str(src / "a.png")]}, str(out), move=True)
        dlg._worker = worker  # noqa: SLF001
        worker.files_moved.connect(dlg._on_files_moved)  # noqa: SLF001
        try:
            worker.start()
            pump_until(lambda: threads)
        finally:
            worker.wait(5000)
            dlg._worker = None  # noqa: SLF001
            dlg.deleteLater()
        assert threads == [True]
        assert user_setting_dict["image_ratings"] == {str(out / "g" / "a.png"): 4}

    def test_name_collision_handled(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        arr = np.full((10, 10, 3), 128, dtype=np.uint8)
        p1 = src / "img.png"
        Image.fromarray(arr).save(str(p1))

        out = tmp_path / "out"
        out.mkdir()
        # Pre-create the destination to force collision
        dest_dir = out / "grp"
        dest_dir.mkdir()
        Image.fromarray(arr).save(str(dest_dir / "img.png"))

        plan = {"grp": [str(p1)]}
        worker = _OrganizerWorker(plan, str(out), move=False)
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert results == [(1, 0)]
        assert (dest_dir / "img_1.png").exists()

    def test_abort_stops_early(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        for i in range(5):
            arr = np.full((10, 10, 3), 128, dtype=np.uint8)
            Image.fromarray(arr).save(str(src / f"img{i}.png"))

        out = tmp_path / "out"
        out.mkdir()

        paths = [str(src / f"img{i}.png") for i in range(5)]
        plan = {"all": paths}
        worker = _OrganizerWorker(plan, str(out), move=False)
        worker.abort()
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert len(results) == 1
        assert results[0][0] == 0  # nothing processed


class TestPlanInvalidation:
    """Changing any plan input after Preview must force a re-Preview.

    ``_do_start`` executes ``_last_plan`` captured at Preview time, so a stale
    plan would move/copy files by a rule the UI no longer shows. These drive the
    methods unbound on fakes -- no Qt widget constructed.
    """

    def test_invalidate_clears_plan_and_disables_start(self):
        enabled: list = []
        fake = SimpleNamespace(
            _last_plan={"2024-01": ["a.png"]},
            _start_btn=SimpleNamespace(setEnabled=enabled.append),
        )
        ImageOrganizerDialog._invalidate_plan(fake)
        assert fake._last_plan == {}
        assert enabled == [False]

    def test_invalidate_accepts_a_signal_argument(self):
        # valueChanged / currentIndexChanged / textChanged all pass an argument.
        enabled: list = []
        fake = SimpleNamespace(
            _last_plan={"x": ["y"]},
            _start_btn=SimpleNamespace(setEnabled=enabled.append),
        )
        ImageOrganizerDialog._invalidate_plan(fake, 7)   # must not raise
        assert fake._last_plan == {}
        assert enabled == [False]

    def test_rule_change_invalidates_plan(self):
        calls: list = []
        fake = SimpleNamespace(
            _rule_combo=SimpleNamespace(currentData=lambda: RULE_SIZE),
            _set_widgets_visible=lambda widgets, visible: None,
            _date_row_widgets=[],
            _size_row_widgets=[],
            _count_row_widgets=[],
            _invalidate_plan=lambda: calls.append("invalidate"),
        )
        ImageOrganizerDialog._on_rule_changed(fake, 3)
        assert calls == ["invalidate"]


class TestGetResolutionBucket:
    @pytest.mark.parametrize("size, bucket", [
        ((3840, 10), "4K+"), ((10, 1920), "1080p+"), ((1280, 720), "720p+"), ((1279, 1), "small"),
    ])
    def test_buckets_by_long_edge(self, tmp_path, size, bucket):
        path = tmp_path / "a.png"
        Image.new("L", size).save(path)
        assert _get_resolution_bucket(str(path)) == bucket

    def test_unreadable_files_are_unknown(self, tmp_path):
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not a png")
        assert _get_resolution_bucket(str(bad)) == "unknown"
        assert _get_resolution_bucket(str(tmp_path / "gone.png")) == "unknown"

    def test_unexpected_error_propagates(self, monkeypatch):
        def boom(_path):
            raise RuntimeError("bug")

        monkeypatch.setattr(Image, "open", boom)
        with pytest.raises(RuntimeError):
            _get_resolution_bucket("x.png")


class TestImageDateBucket:
    def test_exif_date_wins_then_mtime(self, tmp_path):
        from Imervue.gui.image_organizer_dialog import _get_image_date
        path = tmp_path / "a.jpg"
        exif = Image.Exif()
        exif[36867] = "2019:02:03 04:05:06"
        Image.new("RGB", (4, 4)).save(path, exif=exif)
        assert _get_image_date(str(path), year_only=False) == "2019-02"
        bad = tmp_path / "bad.jpg"
        bad.write_bytes(b"not an image")
        stamp = datetime(2021, 7, 1, 12).timestamp()
        os.utime(bad, (stamp, stamp))
        assert _get_image_date(str(bad), year_only=True) == "2021"

    def test_corrupt_webp_exif_falls_back_to_mtime(self, tmp_path):
        from test_read_errors import corrupt_exif_webp

        from Imervue.gui.image_organizer_dialog import _get_image_date
        path = tmp_path / "a.webp"
        path.write_bytes(corrupt_exif_webp())
        stamp = datetime(2017, 5, 1, 12).timestamp()
        os.utime(path, (stamp, stamp))
        assert _get_image_date(str(path), year_only=True) == "2017"

    def test_unparsable_exif_date_falls_back(self, tmp_path):
        from Imervue.gui.image_organizer_dialog import _get_image_date
        path = tmp_path / "a.jpg"
        exif = Image.Exif()
        exif[36867] = "not a date"
        Image.new("RGB", (4, 4)).save(path, exif=exif)
        stamp = datetime(2018, 1, 1, 12).timestamp()
        os.utime(path, (stamp, stamp))
        assert _get_image_date(str(path), year_only=True) == "2018"

    def test_unexpected_error_propagates(self, tmp_path, monkeypatch):
        from Imervue.gui import image_organizer_dialog as mod

        def boom(_path):
            raise RuntimeError("bug")

        monkeypatch.setattr(Image, "open", boom)
        with pytest.raises(RuntimeError):
            mod._get_image_date(str(tmp_path / "a.jpg"), year_only=True)


def _photo_with_original_date(path, when="2019:05:06 07:08:09"):
    """A JPEG whose only date is DateTimeOriginal, in the Exif sub-IFD where cameras put it."""
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = when
    Image.new("RGB", (4, 4)).save(path, exif=exif)
    return path


def test_date_bucket_reads_date_time_original_from_the_exif_sub_ifd(tmp_path):
    """It read IFD0 only, so a camera's DateTimeOriginal was never seen."""
    from Imervue.gui.image_organizer_dialog import _get_image_date
    path = _photo_with_original_date(tmp_path / "a.jpg")
    assert _get_image_date(str(path), year_only=False) == "2019-05"


def test_date_bucket_of_a_missing_file_is_unknown(tmp_path):
    from Imervue.gui.image_organizer_dialog import _get_image_date
    assert _get_image_date(str(tmp_path / "gone.jpg"), year_only=True) == "unknown"
