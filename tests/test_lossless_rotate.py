"""Tests for lossless rotation via PIL."""
import numpy as np
import pytest
from PIL import Image


class TestLosslessRotate:
    """Test PIL-based lossless rotation (the core logic used by lossless_rotate.py)."""

    def test_rotate_90_dimensions(self, tmp_path):
        path = tmp_path / "test.png"
        img = Image.fromarray(np.zeros((100, 200, 3), dtype=np.uint8))
        img.save(str(path))

        loaded = Image.open(str(path))
        rotated = loaded.transpose(Image.Transpose.ROTATE_90)
        rotated.save(str(path))

        result = Image.open(str(path))
        assert result.size == (100, 200)  # width, height swapped

    def test_rotate_180_dimensions(self, tmp_path):
        path = tmp_path / "test.png"
        img = Image.fromarray(np.zeros((100, 200, 3), dtype=np.uint8))
        img.save(str(path))

        loaded = Image.open(str(path))
        rotated = loaded.transpose(Image.Transpose.ROTATE_180)
        rotated.save(str(path))

        result = Image.open(str(path))
        assert result.size == (200, 100)  # same dimensions

    def test_rotate_270_dimensions(self, tmp_path):
        path = tmp_path / "test.png"
        img = Image.fromarray(np.zeros((100, 200, 3), dtype=np.uint8))
        img.save(str(path))

        loaded = Image.open(str(path))
        rotated = loaded.transpose(Image.Transpose.ROTATE_270)
        rotated.save(str(path))

        result = Image.open(str(path))
        assert result.size == (100, 200)  # width, height swapped

    def test_rotate_preserves_content(self, tmp_path):
        """A red pixel at top-left should move after rotation."""
        path = tmp_path / "pixel.png"
        arr = np.zeros((10, 10, 3), dtype=np.uint8)
        arr[0, 0] = [255, 0, 0]
        Image.fromarray(arr).save(str(path))

        loaded = Image.open(str(path))
        rotated = loaded.transpose(Image.Transpose.ROTATE_90)
        result = np.array(rotated)
        # After 90° CCW, top-left → bottom-left
        assert result[9, 0, 0] == 255
        assert result[0, 0, 0] == 0


def test_pil_rotate_turns_a_tagged_image_from_what_is_shown(tmp_path):
    """Rotating the stored pixels while the re-save dropped the tag cancelled out."""
    from Imervue.gpu_image_view.actions.lossless_rotate import _rotate_via_pil
    from Imervue.image.shown import as_shown
    exif = Image.Exif()
    exif[0x0112] = 6
    path = tmp_path / "tagged.png"
    Image.fromarray(np.zeros((20, 40, 3), dtype=np.uint8)).save(path, exif=exif)
    with Image.open(path) as before:
        shown = as_shown(before).size            # (20, 40): portrait on screen
    assert _rotate_via_pil(str(path), clockwise=True) is True
    with Image.open(path) as after:
        assert as_shown(after).size == (shown[1], shown[0])   # a real quarter turn


def _fake_raw(tmp_path):
    """Bytes Pillow reads as a TIFF, as it reads a CR2 / NEF / DNG (their embedded preview)."""
    path = tmp_path / "shot.cr2"
    Image.new("RGB", (30, 20)).save(path, format="TIFF")
    return path


def test_raw_is_refused_and_left_untouched(tmp_path):
    """The Pillow fallback replaced a 9 MB CR2 with a 0.8 MB preview-sized TIFF."""
    from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
    path = _fake_raw(tmp_path)
    before = path.read_bytes()
    assert lossless_rotate(str(path), clockwise=True) is False
    assert path.read_bytes() == before


