"""The merged EXIF view: IFD0 + Exif sub-IFD, GPS nested, same as Pillow's JPEG view."""
from __future__ import annotations

from PIL import Image

from Imervue.image.exif_merge import merged_exif


def _save(path, *, with_gps: bool):
    exif = Image.Exif()
    exif[271] = "Canon"
    exif.get_ifd(0x8769)[36867] = "2019:05:06 07:08:09"
    if with_gps:
        exif.get_ifd(0x8825)[1] = "N"
    Image.new("RGB", (4, 4)).save(path, exif=exif)
    return path


def test_sub_ifd_tags_are_merged_and_gps_is_nested(tmp_path):
    with Image.open(_save(tmp_path / "a.jpg", with_gps=True)) as img:
        merged = merged_exif(img)
        assert merged == img._getexif()
    assert merged[271] == "Canon"
    assert merged[36867] == "2019:05:06 07:08:09"
    assert merged[0x8825] == {1: "N"}


def test_without_gps_there_is_no_gps_entry(tmp_path):
    with Image.open(_save(tmp_path / "a.jpg", with_gps=False)) as img:
        assert 0x8825 not in merged_exif(img)


def test_image_without_exif_is_empty():
    assert merged_exif(Image.new("RGB", (2, 2))) == {}
