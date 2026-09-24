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
