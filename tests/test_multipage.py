"""Tests for multi-page PDF/TIFF combine and split."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.image.multipage import (
    combine_to_multipage,
    multipage_format,
    split_multipage,
    split_page_stem,
)


def _png(path, value):
    Image.fromarray(np.full((16, 16, 3), value, dtype=np.uint8)).save(str(path))
    return str(path)


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def test_multipage_format():
    assert multipage_format(".pdf") == "PDF"
    assert multipage_format(".TIF") == "TIFF"
    assert multipage_format(".tiff") == "TIFF"
    assert multipage_format(".png") is None


def test_split_page_stem_zero_padded():
    assert split_page_stem("/a/doc.tiff", 2) == "doc_page002"
    assert split_page_stem("my.doc.tiff", 0) == "my.doc_page000"


def test_combine_rejects_bad_destination(tmp_path):
    with pytest.raises(ValueError):
        combine_to_multipage([_png(tmp_path / "a.png", 1)], str(tmp_path / "out.png"))


def test_combine_rejects_empty_input(tmp_path):
    with pytest.raises(ValueError):
        combine_to_multipage([], str(tmp_path / "out.tiff"))


# ---------------------------------------------------------------------------
# combine + split round-trip (TIFF is native to Pillow)
# ---------------------------------------------------------------------------


def test_combine_tiff_then_split(tmp_path):
    paths = [_png(tmp_path / f"p{i}.png", v) for i, v in enumerate((30, 120, 210))]
    dst = tmp_path / "doc.tiff"
    result = combine_to_multipage(paths, str(dst))
    assert result["pages"] == 3
    with Image.open(dst) as im:
        assert getattr(im, "n_frames", 1) == 3
    pages = split_multipage(str(dst), str(tmp_path / "pages"))
    assert len(pages) == 3
    assert all(p.exists() for p in pages)


def test_combine_pdf_writes_file(tmp_path):
    paths = [_png(tmp_path / f"p{i}.png", v) for i, v in enumerate((50, 150))]
    dst = tmp_path / "doc.pdf"
    combine_to_multipage(paths, str(dst))
    assert dst.exists()
    assert dst.stat().st_size > 0


def _three_page_tiff(tmp_path):
    paths = [_png(tmp_path / f"p{i}.png", v) for i, v in enumerate((10, 128, 250))]
    dst = tmp_path / "doc.tiff"
    combine_to_multipage(paths, str(dst))
    return dst


def test_split_names_pages_with_the_extension_lowercased(tmp_path):
    pages = split_multipage(str(_three_page_tiff(tmp_path)), str(tmp_path / "out"), "JPG")
    assert [p.name for p in pages] == ["doc_page000.jpg", "doc_page001.jpg", "doc_page002.jpg"]


def test_splitting_again_keeps_the_earlier_pages(tmp_path):
    """A second split into the same folder replaced the first one's pages without a word."""
    src = _three_page_tiff(tmp_path)
    out = tmp_path / "out"
    split_multipage(str(src), str(out))
    retouched = out / "doc_page001.png"
    retouched.write_bytes(b"retouched since")
    again = split_multipage(str(src), str(out))
    assert retouched.read_bytes() == b"retouched since"
    assert [p.name for p in again] == ["doc_page000_1.png", "doc_page001_1.png", "doc_page002_1.png"]
    assert all(p.is_file() for p in again)
