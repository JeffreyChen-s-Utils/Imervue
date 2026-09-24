"""Which files an in-place writer may save back over, and in which format."""
from __future__ import annotations

import pytest

from Imervue.image.in_place_save import in_place_format


@pytest.mark.parametrize(("name", "fmt"), [
    ("a.PNG", "PNG"), ("a.jpg", "JPEG"), ("a.jfif", "JPEG"), ("a.tif", "TIFF"),
    ("a.webp", "WEBP"), ("a.gif", "GIF"), ("a.bmp", "BMP"),
    ("a.cr2", None), ("a.dng", None), ("a.heic", None), ("a.jxl", None), ("a.svg", None),
    ("noext", None),
])
def test_in_place_format(name, fmt):
    assert in_place_format(name) == fmt


def test_replace_atomically_swaps_in_the_new_content(tmp_path):
    from Imervue.image.in_place_save import replace_atomically
    path = tmp_path / "a.bin"
    path.write_bytes(b"old")
    replace_atomically(path, lambda tmp: tmp.write_bytes(b"new"))
    assert path.read_bytes() == b"new"
    assert [p.name for p in tmp_path.iterdir()] == ["a.bin"]


def test_replace_atomically_keeps_the_original_when_the_write_fails(tmp_path):
    from Imervue.image.in_place_save import replace_atomically
    path = tmp_path / "a.bin"
    path.write_bytes(b"old")

    def half_written(tmp):
        tmp.write_bytes(b"ne")
        raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        replace_atomically(path, half_written)
    assert path.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["a.bin"]
