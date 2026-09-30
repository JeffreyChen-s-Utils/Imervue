"""Tests for the headless library scanner."""
from __future__ import annotations

import os
from pathlib import Path

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

        def _boom(_root):
            raise RuntimeError("boom")

        monkeypatch.setattr(scanner, "_iter_images", _boom)
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


class TestScanWithPhash:
    def test_scan_with_phash_indexes_photolike_images(self, tmp_path, qapp):
        """Regression: a non-flat image's 64-bit pHash has its high bit set,
        which used to overflow SQLite's signed INTEGER, roll back the batch,
        and abort the entire scan with zero images indexed. With pHash on (the
        default), every image must now be indexed and carry a stored hash."""
        root = tmp_path / "lib"
        root.mkdir()
        rng = np.random.default_rng(7)
        paths = []
        for i in range(3):
            arr = (rng.random((32, 32, 3)) * 255).astype(np.uint8)
            pth = root / f"img{i}.png"
            Image.fromarray(arr).save(str(pth))
            paths.append(str(pth))

        s = scanner.LibraryScanner([str(root)], with_phash=True)
        errors: list[str] = []
        s.error.connect(errors.append)
        s.run()

        assert errors == []
        assert image_index.count_images() == 3
        for p in paths:
            row = image_index.get_image(p)
            assert row is not None
            assert row["phash"] is not None


