"""Tests for library maintenance (index vs filesystem reconciliation)."""
from __future__ import annotations

import pytest

from Imervue.library import image_index
from Imervue.library.maintenance import (
    diff_index_vs_fs,
    run_maintenance,
    scan_image_files,
)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


def test_diff_index_vs_fs():
    diff = diff_index_vs_fs(["a", "b", "c"], ["b", "c", "d"])
    assert diff["missing"] == ["a"]
    assert diff["new"] == ["d"]


def test_diff_empty():
    assert diff_index_vs_fs([], []) == {"missing": [], "new": []}


def test_scan_image_files_recurses(tmp_path):
    (tmp_path / "a.png").write_bytes(b"\x00")
    (tmp_path / "notes.txt").write_text("x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.jpg").write_bytes(b"\x00")
    found = scan_image_files([str(tmp_path)])
    assert any(p.endswith("a.png") for p in found)
    assert any(p.endswith("b.jpg") for p in found)
    assert not any(p.endswith("notes.txt") for p in found)


def test_run_maintenance_reports_and_prunes(tmp_path):
    gone = str(tmp_path / "gone.png")  # indexed but never written to disk
    image_index.upsert_image(gone, size=1)
    real = tmp_path / "real.png"
    real.write_bytes(b"\x00")

    result = run_maintenance([str(tmp_path)])
    assert gone in result["details"]["missing"]
    assert any(p.endswith("real.png") for p in result["details"]["new"])

    run_maintenance([str(tmp_path)], prune=True)
    assert image_index.get_image(gone) is None
