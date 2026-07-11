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

from safety_review import _constants, _detection, _runner, _workers


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
    # Default now includes make_love (class 1) so the intercourse / junction
    # region is caught out of the box.
    classes = _constants._categories_to_anime_classes(None)
    assert classes == frozenset({0, 1, 3, 4})  # anus, make_love, penis, vagina


def test_default_categories_includes_sexual_act():
    assert _constants.CAT_SEXUAL_ACT in _constants.DEFAULT_CATEGORIES


def test_sexual_act_is_a_noop_for_real_photos():
    # make_love has no NudeNet label, so enabling it by default does not change
    # real-photo detection.
    assert _constants._categories_to_real_labels(None) == frozenset({
        "FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED", "ANUS_EXPOSED",
    })


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
# _detection — merging nearby boxes so a junction is covered
# ---------------------------------------------------------------------------

def test_merge_leaves_distant_boxes_separate():
    boxes = [(0, 0, 10, 10), (100, 100, 110, 110)]
    assert set(_detection._merge_nearby_boxes(boxes, gap=2)) == set(boxes)


def test_merge_unions_overlapping_boxes():
    boxes = [(0, 0, 20, 20), (15, 15, 30, 30)]
    merged = _detection._merge_nearby_boxes(boxes, gap=0)
    assert merged == [(0, 0, 30, 30)]


def test_merge_bridges_a_small_gap():
    # Two boxes 4 px apart — the junction between them — merge when the gap
    # threshold reaches across.
    boxes = [(0, 0, 20, 20), (24, 0, 44, 20)]
    assert _detection._merge_nearby_boxes(boxes, gap=5) == [(0, 0, 44, 20)]
    # Too small a gap keeps them apart.
    assert len(_detection._merge_nearby_boxes(boxes, gap=2)) == 2


def test_merge_is_transitive_chain():
    # A touches B touches C → all three collapse into one union.
    boxes = [(0, 0, 10, 10), (12, 0, 22, 10), (24, 0, 34, 10)]
    assert _detection._merge_nearby_boxes(boxes, gap=3) == [(0, 0, 34, 10)]


def test_merge_gap_scales_with_box_size():
    assert _detection._merge_gap([(0, 0, 100, 40)]) == int(40 * 0.4)
    assert _detection._merge_gap([]) == 0


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
# _detection — censor shape (rect / ellipse / precise) confinement
# ---------------------------------------------------------------------------

def test_region_mask_rect_is_none():
    assert _detection._region_mask(20, 20, _constants.SHAPE_RECT) is None


def test_region_mask_ellipse_clears_corners():
    mask = _detection._region_mask(20, 20, _constants.SHAPE_ELLIPSE)
    assert mask.getpixel((10, 10)) == 255   # centre inside the ellipse
    assert mask.getpixel((0, 0)) == 0       # corner outside


def test_region_mask_precise_uses_supplied_mask():
    seg = _detection._ellipse_mask(20, 20)
    assert _detection._region_mask(20, 20, _constants.SHAPE_PRECISE, seg) is seg


def test_region_mask_precise_without_mask_falls_back_to_ellipse():
    mask = _detection._region_mask(20, 20, _constants.SHAPE_PRECISE, None)
    assert mask.getpixel((10, 10)) == 255
    assert mask.getpixel((0, 0)) == 0


def test_censor_ellipse_keeps_box_corners_but_censors_centre():
    img = Image.new("RGB", (50, 50), (200, 30, 30))
    _detection._censor_region(img, 10, 10, 40, 40, 4,
                              style=_constants.STYLE_BLACK,
                              shape=_constants.SHAPE_ELLIPSE)
    assert img.getpixel((25, 25)) == (0, 0, 0)        # centre censored
    assert img.getpixel((11, 11)) == (200, 30, 30)    # box corner untouched
    assert img.getpixel((45, 45)) == (200, 30, 30)    # outside the box untouched


def test_censor_rect_still_fills_whole_box():
    img = Image.new("RGB", (50, 50), (200, 30, 30))
    _detection._censor_region(img, 10, 10, 40, 40, 4,
                              style=_constants.STYLE_BLACK,
                              shape=_constants.SHAPE_RECT)
    assert img.getpixel((11, 11)) == (0, 0, 0)        # rect covers the corner


