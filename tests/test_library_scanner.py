"""Tests for the headless library scanner."""
from __future__ import annotations

import os

import numpy as np
import pytest
from PIL import Image

from Imervue.library import image_index, scanner


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


@pytest.fixture
def tree(tmp_path):
    """A small on-disk library tree with mixed extensions."""
    root = tmp_path / "lib"
    sub = root / "sub"
    sub.mkdir(parents=True)

    arr = np.zeros((16, 16, 3), dtype=np.uint8)
    images = [
        root / "a.png",
        root / "b.jpg",
        sub / "c.png",
    ]
    for p in images:
        Image.fromarray(arr).save(str(p))

    # Files that should be ignored.
    (root / "notes.txt").write_text("hello", encoding="utf-8")
    (sub / "meta.json").write_text("{}", encoding="utf-8")

    return root, [str(p) for p in images]


class TestIterImages:
    def test_yields_only_image_extensions(self, tree):
        root, images = tree
        found = {str(p) for p in scanner._iter_images(str(root))}
        assert found == set(images)

    def test_walks_subdirectories(self, tree):
        root, images = tree
        assert any(os.path.sep + "sub" + os.path.sep in p for p in images)
        yielded = {os.path.normpath(str(p)) for p in scanner._iter_images(str(root))}
        assert any("sub" in p for p in yielded)

    def test_missing_root_yields_nothing(self, tmp_path):
        ghost = tmp_path / "no_such_dir"
        assert list(scanner._iter_images(str(ghost))) == []


class TestLibraryScanner:
    def test_run_indexes_every_image(self, tree, qapp):
        root, images = tree
        s = scanner.LibraryScanner([str(root)], with_phash=False)
        done_totals: list[int] = []
        s.done.connect(done_totals.append)
        s.run()
        assert done_totals == [3]
        for p in images:
            assert image_index.get_image(p) is not None

    def test_progress_emits_on_completion(self, tree, qapp):
        root, _ = tree
        s = scanner.LibraryScanner([str(root)], with_phash=False)
        events: list[tuple[int, int, str]] = []
        s.progress.connect(lambda i, n, p: events.append((i, n, p)))
        s.run()
        # Final progress row must always fire (i == total).
        assert events and events[-1][0] == events[-1][1] == 3

    def test_cancel_halts_scan(self, tree, qapp):
        root, _ = tree
        s = scanner.LibraryScanner([str(root)], with_phash=False)
        s.cancel()
        s.run()
        assert image_index.count_images() == 0

    def test_non_directory_root_is_skipped(self, tmp_path, qapp):
        not_a_dir = tmp_path / "not_real"
        s = scanner.LibraryScanner([str(not_a_dir)], with_phash=False)
        done: list[int] = []
        s.done.connect(done.append)
        s.run()
        assert done == [0]

    def test_error_signal_on_exception(self, tree, qapp, monkeypatch):
        root, _ = tree
        monkeypatch.setattr(
            scanner, "_iter_images",
            lambda _root: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        s = scanner.LibraryScanner([str(root)], with_phash=False)
        errors: list[str] = []
        s.error.connect(errors.append)
        s.run()
        assert errors == ["boom"]


class TestIndexOne:
    def test_width_height_recorded_when_with_phash(self, tree):
        _, images = tree
        scanner._index_one(__import__("pathlib").Path(images[0]), with_phash=True)
        row = image_index.get_image(images[0])
        assert row is not None
        assert row["width"] == 16
        assert row["height"] == 16

    def test_missing_file_is_silently_skipped(self, tmp_path):
        ghost = tmp_path / "ghost.png"
        scanner._index_one(ghost, with_phash=False)
        # No exception, no entry.
        assert image_index.get_image(str(ghost)) is None
