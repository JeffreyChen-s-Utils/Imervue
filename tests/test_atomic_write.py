"""Tests for replacing a file in one step."""
from __future__ import annotations

import pytest

from Imervue.system.atomic_write import replace_atomically


def test_replace_atomically_swaps_in_the_new_content(tmp_path):
    path = tmp_path / "a.bin"
    path.write_bytes(b"old")
    replace_atomically(path, lambda tmp: tmp.write_bytes(b"new"))
    assert path.read_bytes() == b"new"
    assert [p.name for p in tmp_path.iterdir()] == ["a.bin"]


def test_replace_atomically_keeps_the_original_when_the_write_fails(tmp_path):
    path = tmp_path / "a.bin"
    path.write_bytes(b"old")

    def half_written(tmp):
        tmp.write_bytes(b"ne")
        raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        replace_atomically(path, half_written)
    assert path.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["a.bin"]