def test_censor_precise_confines_to_segmentation_mask():
    from PIL import Image as _Img, ImageDraw
    img = _Img.new("RGB", (50, 50), (200, 30, 30))
    # A tiny white square (0..5 within the box) as the "segmentation" mask.
    seg = _Img.new("L", (30, 30), 0)
    ImageDraw.Draw(seg).rectangle((0, 0, 5, 5), fill=255)
    _detection._censor_region(img, 10, 10, 40, 40, 4,
                              style=_constants.STYLE_BLACK,
                              shape=_constants.SHAPE_PRECISE, seg_mask=seg)
    assert img.getpixel((12, 12)) == (0, 0, 0)        # inside the seg mask
    assert img.getpixel((30, 30)) == (200, 30, 30)    # box interior, but unmasked


def test_crop_seg_mask_handles_none_and_missing():
    assert _detection._crop_seg_mask(None, 0, (0, 0, 4, 4)) is None
    assert _detection._crop_seg_mask([None], 0, (0, 0, 4, 4)) is None
    full = _detection._ellipse_mask(20, 20)
    cropped = _detection._crop_seg_mask([full], 0, (0, 0, 10, 10))
    assert cropped.size == (10, 10)


def test_segment_boxes_degrades_to_none_without_model(monkeypatch):
    # No ultralytics / model → _get_fastsam raises → _segment_boxes returns None
    # so the caller falls back to the ellipse shape instead of crashing.
    def _boom():
        raise ImportError("ultralytics not installed")
    monkeypatch.setattr(_detection, "_get_fastsam", _boom)
    assert _detection._segment_boxes("x.png", [(0, 0, 5, 5)], "real") is None


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


def test_process_single_image_merges_adjacent_detections(tmp_path):
    # Two adjacent genitalia boxes with a gap between them (the junction).
    # With merge on, the gap between them is censored as one region.
    src = _write_png(tmp_path / "in.png", color=(255, 0, 0))
    dst = tmp_path / "out.png"
    detector = _FakeDetector([
        {"class": "MALE_GENITALIA_EXPOSED", "score": 0.9, "box": [5, 20, 20, 30]},
        {"class": "FEMALE_GENITALIA_EXPOSED", "score": 0.9, "box": [24, 20, 40, 30]},
    ])
    count = _detection._process_single_image(
        detector, str(src), str(dst), 4, 0, mode=_constants.MODE_REAL,
        style=_constants.STYLE_BLACK, shape=_constants.SHAPE_RECT,
        merge_regions=True)
    assert count == 1                                   # merged into one region
    out = Image.open(dst)
    assert out.getpixel((22, 25)) == (0, 0, 0)          # the junction is censored


def test_process_single_image_without_merge_keeps_regions_separate(tmp_path):
    src = _write_png(tmp_path / "in.png", color=(255, 0, 0))
    dst = tmp_path / "out.png"
    detector = _FakeDetector([
        {"class": "MALE_GENITALIA_EXPOSED", "score": 0.9, "box": [5, 20, 20, 30]},
        {"class": "FEMALE_GENITALIA_EXPOSED", "score": 0.9, "box": [24, 20, 40, 30]},
    ])
    count = _detection._process_single_image(
        detector, str(src), str(dst), 4, 0, mode=_constants.MODE_REAL,
        style=_constants.STYLE_BLACK, shape=_constants.SHAPE_RECT,
        merge_regions=False)
    assert count == 2                                   # kept as two regions
    out = Image.open(dst)
    assert out.getpixel((22, 25)) == (255, 0, 0)        # junction left uncensored


def test_process_single_image_ellipse_shape_spares_box_corner(tmp_path):
    src = _write_png(tmp_path / "in.png", color=(255, 0, 0))
    dst = tmp_path / "out.png"
    detector = _FakeDetector([
        {"class": "MALE_GENITALIA_EXPOSED", "score": 0.9, "box": [10, 10, 40, 40]},
    ])
    count = _detection._process_single_image(
        detector, str(src), str(dst), 4, 0,
        mode=_constants.MODE_REAL, style=_constants.STYLE_BLACK,
        shape=_constants.SHAPE_ELLIPSE)
    assert count == 1
    out = Image.open(dst)
    assert out.getpixel((25, 25)) == (0, 0, 0)        # centre of the box censored
    assert out.getpixel((11, 11)) == (255, 0, 0)      # box corner left clear


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


def test_process_single_image_only_censored_skips_clean_image(tmp_path):
    # A clean image (no detections) must not be written to dst at all, so a
    # separate-output run collects only the images that were censored.
    src = _write_png(tmp_path / "in.png")
    dst = tmp_path / "out" / "in_censored.png"
    detector = _FakeDetector([])
    count = _detection._process_single_image(
        detector, str(src), str(dst), 4, 0,
        mode=_constants.MODE_REAL, only_censored=True)
    assert count == 0
    assert not dst.exists()
    assert not dst.parent.exists()  # no empty output folder created
    assert src.exists()             # original untouched


