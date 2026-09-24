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


def _exif_with_date():
    from PIL import Image
    exif = Image.Exif()
    exif[0x010F] = "Canon"
    exif.get_ifd(0x8769)[0x9003] = "2020:01:02 03:04:05"
    return exif


def test_edited_copy_in_another_format_keeps_the_descriptive_exif(tmp_path):
    from PIL import Image

    from Imervue.image.in_place_save import save_edited_copy
    src = tmp_path / "a.png"
    Image.new("RGB", (8, 6)).save(src, exif=_exif_with_date(), dpi=(300, 300))
    target = tmp_path / "b.jpg"
    save_edited_copy(src, Image.new("RGBA", (16, 12), (9, 9, 9, 255)), target)
    with Image.open(target) as out:
        assert out.mode == "RGB"
        assert out.getexif().get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"
        assert out.info["dpi"] == pytest.approx((300, 300))


def test_edited_copy_of_an_unreadable_source_is_written_plainly(tmp_path):
    from PIL import Image

    from Imervue.image.in_place_save import save_edited_copy
    src = tmp_path / "gone.cr2"
    target = tmp_path / "out.webp"
    save_edited_copy(src, Image.new("RGB", (4, 4)), target)
    with Image.open(target) as out:
        assert out.size == (4, 4)
        assert not len(out.getexif())


def test_edited_copy_to_an_unwritable_extension_is_refused(tmp_path):
    from PIL import Image

    from Imervue.image.in_place_save import save_edited_copy
    with pytest.raises(ValueError, match="unsupported extension"):
        save_edited_copy(tmp_path / "a.png", Image.new("RGB", (4, 4)), tmp_path / "b.heic")
    assert list(tmp_path.iterdir()) == []


def test_colour_edit_over_a_greyscale_jpeg_does_not_reuse_its_lone_table(tmp_path):
    """A greyscale JPEG has one quantisation table; colour pixels need a chroma one too."""
    from PIL import Image

    from Imervue.image.in_place_save import save_over_source
    path = tmp_path / "grey.jpg"
    Image.new("L", (8, 8), 128).save(path, exif=_exif_with_date())
    save_over_source(path, Image.new("RGBA", (8, 8), (200, 10, 10, 255)))
    with Image.open(path) as out:
        assert out.mode == "RGB"
        assert out.getpixel((4, 4))[0] > 150
        assert out.getexif()[0x010F] == "Canon"


def test_save_over_source_refuses_a_file_it_cannot_rewrite(tmp_path):
    from PIL import Image

    from Imervue.image.in_place_save import save_over_source
    raw = tmp_path / "shot.nef"
    raw.write_bytes(b"RAW")
    with pytest.raises(ValueError, match="saved back whole"):
        save_over_source(raw, Image.new("RGB", (4, 4)))
    assert raw.read_bytes() == b"RAW"


@pytest.mark.parametrize("name", ["a.jpg", "a.webp"])
def test_rewrite_exif_edits_only_the_exif(tmp_path, name):
    from PIL import Image

    from Imervue.image.in_place_save import can_rewrite_exif, rewrite_exif
    path = tmp_path / name
    Image.new("RGB", (8, 8), (40, 80, 120)).save(path)
    with Image.open(path) as img:
        pixels = img.convert("RGB").tobytes()
    assert can_rewrite_exif(path) is True

    def tag(exif):
        exif[0x010F] = "Canon"

    rewrite_exif(path, tag)
    with Image.open(path) as img:
        assert img.getexif()[0x010F] == "Canon"
        assert img.convert("RGB").tobytes() == pixels
    assert [p.name for p in tmp_path.iterdir()] == [name]


def test_rewrite_exif_refuses_other_formats(tmp_path):
    from PIL import Image

    from Imervue.image.in_place_save import can_rewrite_exif, rewrite_exif
    path = tmp_path / "a.png"
    Image.new("RGB", (4, 4)).save(path)
    assert can_rewrite_exif(path) is False
    with pytest.raises(ValueError, match="can't rewrite the EXIF"):
        rewrite_exif(path, lambda _exif: None)