def test_animated_gif_is_refused_and_keeps_its_frames(tmp_path):
    from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
    path = tmp_path / "anim.gif"
    frames = [Image.new("RGB", (8, 4), c) for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
    frames[0].save(path, save_all=True, append_images=frames[1:])
    assert lossless_rotate(str(path), clockwise=True) is False
    with Image.open(path) as img:
        assert img.n_frames == 3 and img.size == (8, 4)


@pytest.mark.parametrize(("name", "expected"), [
    ("a.png", True), ("a.jpg", True), ("a.tiff", True), ("a.webp", True),
    ("a.heic", False), ("a.svg", False), ("a.mp4", False),
])
def test_can_rewrite_in_place_by_format(tmp_path, name, expected):
    from Imervue.image.in_place_save import can_rewrite_in_place
    path = tmp_path / name
    fmt = {"a.jpg": "JPEG", "a.tiff": "TIFF", "a.webp": "WEBP"}.get(name, "PNG")
    Image.new("RGB", (4, 4)).save(path, format=fmt)
    assert can_rewrite_in_place(str(path)) is expected


def test_multi_page_tiff_and_missing_files_cannot_be_rewritten(tmp_path):
    from Imervue.image.in_place_save import can_rewrite_in_place
    path = tmp_path / "pages.tif"
    Image.new("RGB", (4, 4)).save(path, save_all=True, append_images=[Image.new("RGB", (4, 4))])
    assert can_rewrite_in_place(str(path)) is False
    assert can_rewrite_in_place(str(tmp_path / "gone.png")) is False



def _described_exif(orientation: int | None = None) -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "Canon"
    if orientation is not None:
        exif[0x0112] = orientation
    exif.get_ifd(0x8769)[0x9003] = "2020:01:02 03:04:05"
    exif[0x8769] = 0
    exif.get_ifd(0x8825)[1] = "N"
    exif[0x8825] = 0
    return exif


def _assert_metadata_kept(img):
    exif = img.getexif()
    assert exif[0x010F] == "Canon"
    assert exif.get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"
    assert exif.get_ifd(0x8825)[1] == "N"


def _marked(width=40, height=20):
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[0, 0] = (255, 0, 0)          # top-left marker; a clockwise turn moves it top-right
    return Image.fromarray(arr)


def test_jpeg_turn_only_changes_the_orientation_tag(tmp_path, monkeypatch):
    """Without piexif the JPEG was re-encoded and lost its EXIF (camera, date, GPS)."""
    import sys

    from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
    monkeypatch.setitem(sys.modules, "piexif", None)       # not a dependency
    path = tmp_path / "shot.jpg"
    _marked().save(path, quality=90, exif=_described_exif(1))
    before = path.read_bytes()
    assert lossless_rotate(str(path), clockwise=True) is True
    after = path.read_bytes()
    assert len(after) == len(before)
    assert sum(a != b for a, b in zip(before, after, strict=True)) == 1
    with Image.open(path) as img:
        assert img.getexif()[0x0112] == 6
        _assert_metadata_kept(img)


def test_jpeg_turns_follow_the_orientation_cycle(tmp_path):
    from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
    path = tmp_path / "shot.jpg"
    _marked().save(path)
    seen = []
    for clockwise in (True, True, True, True, False):
        assert lossless_rotate(str(path), clockwise=clockwise) is True
        with Image.open(path) as img:
            seen.append(img.getexif()[0x0112])
    assert seen == [6, 3, 8, 1, 8]


def test_unparseable_jpeg_falls_back_to_a_re_encode(tmp_path, monkeypatch):
    from Imervue.gpu_image_view.actions import lossless_rotate as rotate_mod
    path = tmp_path / "odd.jpg"
    _marked().save(path)

    def refuse(_data, _code):
        raise ValueError("malformed")

    monkeypatch.setattr(rotate_mod, "set_jpeg_orientation", refuse)
    assert rotate_mod.lossless_rotate(str(path), clockwise=True) is True
    with Image.open(path) as img:
        assert img.size == (20, 40)


@pytest.mark.parametrize("name", ["a.png", "a.tif", "a.webp"])
def test_re_saved_formats_keep_their_metadata_and_pixels(tmp_path, name):
    """A TIFF's own layout tags handed back to the save made a turned 40x20 file 40x40."""
    from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
    path = tmp_path / name
    save_kwargs = {"lossless": True} if name == "a.webp" else {}
    _marked().save(path, exif=_described_exif(), dpi=(300, 300), **save_kwargs)
    assert lossless_rotate(str(path), clockwise=True) is True
    with Image.open(path) as img:
        assert img.size == (20, 40)
        assert np.asarray(img.convert("RGB"))[0, -1].tolist() == [255, 0, 0]
        _assert_metadata_kept(img)
        assert 0x0112 not in img.getexif()
        if name == "a.tif":
            assert img.info["dpi"] == pytest.approx((300, 300))


def test_compressed_tiff_keeps_its_compression(tmp_path):
    from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
    path = tmp_path / "a.tif"
    exif = Image.Exif()
    exif[0x010F] = "Canon"
    _marked().save(path, compression="tiff_lzw", exif=exif)
    assert lossless_rotate(str(path), clockwise=True) is True
    with Image.open(path) as img:
        assert img.size == (20, 40)
        assert img.info["compression"] == "tiff_lzw"
        assert img.getexif()[0x010F] == "Canon"


def test_tiff_with_exif_ifds_is_stored_uncompressed_to_keep_them(tmp_path):
    """Pillow's libtiff writer raises on the Exif / GPS IFDs, so they win over compression."""
    from Imervue.gpu_image_view.actions.lossless_rotate import _metadata_kwargs
    path = tmp_path / "a.tif"
    _marked().save(path, exif=_described_exif())
    with Image.open(path) as source:
        kwargs = _metadata_kwargs(source, "TIFF", str(path))
    assert kwargs["compression"] == "raw"
    assert kwargs["exif"].get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"


def test_lossy_webp_stays_lossy_and_lossless_stays_lossless(tmp_path):
    from Imervue.gpu_image_view.actions.lossless_rotate import _webp_is_lossless, lossless_rotate
    lossy = tmp_path / "lossy.webp"
    lossless = tmp_path / "lossless.webp"
    _marked().save(lossy, quality=80)
    _marked().save(lossless, lossless=True, exif=_described_exif())   # extended (VP8X) layout
    for path in (lossy, lossless):
        assert lossless_rotate(str(path), clockwise=False) is True
    assert _webp_is_lossless(str(lossy)) is False
    assert _webp_is_lossless(str(lossless)) is True


def test_icc_profile_and_png_text_survive_without_the_xmp_orientation(tmp_path):
    from PIL import ImageCms, PngImagePlugin

    from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    text = PngImagePlugin.PngInfo()
    text.add_text("Comment", "keep me")
    text.add_itxt("XML:com.adobe.xmp", '<x tiff:Orientation="6" dc:title="t"/>')
    path = tmp_path / "a.png"
    _marked().save(path, icc_profile=icc, pnginfo=text)
    assert lossless_rotate(str(path), clockwise=True) is True
    with Image.open(path) as img:
        assert img.info["icc_profile"] == icc
        assert img.text["Comment"] == "keep me"
        assert "Orientation" not in img.text["XML:com.adobe.xmp"]
        assert img.size == (40, 20)      # shown 20x40 (the XMP tag), turned: 40x20, now untagged
        assert 0x0112 not in img.getexif()


def test_failed_write_leaves_the_original_whole(tmp_path, monkeypatch):
    from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
    path = tmp_path / "a.png"
    _marked().save(path)
    before = path.read_bytes()

    def disk_full(self, *_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Image.Image, "save", disk_full)
    assert lossless_rotate(str(path), clockwise=True) is False
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["a.png"]


def test_missing_file_is_reported_not_raised(tmp_path):
    from Imervue.gpu_image_view.actions.lossless_rotate import lossless_rotate
    assert lossless_rotate(str(tmp_path / "gone.jpg")) is False
