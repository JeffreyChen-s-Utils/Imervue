"""Tests for the manual censor editor.

The interaction geometry (``_manual``) and the censor-apply (``_detection.
_process_manual_image``) are pure and tested directly. ``ManualReviewDialog``
is a plain ``QDialog`` with a ``QWidget`` canvas — not a ``QOpenGLWidget`` —
so no headless-CI skip marker is needed; a smoke test drives it under qapp.
"""
from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from safety_review import _constants, _detection, _manual


# ---------------------------------------------------------------------------
# _manual — pure interaction geometry
# ---------------------------------------------------------------------------

def test_normalize_rect_orders_corners():
    assert _manual.normalize_rect(30, 40, 10, 20) == (10, 20, 30, 40)


def test_is_valid_region_rejects_specks():
    assert _manual.is_valid_region((0, 0, 20, 20)) is True
    assert _manual.is_valid_region((0, 0, 3, 30)) is False   # too thin


def test_region_at_returns_topmost():
    regions = [(0, 0, 40, 40), (10, 10, 20, 20)]
    # The later (on-top) region wins where they overlap.
    assert _manual.region_at(regions, 15, 15) == 1
    # Only the first covers this point.
    assert _manual.region_at(regions, 35, 35) == 0
    assert _manual.region_at(regions, 100, 100) == -1


def test_move_and_clamp_region():
    moved = _manual.move_region((10, 10, 20, 20), 5, -5)
    assert moved == (15, 5, 25, 15)
    assert _manual.clamp_region((-5, -5, 200, 200), 100, 80) == (0, 0, 100, 80)


def test_fit_scale_never_upscales():
    assert _manual.fit_scale(200, 100, 400, 400) == 1.0     # small image, no upscale
    assert _manual.fit_scale(1000, 500, 500, 500) == 0.5    # wide image, halve


def test_coordinate_round_trip():
    assert _manual.to_image_point(50, 30, 0.5) == (100, 60)
    assert _manual.to_display_rect((0, 0, 100, 60), 0.5) == (0, 0, 50, 30)


# ---------------------------------------------------------------------------
# _detection._process_manual_image — censor the drawn boxes, no detection
# ---------------------------------------------------------------------------

def test_process_manual_image_censors_the_given_regions(tmp_path):
    src = tmp_path / "in.png"
    Image.new("RGB", (50, 50), (255, 0, 0)).save(src)
    dst = tmp_path / "out.png"
    count = _detection._process_manual_image(
        str(src), str(dst), [(10, 10, 30, 30)], 4,
        style=_constants.STYLE_BLACK, shape=_constants.SHAPE_RECT)
    assert count == 1
    out = Image.open(dst)
    assert out.getpixel((20, 20)) == (0, 0, 0)       # inside the drawn box
    assert out.getpixel((45, 45)) == (255, 0, 0)     # outside untouched


def test_process_manual_image_no_regions_is_a_verbatim_copy(tmp_path):
    src = tmp_path / "in.png"
    Image.new("RGB", (20, 20), (10, 20, 30)).save(src)
    dst = tmp_path / "out.png"
    assert _detection._process_manual_image(str(src), str(dst), [], 4) == 0
    assert Image.open(dst).getpixel((10, 10)) == (10, 20, 30)


# ---------------------------------------------------------------------------
# ManualReviewDialog / canvas — Qt smoke
# ---------------------------------------------------------------------------

def _dialog(qapp, tmp_path, color=(200, 40, 40)):
    from safety_review._manual_dialog import ManualReviewDialog
    src = tmp_path / "img.png"
    Image.new("RGB", (60, 40), color).save(src)
    gui = SimpleNamespace(main_window=None)
    dlg = ManualReviewDialog(gui, str(src))
    return dlg, str(src)


def test_canvas_loads_image_and_scales(qapp, tmp_path):
    dlg, _src = _dialog(qapp, tmp_path)
    assert dlg._canvas.image_size() == (60, 40)
    assert dlg._canvas.regions() == []
    dlg.deleteLater()


