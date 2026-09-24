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

