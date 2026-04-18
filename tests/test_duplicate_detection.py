"""
Tests for duplicate image detection — dHash, hamming distance, scanning.

No Qt dependency for core logic tests; dialog tests require ``qapp``.
"""
from __future__ import annotations

import os

import numpy as np
import pytest
from PIL import Image

from Imervue.gui.duplicate_detection_dialog import (
    _dhash,
    _hamming_distance,
    _ScanWorker,
)


# ---------------------------------------------------------------------------
# dHash (perceptual hash)
# ---------------------------------------------------------------------------

class TestDHash:
    def test_identical_images_same_hash(self):
        arr = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
        img1 = Image.fromarray(arr)
        img2 = Image.fromarray(arr.copy())
        assert _dhash(img1) == _dhash(img2)

    def test_different_images_different_hash(self):
        # Use images with actual gradient differences, not solid colors
        # (solid colors produce identical dHash since all adjacent pixels match)
        arr1 = np.zeros((64, 64, 3), dtype=np.uint8)
        arr1[:, :32] = 255  # left half white
        arr2 = np.zeros((64, 64, 3), dtype=np.uint8)
        arr2[:32, :] = 255  # top half white
        img1 = Image.fromarray(arr1)
        img2 = Image.fromarray(arr2)
        assert _dhash(img1) != _dhash(img2)

    def test_hash_is_integer(self):
        img = Image.fromarray(np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8))
        h = _dhash(img)
        assert isinstance(h, int)

    def test_hash_deterministic(self):
        arr = np.full((32, 32, 3), 128, dtype=np.uint8)
        img = Image.fromarray(arr)
        h1 = _dhash(img)
        h2 = _dhash(img)
        assert h1 == h2

    def test_similar_images_close_hash(self):
        """Slightly modified images should have small hamming distance."""
        arr = np.full((64, 64, 3), 128, dtype=np.uint8)
        img1 = Image.fromarray(arr)
        arr2 = arr.copy()
        arr2[0:5, 0:5] = 200  # Small region change
        img2 = Image.fromarray(arr2)
        dist = _hamming_distance(_dhash(img1), _dhash(img2))
        assert dist < 10  # Should be close

    def test_resized_image_close_hash(self):
        """Resized version of same image should have similar hash."""
        arr = np.random.randint(0, 256, (128, 128, 3), dtype=np.uint8)
        img_large = Image.fromarray(arr)
        img_small = img_large.resize((64, 64))
        dist = _hamming_distance(_dhash(img_large), _dhash(img_small))
        assert dist < 15  # Resized images should be somewhat close

    def test_grayscale_input(self):
        """dHash should handle grayscale images."""
        arr = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
        img = Image.fromarray(arr, mode="L")
        h = _dhash(img)
        assert isinstance(h, int)


# ---------------------------------------------------------------------------
# Hamming distance
# ---------------------------------------------------------------------------

class TestHammingDistance:
    def test_same_values(self):
        assert _hamming_distance(0, 0) == 0
        assert _hamming_distance(42, 42) == 0

    def test_one_bit_difference(self):
        assert _hamming_distance(0b0000, 0b0001) == 1
        assert _hamming_distance(0b1010, 0b1011) == 1

    def test_all_bits_different(self):
        assert _hamming_distance(0b0000, 0b1111) == 4

    def test_large_values(self):
        a = (1 << 64) - 1  # all 1s
        b = 0
        assert _hamming_distance(a, b) == 64


# ---------------------------------------------------------------------------
# File scanning and duplicate detection (integration)
# ---------------------------------------------------------------------------

@pytest.fixture
def dup_folder(tmp_path):
    """Create a folder with some duplicate and unique images."""
    # Two identical images
    arr_a = np.full((32, 32, 3), 100, dtype=np.uint8)
    img_a = Image.fromarray(arr_a)
    img_a.save(str(tmp_path / "dup1.png"), format="PNG")
    img_a.save(str(tmp_path / "dup2.png"), format="PNG")

    # One unique image
    arr_b = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
    img_b = Image.fromarray(arr_b)
    img_b.save(str(tmp_path / "unique.png"), format="PNG")

    return str(tmp_path)


@pytest.fixture
def dup_folder_with_subfolder(dup_folder, tmp_path):
    """Extend dup_folder with a subfolder containing another duplicate."""
    sub = tmp_path / "sub"
    sub.mkdir()
    arr_a = np.full((32, 32, 3), 100, dtype=np.uint8)
    img_a = Image.fromarray(arr_a)
    img_a.save(str(sub / "dup3.png"), format="PNG")
    return dup_folder


