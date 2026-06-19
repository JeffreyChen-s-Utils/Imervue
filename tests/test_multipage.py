"""Tests for multi-page PDF/TIFF combine and split."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.image.multipage import (
    combine_to_multipage,
    multipage_format,
    split_multipage,
    split_page_name,
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


def test_split_page_name_zero_padded():
    assert split_page_name("/a/doc.tiff", 2, ".png") == "doc_page002.png"
    assert split_page_name("doc.tiff", 0, "jpg") == "doc_page000.jpg"


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
