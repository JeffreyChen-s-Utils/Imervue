"""Tests for the heuristic auto-tagging helpers."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.library import auto_tag, image_index


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


def _save_png(path, arr):
    Image.fromarray(arr).save(str(path))
    return str(path)


@pytest.fixture
def white_page(tmp_path):
    """Near-white, low-saturation, low-edge — classic document signature."""
    arr = np.full((128, 96, 3), 245, dtype=np.uint8)
    return _save_png(tmp_path / "doc.png", arr)


@pytest.fixture
def colourful_photo(tmp_path):
    """Strongly saturated gradient — reads as photo-like."""
    arr = np.zeros((96, 128, 3), dtype=np.uint8)
    arr[..., 0] = np.linspace(0, 255, 128, dtype=np.uint8)[None, :]
    arr[..., 2] = np.linspace(255, 0, 128, dtype=np.uint8)[None, :]
    return _save_png(tmp_path / "photo.png", arr)


@pytest.fixture
def grayscale_edges(tmp_path):
    """Dim-brightness, low-sat, sharp vertical lines — screenshot heuristic."""
    arr = np.full((96, 128, 3), 80, dtype=np.uint8)
    arr[:, ::4] = 230  # high-contrast vertical stripes
    return _save_png(tmp_path / "screen.png", arr)


class TestClassifyHeuristic:
    def test_document_white_page(self, white_page):
        tags = auto_tag.classify_heuristic(white_page)
        assert "document" in tags

    def test_photo_for_colourful_image(self, colourful_photo):
        tags = auto_tag.classify_heuristic(colourful_photo)
        assert "photo" in tags

    def test_screenshot_for_grayscale_edges(self, grayscale_edges):
        tags = auto_tag.classify_heuristic(grayscale_edges)
        assert "screenshot" in tags

    def test_always_returns_a_content_tag(self, colourful_photo, white_page):
        # Every readable image gets at least one of document/screenshot/photo/graphic.
        content_tags = {"document", "screenshot", "photo", "graphic"}
        for p in (colourful_photo, white_page):
            tags = auto_tag.classify_heuristic(p)
            assert content_tags.intersection(tags)

    def test_unreadable_file_returns_empty(self, tmp_path):
        bad = tmp_path / "broken.png"
        bad.write_bytes(b"not an image")
        assert auto_tag.classify_heuristic(bad) == []

    def test_missing_file_returns_empty(self, tmp_path):
        ghost = tmp_path / "ghost.png"
        assert auto_tag.classify_heuristic(ghost) == []


class TestTryClipLabels:
    def test_returns_empty_when_onnxruntime_missing(self, monkeypatch):
        import sys
        # Hide onnxruntime even if the dev env has it installed.
        monkeypatch.setitem(sys.modules, "onnxruntime", None)
        assert auto_tag.try_clip_labels("/irrelevant/path.png") == []


class TestAutoTagImage:
    def test_tags_are_written_into_index(self, colourful_photo):
        tags = auto_tag.auto_tag_image(colourful_photo)
        assert tags, "expected at least one heuristic tag"
        stored = image_index.tags_of_image(colourful_photo)
        for t in tags:
            assert t in stored

    def test_unreadable_image_yields_no_tags(self, tmp_path):
        bad = tmp_path / "broken.png"
        bad.write_bytes(b"not an image")
        assert auto_tag.auto_tag_image(str(bad)) == []


class TestAutoTagBatch:
    def test_progress_callback_is_called(self, colourful_photo, white_page):
        paths = [colourful_photo, white_page]
        seen: list[tuple[int, int, str]] = []
        auto_tag.auto_tag_batch(paths, progress_cb=lambda i, n, p: seen.append((i, n, p)))
        assert [idx for idx, _, _ in seen] == [1, 2]
        assert all(total == 2 for _, total, _ in seen)

    def test_results_map_has_one_entry_per_path(self, colourful_photo, white_page):
        results = auto_tag.auto_tag_batch([colourful_photo, white_page])
        assert set(results.keys()) == {colourful_photo, white_page}


def test_heuristic_returns_nothing_for_an_unreadable_file(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    assert auto_tag.classify_heuristic(bad) == []


def test_heuristic_propagates_an_unexpected_error(tmp_path, monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("reader bug")

    monkeypatch.setattr(auto_tag.Image, "open", broken)
    with pytest.raises(RuntimeError, match="reader bug"):
        auto_tag.classify_heuristic(tmp_path / "x.png")



def _jpeg(path, size, orientation=None):
    rng = np.random.default_rng(0)
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)).save(path, exif=exif)
    return str(path)


def test_a_wide_picture_is_tagged_landscape_and_a_tall_one_portrait(tmp_path):
    """The aspect was measured on the 64 x 64 sample, so neither tag was ever given."""
    assert "landscape" in auto_tag.classify_heuristic(_jpeg(tmp_path / "wide.jpg", (80, 40)))
    assert "portrait" in auto_tag.classify_heuristic(_jpeg(tmp_path / "tall.jpg", (40, 80)))
    square = auto_tag.classify_heuristic(_jpeg(tmp_path / "square.jpg", (60, 60)))
    assert not {"landscape", "portrait"} & set(square)


def test_a_portrait_phone_photo_is_tagged_portrait(tmp_path):
    """Stored on its side with an EXIF turn, as phones save an upright shot."""
    tags = auto_tag.classify_heuristic(_jpeg(tmp_path / "phone.jpg", (80, 40), orientation=6))
    assert "portrait" in tags and "landscape" not in tags


def test_a_sixteen_bit_scan_is_tagged_like_its_eight_bit_copy(tmp_path):
    """Clipped almost white, a 16-bit grey ramp read as a blank document page."""
    ramp = np.tile(np.linspace(0, 65535, 64, dtype=np.uint16), (48, 1))
    sixteen, eight = tmp_path / "scan16.png", tmp_path / "scan8.png"
    Image.fromarray(ramp).save(sixteen)
    Image.fromarray((ramp // 257).astype(np.uint8)).save(eight)
    assert auto_tag.classify_heuristic(sixteen) == auto_tag.classify_heuristic(eight)