def test_clear_regions_empties_the_canvas(qapp, tmp_path):
    dlg, _src = _dialog(qapp, tmp_path)
    dlg._canvas._regions = [(1, 1, 10, 10)]
    dlg._canvas.clear_regions()
    assert dlg._canvas.regions() == []
    dlg.deleteLater()


def test_apply_censors_drawn_regions_to_a_censored_copy(qapp, tmp_path):
    dlg, src = _dialog(qapp, tmp_path, color=(200, 40, 40))
    # Simulate a hand-drawn box (image coords) without synthesising mouse events.
    dlg._canvas._regions = [(10, 10, 40, 30)]
    dlg._style_combo.setCurrentIndex(
        dlg._style_combo.findData(_constants.STYLE_BLACK))
    dlg._shape_combo.setCurrentIndex(
        dlg._shape_combo.findData(_constants.SHAPE_RECT))
    dlg._apply()
    out = Image.open(
        tmp_path / "img_censored.png")   # overwrite off → sibling copy
    assert out.getpixel((25, 20)) == (0, 0, 0)       # inside the drawn box
    assert out.getpixel((55, 5)) == (200, 40, 40)    # untouched
    dlg.deleteLater()


def test_apply_with_no_regions_writes_nothing(qapp, tmp_path):
    dlg, _src = _dialog(qapp, tmp_path)
    dlg._apply()
    assert not (tmp_path / "img_censored.png").exists()
    dlg.deleteLater()


# ---------------------------------------------------------------------------
# Auto-detect prefill
# ---------------------------------------------------------------------------

def test_add_regions_clamps_and_filters_specks(qapp, tmp_path):
    dlg, _src = _dialog(qapp, tmp_path)   # 60x40 image
    added = dlg._canvas.add_regions([
        (10, 5, 40, 30),      # valid
        (-5, -5, 100, 100),   # clamped to (0,0,60,40)
        (0, 0, 2, 30),        # speck → dropped
    ])
    assert added == 2
    regions = dlg._canvas.regions()
    assert (10, 5, 40, 30) in regions
    assert (0, 0, 60, 40) in regions
    dlg.deleteLater()


def test_on_detected_prefills_labeled_boxes_and_resets_button(qapp, tmp_path):
    dlg, _src = _dialog(qapp, tmp_path)
    dlg._detect_btn.setEnabled(False)
    dlg._on_detected([((10, 5, 40, 30), 3)])
    assert dlg._canvas.regions() == [(10, 5, 40, 30)]
    assert dlg._canvas.labeled_regions() == [((10, 5, 40, 30), 3)]  # class carried
    assert dlg._detect_btn.isEnabled() is True     # button reset for reuse
    dlg.deleteLater()


def test_detect_worker_emits_labeled_boxes(qapp, tmp_path, monkeypatch):
    # Drive the worker body directly with a stubbed detector + detection.
    from safety_review import _detection, _workers
    from safety_review._manual_dialog import _DetectWorker

    src = tmp_path / "x.png"
    Image.new("RGB", (30, 30), (0, 0, 0)).save(src)
    monkeypatch.setattr(_workers, "_resolve_detector", lambda mode: object())
    monkeypatch.setattr(
        _detection, "_detect_labeled",
        lambda det, s, conf, mode: [((1, 2, 3, 4), 0), ((5, 6, 7, 8), 3)])
    worker = _DetectWorker(str(src), _constants.MODE_AUTO, 0.25)
    got = []
    worker.done.connect(got.append)
    worker.run()   # the thread body, called synchronously
    assert got == [[((1, 2, 3, 4), 0), ((5, 6, 7, 8), 3)]]


def test_detect_worker_reports_failure(qapp, tmp_path, monkeypatch):
    from safety_review import _workers
    from safety_review._manual_dialog import _DetectWorker

    def _boom(mode):
        raise RuntimeError("no model")

    monkeypatch.setattr(_workers, "_resolve_detector", _boom)
    worker = _DetectWorker("x.png", _constants.MODE_ANIME, 0.15)
    errors = []
    worker.failed.connect(errors.append)
    worker.run()
    assert errors == ["no model"]