class TestScanWorkerCollect:
    def test_collect_flat(self, dup_folder):
        worker = _ScanWorker(dup_folder, "exact", 5, recursive=False)
        paths = worker._collect_paths()
        assert len(paths) == 3
        names = {os.path.basename(p) for p in paths}
        assert names == {"dup1.png", "dup2.png", "unique.png"}

    def test_collect_recursive(self, dup_folder_with_subfolder):
        worker = _ScanWorker(
            dup_folder_with_subfolder, "exact", 5, recursive=True)
        paths = worker._collect_paths()
        assert len(paths) == 4  # 3 in root + 1 in sub

    def test_ignores_non_image_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "data.csv").write_text("a,b,c")
        arr = np.full((10, 10, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(str(tmp_path / "img.png"))
        worker = _ScanWorker(str(tmp_path), "exact", 5, recursive=False)
        paths = worker._collect_paths()
        assert len(paths) == 1


class TestScanWorkerHash:
    def test_exact_hash_identical_files(self, dup_folder):
        worker = _ScanWorker(dup_folder, "exact", 5, recursive=False)
        h1 = worker._file_hash(os.path.join(dup_folder, "dup1.png"))
        h2 = worker._file_hash(os.path.join(dup_folder, "dup2.png"))
        assert h1 == h2

    def test_exact_hash_different_files(self, dup_folder):
        worker = _ScanWorker(dup_folder, "exact", 5, recursive=False)
        h1 = worker._file_hash(os.path.join(dup_folder, "dup1.png"))
        h3 = worker._file_hash(os.path.join(dup_folder, "unique.png"))
        assert h1 != h3

    def test_perceptual_hash_returns_string(self, dup_folder):
        worker = _ScanWorker(dup_folder, "perceptual", 5, recursive=False)
        h = worker._perceptual_hash(os.path.join(dup_folder, "dup1.png"))
        assert isinstance(h, str)


class TestScanWorkerClustering:
    def test_cluster_identical_hashes(self):
        """Entries with identical hashes should cluster together."""
        worker = _ScanWorker("", "perceptual", 5, recursive=False)
        hash_map = {
            "100": [("/a.png", 1000), ("/b.png", 1000)],
            "999999": [("/c.png", 2000)],  # far from 100
        }
        groups = worker._cluster_perceptual(hash_map)
        # /a.png and /b.png share hash 100, so they cluster
        found = False
        for g in groups:
            paths = {p for p, _ in g}
            if "/a.png" in paths and "/b.png" in paths:
                found = True
        assert found, f"Expected /a.png and /b.png to cluster, got {groups}"

    def test_cluster_close_hashes(self):
        """Hashes within threshold should cluster."""
        worker = _ScanWorker("", "perceptual", 5, recursive=False)
        hash_map = {
            "0": [("/a.png", 1000)],    # hamming distance 0→1 = 1
            "1": [("/b.png", 1000)],
            "1000": [("/c.png", 2000)],  # far away
        }
        groups = worker._cluster_perceptual(hash_map)
        assert len(groups) == 1
        paths = {p for p, _ in groups[0]}
        assert paths == {"/a.png", "/b.png"}

    def test_cluster_no_duplicates(self):
        worker = _ScanWorker("", "perceptual", 0, recursive=False)
        hash_map = {
            "100": [("/a.png", 1000)],
            "200": [("/b.png", 2000)],
        }
        groups = worker._cluster_perceptual(hash_map)
        assert len(groups) == 0


# ---------------------------------------------------------------------------
# Full scan integration test (uses QThread but we call .run() directly)
# ---------------------------------------------------------------------------

class TestScanWorkerRun:
    def test_exact_scan_finds_duplicates(self, dup_folder):
        worker = _ScanWorker(dup_folder, "exact", 5, recursive=False)
        results = []
        worker.result_ready.connect(results.append)
        worker.run()  # Direct call, not threaded
        assert len(results) == 1
        groups = results[0]
        assert len(groups) == 1  # one group of duplicates
        paths = {os.path.basename(p) for p, _ in groups[0]}
        assert paths == {"dup1.png", "dup2.png"}

    def test_perceptual_scan_finds_duplicates(self, dup_folder):
        worker = _ScanWorker(dup_folder, "perceptual", 10, recursive=False)
        results = []
        worker.result_ready.connect(results.append)
        worker.run()
        assert len(results) == 1
        groups = results[0]
        # At minimum the identical files should cluster
        assert len(groups) >= 1
        all_paths = set()
        for g in groups:
            for p, _ in g:
                all_paths.add(os.path.basename(p))
        assert "dup1.png" in all_paths and "dup2.png" in all_paths

    def test_empty_folder(self, tmp_path):
        worker = _ScanWorker(str(tmp_path), "exact", 5, recursive=False)
        results = []
        worker.result_ready.connect(results.append)
        worker.run()
        assert len(results) == 1
        assert results[0] == []

    def test_abort_stops_scan(self, dup_folder):
        worker = _ScanWorker(dup_folder, "exact", 5, recursive=False)
        worker.abort()
        results = []
        worker.result_ready.connect(results.append)
        worker.run()
        # Aborted — no result emitted
        assert len(results) == 0
