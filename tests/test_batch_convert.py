"""
Tests for batch format conversion — scanning, worker logic, format handling.

Core logic tests are pure Python (no Qt needed for the scan function).
Worker tests call .run() directly (no thread) and require ``qapp``.
"""
from __future__ import annotations

import os

import numpy as np
from PIL import Image

from Imervue.gui.batch_convert_dialog import _scan_folder, _ConvertWorker


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
        success, failed, skipped = results[0]
        assert success == 1
        assert failed == 0
        # Output file exists
        out_files = list(out.iterdir())
        assert len(out_files) == 1
        assert out_files[0].suffix == ".jpg"

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

        success, failed, skipped = results[0]
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
            arr = np.random.randint(0, 256, (16, 16, 3), dtype=np.uint8)
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

        success, failed, skipped = results[0]
        assert success == 5
        out_files = list(out.iterdir())
        assert len(out_files) == 5
        assert all(f.suffix == ".webp" for f in out_files)