def test_process_single_image_only_censored_still_writes_detections(tmp_path):
    src = _write_png(tmp_path / "in.png", color=(255, 0, 0))
    dst = tmp_path / "out" / "sub" / "in_censored.png"
    detector = _FakeDetector([
        {"class": "MALE_GENITALIA_EXPOSED", "score": 0.9, "box": [10, 10, 30, 30]},
    ])
    count = _detection._process_single_image(
        detector, str(src), str(dst), 4, 0,
        mode=_constants.MODE_REAL, style=_constants.STYLE_BLACK,
        only_censored=True)
    assert count == 1
    # The censored image is written and its mirrored folder created on demand.
    assert dst.exists()
    assert Image.open(dst).getpixel((20, 20)) == (0, 0, 0)


def test_process_one_runner_only_censored_skips_clean_image(tmp_path):
    src = _write_png(tmp_path / "in.png")
    dst = tmp_path / "out" / "in_censored.png"
    detector = _FakeDetector([])
    count = _runner._process_one(
        detector, str(src), str(dst), 4, 0,
        det_mode="real", only_censored=True)
    assert count == 0
    assert not dst.exists()
    assert src.exists()


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


def test_scan_folder_non_recursive_skips_subfolders(tmp_path):
    _write_png(tmp_path / "top.png")
    sub = tmp_path / "sub"
    sub.mkdir()
    _write_png(sub / "nested.png")
    result = _detection._scan_folder(str(tmp_path))
    names = [Path(p).name for p in result]
    assert names == ["top.png"]


def test_scan_folder_recursive_includes_subfolders(tmp_path):
    _write_png(tmp_path / "top.png")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    _write_png(sub / "deep.png")
    (tmp_path / "a" / "note.txt").write_text("skip", encoding="utf-8")
    result = _detection._scan_folder(str(tmp_path), recursive=True)
    names = {Path(p).name for p in result}
    assert names == {"top.png", "deep.png"}


def test_scan_folder_recursive_empty_tree(tmp_path):
    (tmp_path / "sub").mkdir()
    assert _detection._scan_folder(str(tmp_path), recursive=True) == []


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


# ---------------------------------------------------------------------------
# _workers — failed-image collection into a mirrored failed folder
# ---------------------------------------------------------------------------

def test_failed_destination_flat_without_scan_root(tmp_path):
    dst = _workers._failed_destination(
        str(tmp_path / "pic.png"), str(tmp_path / "failed"), None)
    assert Path(dst) == tmp_path / "failed" / "pic.png"


def test_failed_destination_mirrors_subfolder(tmp_path):
    root = tmp_path / "src"
    failed = tmp_path / "failed"
    dst = _workers._failed_destination(
        str(root / "a" / "b" / "pic.png"), str(failed), str(root))
    assert Path(dst) == failed / "a" / "b" / "pic.png"


def test_copy_failed_copies_original_into_mirrored_folder(tmp_path):
    root = tmp_path / "src"
    (root / "sub").mkdir(parents=True)
    src = root / "sub" / "bad.png"
    src.write_bytes(b"original-bytes")
    failed = tmp_path / "failed"
    _workers._copy_failed(str(src), str(failed), str(root))
    out = failed / "sub" / "bad.png"
    assert out.exists()
    assert out.read_bytes() == b"original-bytes"
    assert src.exists()  # original left in place


def test_write_failed_manifest_lists_reasons(tmp_path):
    failed = tmp_path / "failed"
    failed.mkdir()
    _workers._write_failed_manifest(
        str(failed), [("a.png", "decode error"), ("b.png", "locked")])
    log = (failed / "censor_failed.log").read_text(encoding="utf-8")
    assert "a.png: decode error" in log
    assert "b.png: locked" in log


def test_batch_record_failure_copies_and_records(tmp_path):
    # Exercise the worker glue via the unbound method (no QThread construction).
    from types import SimpleNamespace
    root = tmp_path / "src"
    root.mkdir()
    src = root / "bad.png"
    src.write_bytes(b"x")
    failed = tmp_path / "failed"
    fake = SimpleNamespace(_failed_dir=str(failed), _scan_root=str(root))
    failures: list[tuple[str, str]] = []
    _workers._BatchWorker._record_failure(fake, str(src), ValueError("boom"),
                                          failures)
    assert failures == [("bad.png", "boom")]
    assert (failed / "bad.png").exists()   # original collected


