"""Unit tests for the safety_review plugin's pure (non-Qt) core.

These exercise the logic extracted out of the 2000-line ``safety_review.py``
shell during the module split: category mapping (``_constants``), geometry +
censoring + the single-image pipeline (``_detection``), and the worker path
helpers (``_workers``). No Qt widgets and no ML model downloads are involved —
detectors are replaced with tiny fakes.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from safety_review import _constants, _detection, _workers


# ---------------------------------------------------------------------------
# _constants — category → label / class mapping
# ---------------------------------------------------------------------------

class _FakeDetector:
    """Minimal stand-in for NudeDetector: returns canned detections."""

    def __init__(self, detections):
        self._detections = detections
        self.calls: list[str] = []

    def detect(self, src):
        self.calls.append(src)
        return self._detections


def test_categories_to_real_labels_default_is_genitalia_and_anus():
    labels = _constants._categories_to_real_labels(None)
    assert labels == frozenset({
        "FEMALE_GENITALIA_EXPOSED",
        "MALE_GENITALIA_EXPOSED",
        "ANUS_EXPOSED",
    })


def test_categories_to_real_labels_nipple_maps_to_breast():
    labels = _constants._categories_to_real_labels({_constants.CAT_NIPPLE})
    assert labels == frozenset({"FEMALE_BREAST_EXPOSED"})


def test_categories_to_real_labels_sexual_act_has_no_real_label():
    assert _constants._categories_to_real_labels({_constants.CAT_SEXUAL_ACT}) == frozenset()


def test_categories_to_real_labels_unknown_category_ignored():
    assert _constants._categories_to_real_labels({"bogus"}) == frozenset()


def test_categories_to_anime_classes_default():
    classes = _constants._categories_to_anime_classes(None)
    assert classes == frozenset({0, 3, 4})  # anus, penis, vagina


def test_categories_to_anime_classes_sexual_act_is_make_love():
    assert _constants._categories_to_anime_classes({_constants.CAT_SEXUAL_ACT}) == frozenset({1})


def test_categories_to_anime_classes_empty_input():
    assert _constants._categories_to_anime_classes(frozenset()) == frozenset()


def test_required_packages_auto_is_union_without_duplicates():
    auto = _constants.REQUIRED_PACKAGES_AUTO
    assert set(_constants.REQUIRED_PACKAGES_REAL) <= set(auto)
    assert set(_constants.REQUIRED_PACKAGES_ANIME) <= set(auto)
    assert len(auto) == len(set(auto))


# ---------------------------------------------------------------------------
# _detection._expand_box — geometry + clamping
# ---------------------------------------------------------------------------

def test_expand_box_fixed_padding():
    assert _detection._expand_box(10, 10, 20, 20, 5, 0, 100, 100) == (5, 5, 25, 25)


def test_expand_box_percentage():
    # box is 10x10, expand 50% → 5 px each side
    assert _detection._expand_box(10, 10, 20, 20, 0, 50, 100, 100) == (5, 5, 25, 25)


def test_expand_box_clamps_to_image_bounds():
    assert _detection._expand_box(0, 0, 10, 10, 50, 0, 30, 30) == (0, 0, 30, 30)


def test_expand_box_no_expansion_when_zero():
    assert _detection._expand_box(3, 4, 7, 9, 0, 0, 100, 100) == (3, 4, 7, 9)


# ---------------------------------------------------------------------------
# _detection._censor_region — styles
# ---------------------------------------------------------------------------

def _solid_image(color=(200, 50, 50)):
    return Image.new("RGB", (40, 40), color)


def test_censor_black_fills_region():
    img = _solid_image()
    _detection._censor_region(img, 5, 5, 20, 20, 4, style=_constants.STYLE_BLACK)
    assert img.getpixel((10, 10)) == (0, 0, 0)
    # Outside the region is untouched.
    assert img.getpixel((30, 30)) == (200, 50, 50)


def test_censor_region_zero_area_is_noop():
    img = _solid_image()
    before = img.tobytes()
    _detection._censor_region(img, 10, 10, 10, 20, 4, style=_constants.STYLE_BLACK)
    assert img.tobytes() == before


def test_censor_mosaic_changes_region_but_not_outside():
    img = Image.new("RGB", (40, 40))
    # paint a gradient so mosaic visibly averages
    for x in range(40):
        for y in range(40):
            img.putpixel((x, y), (x * 6 % 256, y * 6 % 256, 0))
    outside = img.getpixel((39, 39))
    _detection._censor_region(img, 0, 0, 20, 20, 8, style=_constants.STYLE_MOSAIC)
    assert img.getpixel((39, 39)) == outside


def test_censor_blur_runs_on_region():
    img = _solid_image()
    # Should not raise and should keep image size.
    _detection._censor_region(img, 0, 0, 30, 30, 4, style=_constants.STYLE_BLUR)
    assert img.size == (40, 40)


# ---------------------------------------------------------------------------
# _detection._detect_regions_real — filtering by label + confidence
# ---------------------------------------------------------------------------

def test_detect_regions_real_filters_by_label_and_confidence():
    detector = _FakeDetector([
        {"class": "MALE_GENITALIA_EXPOSED", "score": 0.9, "box": [1, 2, 3, 4]},
        {"class": "FEMALE_BREAST_EXPOSED", "score": 0.9, "box": [5, 6, 7, 8]},
        {"class": "MALE_GENITALIA_EXPOSED", "score": 0.1, "box": [9, 9, 9, 9]},
    ])
    labels = frozenset({"MALE_GENITALIA_EXPOSED"})
    boxes = _detection._detect_regions_real(detector, "x.png", 0.25, labels)
    assert boxes == [(1, 2, 3, 4)]


# ---------------------------------------------------------------------------
# _detection._process_single_image — end-to-end on synthetic input
# ---------------------------------------------------------------------------

def _write_png(path: Path, color=(123, 200, 80)):
    Image.new("RGB", (50, 50), color).save(path, format="PNG")
    return path


def test_process_single_image_no_boxes_copies_source(tmp_path):
    src = _write_png(tmp_path / "in.png")
    dst = tmp_path / "out.png"
    detector = _FakeDetector([])
    count = _detection._process_single_image(
        detector, str(src), str(dst), 4, 0, mode=_constants.MODE_REAL)
    assert count == 0
    assert dst.exists()
    assert Image.open(dst).getpixel((25, 25)) == (123, 200, 80)


def test_process_single_image_no_boxes_same_path_is_noop(tmp_path):
    src = _write_png(tmp_path / "in.png")
    detector = _FakeDetector([])
    count = _detection._process_single_image(
        detector, str(src), str(src), 4, 0, mode=_constants.MODE_REAL)
    assert count == 0
    assert src.exists()


def test_process_single_image_censors_detected_box(tmp_path):
    src = _write_png(tmp_path / "in.png", color=(255, 0, 0))
    dst = tmp_path / "out.png"
    detector = _FakeDetector([
        {"class": "MALE_GENITALIA_EXPOSED", "score": 0.9, "box": [10, 10, 30, 30]},
    ])
    count = _detection._process_single_image(
        detector, str(src), str(dst), 4, 0,
        mode=_constants.MODE_REAL, style=_constants.STYLE_BLACK)
    assert count == 1
    out = Image.open(dst)
    assert out.getpixel((20, 20)) == (0, 0, 0)          # inside censored box
    assert out.getpixel((45, 45)) == (255, 0, 0)        # outside untouched


def test_process_single_image_jpeg_dst_from_rgba_source(tmp_path):
    src = tmp_path / "in.png"
    Image.new("RGBA", (40, 40), (10, 20, 30, 255)).save(src, format="PNG")
    dst = tmp_path / "out.jpg"
    detector = _FakeDetector([
        {"class": "MALE_GENITALIA_EXPOSED", "score": 0.9, "box": [5, 5, 15, 15]},
    ])
    count = _detection._process_single_image(
        detector, str(src), str(dst), 4, 0, mode=_constants.MODE_REAL)
    assert count == 1
    # JPEG cannot hold alpha; saving must have converted to RGB without error.
    assert Image.open(dst).mode == "RGB"


# ---------------------------------------------------------------------------
# _detection._scan_folder
# ---------------------------------------------------------------------------

def test_scan_folder_returns_sorted_images_only(tmp_path):
    _write_png(tmp_path / "b.png")
    _write_png(tmp_path / "a.png")
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")
    result = _detection._scan_folder(str(tmp_path))
    names = [Path(p).name for p in result]
    assert names == ["a.png", "b.png"]


def test_scan_folder_missing_dir_returns_empty(tmp_path):
    assert _detection._scan_folder(str(tmp_path / "nope")) == []


# ---------------------------------------------------------------------------
# _detection._detect_image_mode — heuristic boundary
# ---------------------------------------------------------------------------

def test_detect_image_mode_flat_image_is_anime(tmp_path):
    src = _write_png(tmp_path / "flat.png", color=(40, 40, 40))
    assert _detection._detect_image_mode(str(src)) == _constants.MODE_ANIME


def test_detect_image_mode_noisy_image_is_real(tmp_path):
    src = tmp_path / "noise.png"
    img = Image.new("RGB", (256, 256))
    for x in range(256):
        for y in range(256):
            img.putpixel((x, y), (x, y, (x * y) % 256))
    img.save(src, format="PNG")
    assert _detection._detect_image_mode(str(src)) == _constants.MODE_REAL


# ---------------------------------------------------------------------------
# _workers — pure path helpers
# ---------------------------------------------------------------------------

def test_non_overwrite_destination_no_clash(tmp_path):
    dst = _workers._non_overwrite_destination(str(tmp_path / "pic.png"), str(tmp_path))
    assert Path(dst).name == "pic_censored.png"


def test_non_overwrite_destination_increments_on_clash(tmp_path):
    (tmp_path / "pic_censored.png").write_text("x", encoding="utf-8")
    dst = _workers._non_overwrite_destination(str(tmp_path / "pic.png"), str(tmp_path))
    assert Path(dst).name == "pic_censored_1.png"


def test_non_overwrite_destination_defaults_suffix_when_missing(tmp_path):
    dst = _workers._non_overwrite_destination(str(tmp_path / "pic"), str(tmp_path))
    assert Path(dst).name == "pic_censored.png"


@pytest.mark.parametrize("categories,expected", [
    (None, ""),
    (frozenset(), ""),
    (frozenset({"anus", "genitalia"}), "anus,genitalia"),
])
def test_categories_arg(categories, expected):
    assert _workers._categories_arg(categories) == expected