def test_index_one_indexes_an_unreadable_file_without_size(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    assert scanner._index_one(bad, with_phash=True) is True
    row = image_index.get_image(str(bad))
    assert row is not None
    assert row["width"] is None


def test_index_one_propagates_an_unexpected_reader_error(tmp_path, monkeypatch):
    img = tmp_path / "a.png"
    Image.new("RGB", (4, 4)).save(img)

    def broken(*_args, **_kwargs):
        raise RuntimeError("reader bug")

    monkeypatch.setattr(Image, "open", broken)
    with pytest.raises(RuntimeError, match="reader bug"):
        scanner._index_one(img, with_phash=True)


def test_scanner_walks_exactly_what_maintenance_diffs_against(tmp_path):
    """Maintenance counted HEIC / JXL as new files that no rescan ever indexed."""
    from Imervue.library.maintenance import scan_image_files
    for name in ("a.heic", "b.jxl", "c.svg", "d.png", "e.mp4", "f.txt"):
        (tmp_path / name).write_bytes(b"\x00")
    walked = {str(p) for p in scanner._iter_images(str(tmp_path))}
    assert walked == set(scan_image_files([str(tmp_path)]))
    assert {Path(p).name for p in walked} == {"a.heic", "b.jxl", "c.svg", "d.png"}


def test_index_one_registers_the_codec_before_reading(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(scanner, "ensure_pillow_opener", seen.append)
    img = tmp_path / "a.heic"
    img.write_bytes(b"not decodable")
    assert scanner._index_one(img, with_phash=True) is True
    assert seen == [".heic"]


# --- incremental and parallel scanning ---------------------------------------

def _noise(path, seed=0):
    rng = np.random.default_rng(seed)
    Image.fromarray((rng.random((32, 32, 3)) * 255).astype(np.uint8)).save(str(path))
    return str(path)


def _scan(root, *, with_phash=True):
    s = scanner.LibraryScanner([str(root)], with_phash=with_phash)
    errors: list[str] = []
    s.error.connect(errors.append)
    s.run()
    assert errors == []
    return s


@pytest.mark.parametrize(("cpus", "workers"), [(None, 1), (1, 1), (2, 1), (4, 3), (64, 8)])
def test_probe_workers_leave_a_core_for_the_ui_and_stop_at_eight(cpus, workers, monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: None)
    assert scanner.probe_workers(cpus) == workers


def test_probe_workers_default_to_the_machine(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 6)
    assert scanner.probe_workers() == 5


def test_a_rescan_with_phash_fills_in_a_row_indexed_without_one(tmp_path, qapp):
    """A file first indexed with pHash off was skipped by every later pHash scan."""
    root = tmp_path / "lib"
    root.mkdir()
    path = _noise(root / "a.png")
    _scan(root, with_phash=False)
    assert image_index.get_image(path)["phash"] is None
    _scan(root, with_phash=True)
    row = image_index.get_image(path)
    assert row["phash"] is not None
    assert (row["width"], row["height"]) == (32, 32)


def test_an_unchanged_hashed_file_is_not_read_again(tmp_path, qapp, monkeypatch):
    root = tmp_path / "lib"
    root.mkdir()
    _noise(root / "a.png")
    _scan(root)
    read: list[str] = []
    monkeypatch.setattr(scanner, "compute_phash", lambda p: read.append(str(p)))
    _scan(root)
    assert read == []


def test_a_changed_file_scanned_without_phash_drops_the_stale_hash(tmp_path, qapp):
    """The old content's pHash and size would otherwise keep matching it in similar search."""
    root = tmp_path / "lib"
    root.mkdir()
    path = _noise(root / "a.png")
    _scan(root)
    assert image_index.get_image(path)["phash"] is not None
    Image.new("RGB", (8, 4)).save(path)
    stat = os.stat(path)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
    _scan(root, with_phash=False)
    row = image_index.get_image(path)
    assert (row["phash"], row["width"], row["height"]) == (None, None, None)
    assert row["size"] == os.stat(path).st_size


def test_files_are_read_on_worker_threads_with_the_database_lock_free(tmp_path, qapp,
                                                                      monkeypatch):
    import threading
    import time
    root = tmp_path / "lib"
    root.mkdir()
    for i in range(12):
        _noise(root / f"{i}.png", seed=i)
    real_probe = scanner._probe
    threads: set[int] = set()
    lock_free: list[bool] = []

    def probe(path, stat_result, *, with_phash):
        threads.add(threading.get_ident())
        acquired = image_index._lock.acquire(blocking=False)  # noqa: SLF001
        lock_free.append(acquired)
        if acquired:
            image_index._lock.release()  # noqa: SLF001
        time.sleep(0.02)
        return real_probe(path, stat_result, with_phash=with_phash)

    monkeypatch.setattr(scanner, "_probe", probe)
    monkeypatch.setattr(scanner, "probe_workers", lambda: 3)
    _scan(root)
    assert image_index.count_images() == 12
    assert threading.get_ident() not in threads
    assert len(threads) > 1
    assert all(lock_free)


def test_progress_reaches_the_total_once_per_file_count(tmp_path, qapp, monkeypatch):
    monkeypatch.setattr(scanner, "_SCAN_COMMIT_CHUNK", 4)
    root = tmp_path / "lib"
    root.mkdir()
    for i in range(9):
        _noise(root / f"{i}.png", seed=i)
    s = scanner.LibraryScanner([str(root)], with_phash=False)
    events: list[int] = []
    s.progress.connect(lambda i, n, p: events.append(i))
    s.run()
    assert events == sorted(set(events))
    assert events[-1] == 9
    assert {4, 8} <= set(events)   # every chunk's end, skipped files included


def test_cancel_during_a_chunk_stops_before_the_next(tmp_path, qapp, monkeypatch):
    monkeypatch.setattr(scanner, "_SCAN_COMMIT_CHUNK", 2)
    root = tmp_path / "lib"
    root.mkdir()
    for i in range(6):
        _noise(root / f"{i}.png", seed=i)
    s = scanner.LibraryScanner([str(root)], with_phash=False)
    real_probe = scanner._probe

    def probe(path, stat_result, *, with_phash):
        s.cancel()
        return real_probe(path, stat_result, with_phash=with_phash)

    monkeypatch.setattr(scanner, "_probe", probe)
    monkeypatch.setattr(scanner, "probe_workers", lambda: 1)
    s.run()
    assert image_index.count_images() == 1


def test_a_failing_probe_ends_the_scan_with_an_error(tmp_path, qapp, monkeypatch):
    root = tmp_path / "lib"
    root.mkdir()
    _noise(root / "a.png")

    def broken(*_args, **_kwargs):
        raise RuntimeError("decoder bug")

    monkeypatch.setattr(scanner, "_probe", broken)
    s = scanner.LibraryScanner([str(root)])
    errors: list[str] = []
    s.error.connect(errors.append)
    s.run()
    assert errors == ["decoder bug"]


def test_set_decoded_fields_replaces_and_clears(tmp_path):
    image_index.upsert_image(str(tmp_path / "a.png"), size=1, mtime=1.0, width=5, height=6,
                             phash=2**63 + 1)
    image_index.set_decoded_fields(str(tmp_path / "a.png"), width=None, height=7, phash=2**63 + 5)
    row = image_index.get_image(str(tmp_path / "a.png"))
    assert (row["width"], row["height"]) == (None, 7)
    from Imervue.library.phash import to_signed64
    assert row["phash"] == to_signed64(2**63 + 5)