def test_shape_fallback_returns_first_success():
    calls = []
    result = _workers._process_with_shape_fallback(
        lambda shp: calls.append(shp) or "ok", _constants.SHAPE_PRECISE)
    assert result == "ok"
    assert calls == [_constants.SHAPE_PRECISE]   # succeeded first try, no retry


def test_shape_fallback_retries_same_shape_then_succeeds():
    calls = []

    def _run(shp):
        calls.append(shp)
        if len(calls) == 1:
            raise ValueError("transient")
        return "ok"

    assert _workers._process_with_shape_fallback(
        _run, _constants.SHAPE_PRECISE) == "ok"
    # First precise attempt failed, the retry (still precise) succeeded.
    assert calls == [_constants.SHAPE_PRECISE, _constants.SHAPE_PRECISE]


def test_shape_fallback_downgrades_to_ellipse():
    calls = []

    def _run(shp):
        calls.append(shp)
        if shp != _constants.SHAPE_ELLIPSE:
            raise ValueError("shape failed")
        return "ok"

    assert _workers._process_with_shape_fallback(
        _run, _constants.SHAPE_PRECISE) == "ok"
    # Precise twice (attempt + retry), then the ellipse downgrade succeeds.
    assert calls == [_constants.SHAPE_PRECISE, _constants.SHAPE_PRECISE,
                     _constants.SHAPE_ELLIPSE]


def test_shape_fallback_reraises_when_all_attempts_fail():
    def _run(shp):
        raise ValueError(f"nope-{shp}")

    with pytest.raises(ValueError, match="nope-"):
        _workers._process_with_shape_fallback(_run, _constants.SHAPE_PRECISE)


def test_shape_fallback_ellipse_choice_has_no_extra_downgrade():
    calls = []
    with pytest.raises(ValueError):
        _workers._process_with_shape_fallback(
            lambda shp: calls.append(shp) or (_ for _ in ()).throw(ValueError()),
            _constants.SHAPE_ELLIPSE)
    # Ellipse chosen → attempt + one retry, no third (already the fallback).
    assert calls == [_constants.SHAPE_ELLIPSE, _constants.SHAPE_ELLIPSE]


def test_batch_record_failure_without_failed_dir_only_records(tmp_path):
    from types import SimpleNamespace
    src = tmp_path / "bad.png"
    src.write_bytes(b"x")
    fake = SimpleNamespace(_failed_dir=None, _scan_root=None)
    failures: list[tuple[str, str]] = []
    _workers._BatchWorker._record_failure(fake, str(src), OSError("locked"),
                                          failures)
    assert failures == [("bad.png", "locked")]
    # No failed folder configured → nothing copied anywhere.
    assert list(tmp_path.iterdir()) == [src]


# ---------------------------------------------------------------------------
# _workers — recursive-scan destination mirroring
# ---------------------------------------------------------------------------

def test_relative_parent_direct_child_is_empty(tmp_path):
    src = tmp_path / "pic.png"
    assert _workers._relative_parent(str(src), str(tmp_path)) == ""


def test_relative_parent_nested_returns_subpath(tmp_path):
    src = tmp_path / "a" / "b" / "pic.png"
    rel = _workers._relative_parent(str(src), str(tmp_path))
    assert Path(rel) == Path("a/b")


def test_relative_parent_no_root_is_empty(tmp_path):
    assert _workers._relative_parent(str(tmp_path / "pic.png"), "") == ""


