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

from Imervue.gui.image_organizer_dialog import (
    _scan_folder,
    plan_organization,
    _OrganizerWorker,
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
