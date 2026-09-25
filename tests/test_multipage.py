"""Tests for multi-page PDF/TIFF combine and split."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.image.multipage import (
    combine_to_multipage,
    multipage_format,
    page_count,
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


# ---------------------------------------------------------------------------
# combine: pages as the viewer shows them, written in one step
# ---------------------------------------------------------------------------


def test_combine_turns_a_phone_photo_upright(tmp_path):
    """Image.open kept the stored orientation: a portrait photo lay on its side in the PDF/TIFF."""
    exif = Image.Exif()
    exif[0x0112] = 6
    src = tmp_path / "portrait.jpg"
    Image.new("RGB", (40, 20), "white").save(src, exif=exif)
    dst = tmp_path / "doc.tiff"
    combine_to_multipage([str(src)], str(dst))
    with Image.open(dst) as page:
        assert page.size == (20, 40)


def test_combine_converts_a_wide_gamut_page_to_srgb(tmp_path):
    """A PDF page carries no colour profile, so a Display P3 photo came out washed out."""
    from _icc_profiles import DISPLAY_P3
    src = tmp_path / "p3.png"
    Image.new("RGB", (8, 8), (0, 255, 0)).save(src, icc_profile=DISPLAY_P3)
    dst = tmp_path / "doc.tiff"
    combine_to_multipage([str(src)], str(dst))
    with Image.open(dst) as page:
        assert "icc_profile" not in page.info
        assert page.convert("RGB").getpixel((0, 0))[:2] == (0, 255)


def test_a_failed_combine_keeps_the_file_it_would_replace(tmp_path, monkeypatch):
    """Saving straight to the target truncated it first: a failure lost the old document."""
    page = _png(tmp_path / "a.png", 1)
    dst = tmp_path / "doc.tiff"
    dst.write_bytes(b"the document from last week")

    def fail_midway(self, fp, *args, **kwargs):
        with open(fp, "wb") as handle:
            handle.write(b"half a page")
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Image.Image, "save", fail_midway)
    with pytest.raises(OSError):
        combine_to_multipage([page], str(dst))
    assert dst.read_bytes() == b"the document from last week"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.png", "doc.tiff"]


def test_combine_can_replace_one_of_its_own_pages(tmp_path):
    first = _png(tmp_path / "a.png", 10)
    dst = tmp_path / "a.tiff"
    Image.new("RGB", (16, 16), (200, 0, 0)).save(dst)
    result = combine_to_multipage([str(dst), first], str(dst))
    assert result["pages"] == 2
    with Image.open(dst) as doc:
        assert doc.n_frames == 2
        assert doc.convert("RGB").getpixel((0, 0)) == (200, 0, 0)


def _layered_psd(tmp_path):
    import numpy as np

    from Imervue.paint.document import PaintDocument
    from Imervue.paint.psd_io import save_psd
    doc = PaintDocument()
    base = np.zeros((8, 10, 4), dtype=np.uint8)
    base[...] = (200, 100, 50, 255)
    doc.load_image(base)
    doc.add_layer(name="Above").image[2:6, 2:6] = (10, 200, 30, 255)
    path = tmp_path / "layered.psd"
    save_psd(doc, path)
    return path


def test_a_psds_layers_are_not_pages(tmp_path):
    """Pillow counts a PSD's layers as frames from 1; splitting raised EOFError on frame 0."""
    path = _layered_psd(tmp_path)
    with Image.open(path) as img:
        assert getattr(img, "n_frames", 1) == 2
        assert page_count(img) == 1
    pages = split_multipage(str(path), str(tmp_path / "pages"))
    assert [p.name for p in pages] == ["layered_page000.png"]
    with Image.open(pages[0]) as page:
        assert page.getpixel((3, 3))[:3] == (10, 200, 30)   # the merged picture


def test_page_count_of_a_multi_page_tiff_is_its_frames(tmp_path):
    frames = [Image.new("RGB", (4, 4), colour) for colour in ("red", "green", "blue")]
    path = tmp_path / "doc.tif"
    frames[0].save(path, save_all=True, append_images=frames[1:])
    with Image.open(path) as img:
        assert page_count(img) == 3