def test_relative_parent_outside_root_falls_back_to_flat(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "other" / "pic.png"
    assert _workers._relative_parent(str(outside), str(root)) == ""


def test_mirrored_destination_maps_subfolder_tree(tmp_path):
    root = tmp_path / "src"
    out = tmp_path / "out"
    out.mkdir()
    src = root / "sub" / "deep" / "pic.png"
    dst = _workers._mirrored_destination(str(src), str(out), str(root))
    assert Path(dst) == out / "sub" / "deep" / "pic_censored.png"
    # The path is only computed here — the directory is created at write time
    # so a skipped clean image leaves no empty output folder behind.
    assert not (out / "sub" / "deep").exists()


def test_mirrored_destination_increments_on_clash(tmp_path):
    root = tmp_path / "src"
    out = tmp_path / "out"
    out.mkdir()
    src = root / "sub" / "pic.png"
    first = _workers._mirrored_destination(str(src), str(out), str(root))
    Path(first).parent.mkdir(parents=True, exist_ok=True)
    Path(first).write_text("x", encoding="utf-8")
    second = _workers._mirrored_destination(str(src), str(out), str(root))
    assert Path(second).name == "pic_censored_1.png"


def test_resolve_destination_overwrite_returns_source(tmp_path):
    src = str(tmp_path / "pic.png")
    assert _workers._resolve_destination(src, None, True, None) == src


def test_resolve_destination_flat_without_root(tmp_path):
    src = str(tmp_path / "pic.png")
    dst = _workers._resolve_destination(src, str(tmp_path), False, None)
    assert Path(dst).name == "pic_censored.png"
    assert Path(dst).parent == tmp_path


def test_resolve_destination_mirrors_with_root(tmp_path):
    root = tmp_path / "src"
    out = tmp_path / "out"
    out.mkdir()
    src = str(root / "sub" / "pic.png")
    dst = _workers._resolve_destination(src, str(out), False, str(root))
    assert Path(dst) == out / "sub" / "pic_censored.png"


# ---------------------------------------------------------------------------
# _runner._batch_destination — subprocess path mirrors the same way
# ---------------------------------------------------------------------------

def test_runner_batch_destination_overwrite_returns_source(tmp_path):
    src = str(tmp_path / "pic.png")
    assert _runner._batch_destination(src, str(tmp_path), True, "") == src


def test_runner_batch_destination_flat_without_root(tmp_path):
    src = str(tmp_path / "pic.png")
    dst = _runner._batch_destination(src, str(tmp_path), False, "")
    assert Path(dst).name == "pic_censored.png"
    assert Path(dst).parent == tmp_path


def test_runner_batch_destination_mirrors_subfolder(tmp_path):
    root = tmp_path / "src"
    out = tmp_path / "out"
    out.mkdir()
    src = str(root / "a" / "b" / "pic.png")
    dst = _runner._batch_destination(src, str(out), False, str(root))
    assert Path(dst) == out / "a" / "b" / "pic_censored.png"
    # Path only — directory materialised on write, not here.
    assert not (out / "a" / "b").exists()


def test_runner_censor_ellipse_spares_corner(tmp_path):
    # The frozen-env runner mirrors the ellipse confinement (precise → ellipse).
    img = Image.new("RGB", (50, 50), (10, 200, 40))
    _runner._censor_region(img, 10, 10, 40, 40, 4,
                           style=_runner.STYLE_BLACK, shape=_runner.SHAPE_ELLIPSE)
    assert img.getpixel((25, 25)) == (0, 0, 0)        # centre censored
    assert img.getpixel((11, 11)) == (10, 200, 40)    # corner spared


def test_runner_censor_precise_degrades_to_ellipse(tmp_path):
    img = Image.new("RGB", (50, 50), (10, 200, 40))
    _runner._censor_region(img, 10, 10, 40, 40, 4,
                           style=_runner.STYLE_BLACK, shape=_runner.SHAPE_PRECISE)
    assert img.getpixel((25, 25)) == (0, 0, 0)
    assert img.getpixel((11, 11)) == (10, 200, 40)   # ellipse fallback spares corner


def test_runner_censor_rect_fills_whole_box(tmp_path):
    img = Image.new("RGB", (50, 50), (10, 200, 40))
    _runner._censor_region(img, 10, 10, 40, 40, 4,
                           style=_runner.STYLE_BLACK, shape=_runner.SHAPE_RECT)
    assert img.getpixel((11, 11)) == (0, 0, 0)


def test_runner_failed_dest_mirrors_subfolder(tmp_path):
    root = tmp_path / "src"
    failed = tmp_path / "failed"
    dst = _runner._failed_dest(str(root / "a" / "pic.png"), str(failed), str(root))
    assert Path(dst) == failed / "a" / "pic.png"


def test_runner_copy_failed_copies_original(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    src = root / "bad.png"
    src.write_bytes(b"orig")
    failed = tmp_path / "failed"
    _runner._copy_failed(str(src), str(failed), str(root))
    assert (failed / "bad.png").read_bytes() == b"orig"


def test_runner_batch_destination_increments_on_clash(tmp_path):
    root = tmp_path / "src"
    out = tmp_path / "out"
    out.mkdir()
    src = str(root / "sub" / "pic.png")
    first = _runner._batch_destination(src, str(out), False, str(root))
    Path(first).parent.mkdir(parents=True, exist_ok=True)
    Path(first).write_text("x", encoding="utf-8")
    second = _runner._batch_destination(src, str(out), False, str(root))
    assert Path(second).name == "pic_censored_1.png"
