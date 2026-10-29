"""Contract tests for the safety_review manual censor editor.

Pins the behaviour of ``safety_review._manual_dialog`` that the existing
manual / dataset smoke tests leave open: pixmap loading and its Pillow
fallback, the canvas state API, mouse / keyboard editing, painting, the
auto-detect wiring, dataset-folder persistence and the apply paths.
``ManualReviewDialog`` and its canvas are plain ``QDialog`` / ``QWidget``
(no ``QOpenGLWidget``), so no headless-CI skip marker is needed.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import QDialog, QFileDialog

from safety_review import _constants, _manual_dialog
from safety_review._manual_dialog import (
    ManualReviewDialog,
    _DetectWorker,
    _ManualCanvas,
    _load_pixmap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_everywhere(monkeypatch, name, value):
    """Replace *name* in every loaded safety_review module that binds it."""
    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith("safety_review") and hasattr(mod, name):
            monkeypatch.setattr(mod, name, value)


class _Toast:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def info(self, msg):
        self.calls.append(("info", msg))

    def success(self, msg):
        self.calls.append(("success", msg))

    def error(self, msg):
        self.calls.append(("error", msg))


def _image(tmp_path, size=(60, 40), color=(200, 40, 40), name="img.png"):
    src = tmp_path / name
    Image.new("RGB", size, color).save(src)
    return str(src)


def _dialog(tmp_path, **kwargs):
    src = _image(tmp_path, **kwargs)
    dlg = ManualReviewDialog(SimpleNamespace(main_window=None), src)
    dlg._lang = {}
    return dlg, src


def _with_toast(dlg):
    toast = _Toast()
    dlg._gui = SimpleNamespace(main_window=SimpleNamespace(toast=toast))
    return toast


def _canvas(size=(200, 100)):
    pix = QPixmap(*size)
    pix.fill(QColor(10, 200, 10))
    canvas = _ManualCanvas()
    canvas.set_image(pix)
    return canvas


def _mouse(kind, x, y, button=Qt.MouseButton.LeftButton):
    pos = QPointF(x, y)
    return QMouseEvent(kind, pos, pos, button, button,
                       Qt.KeyboardModifier.NoModifier)


def _drag(canvas, start, end, button=Qt.MouseButton.LeftButton):
    canvas.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, *start, button))
    canvas.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, *end, button))
    canvas.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, *end, button))


# ---------------------------------------------------------------------------
# _load_pixmap
# ---------------------------------------------------------------------------

def test_load_pixmap_reads_with_qt(qapp, tmp_path):
    pix = _load_pixmap(_image(tmp_path, size=(30, 20)))
    assert (pix.width(), pix.height()) == (30, 20)


def test_load_pixmap_falls_back_to_pillow(qapp, tmp_path, monkeypatch):
    src = _image(tmp_path, size=(12, 7), color=(1, 2, 3))
    monkeypatch.setattr(QImageReader, "read", lambda self: QImage())
    pix = _load_pixmap(src)
    assert (pix.width(), pix.height()) == (12, 7)
    assert pix.toImage().pixelColor(3, 3) == QColor(1, 2, 3)


def test_load_pixmap_unreadable_returns_null_and_logs(qapp, tmp_path, caplog):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    with caplog.at_level("ERROR", logger="Imervue.plugin.safety_review"):
        pix = _load_pixmap(str(bad))
    assert pix.isNull()
    assert "couldn't load" in caplog.text


# ---------------------------------------------------------------------------
# Canvas state
# ---------------------------------------------------------------------------

def test_canvas_without_image_is_empty(qapp):
    canvas = _ManualCanvas()
    assert canvas.image_size() == (0, 0)
    assert canvas.regions() == []
    assert canvas.labeled_regions() == []
    assert canvas.selected_class() is None
    assert canvas.focusPolicy() == Qt.FocusPolicy.StrongFocus
    canvas.deleteLater()


def test_canvas_scales_large_images_to_fit(qapp):
    canvas = _canvas(size=(2200, 720))
    assert canvas._scale == pytest.approx(0.5)
    assert (canvas.width(), canvas.height()) == (1100, 360)
    assert canvas.image_size() == (2200, 720)
    canvas.deleteLater()


def test_canvas_regions_returns_a_copy(qapp):
    canvas = _canvas()
    canvas.add_regions([(10, 10, 50, 50)])
    canvas.regions().append((0, 0, 1, 1))
    assert canvas.regions() == [(10, 10, 50, 50)]
    canvas.deleteLater()


def test_set_current_class_reclasses_the_selection(qapp):
    canvas = _canvas()
    canvas.add_regions([(10, 10, 50, 50), (60, 10, 90, 50)], [1, 2])
    canvas.set_current_class(4)                 # nothing selected
    assert canvas.labeled_regions() == [((10, 10, 50, 50), 1), ((60, 10, 90, 50), 2)]
    canvas._selected = 1
    assert canvas.selected_class() == 2
    canvas.set_current_class(5)
    assert canvas.selected_class() == 5
    assert canvas.labeled_regions()[0][1] == 1
    canvas.add_regions([(100, 10, 140, 50)])
    assert canvas.labeled_regions()[-1][1] == 5
    canvas.deleteLater()


def test_clear_regions_drops_classes_and_selection(qapp):
    canvas = _canvas()
    canvas.add_regions([(10, 10, 50, 50)], [3])
    canvas._selected = 0
    canvas.clear_regions()
    assert canvas.labeled_regions() == []
    assert canvas.selected_class() is None
    canvas.deleteLater()


def test_remove_region_ignores_out_of_range(qapp):
    canvas = _canvas()
    canvas.add_regions([(10, 10, 50, 50)], [3])
    canvas._remove_region(5)
    canvas._remove_region(-1)
    assert canvas.regions() == [(10, 10, 50, 50)]
    canvas._remove_region(0)
    assert canvas.labeled_regions() == []
    canvas.deleteLater()


# ---------------------------------------------------------------------------
# Canvas mouse / keyboard
# ---------------------------------------------------------------------------

def test_left_drag_on_empty_space_draws_a_selected_box(qapp):
    canvas = _canvas()
    canvas.set_current_class(2)
    _drag(canvas, (20, 20), (80, 70))
    assert canvas.labeled_regions() == [((20, 20, 80, 70), 2)]
    assert canvas._selected == 0
    assert (canvas._drawing, canvas._moving) == (False, False)
    assert canvas._draw_start is None and canvas._move_last is None
    canvas.deleteLater()


def test_drag_backwards_normalises_and_specks_are_dropped(qapp):
    canvas = _canvas()
    _drag(canvas, (80, 70), (20, 20))
    assert canvas.regions() == [(20, 20, 80, 70)]
    _drag(canvas, (150, 10), (151, 11))       # speck → not added
    assert canvas.regions() == [(20, 20, 80, 70)]
    assert canvas._selected == -1
    canvas.deleteLater()


def test_left_drag_on_a_box_moves_it_clamped(qapp):
    canvas = _canvas()
    canvas.add_regions([(20, 20, 60, 60)])
    _drag(canvas, (30, 30), (40, 35))
    assert canvas.regions() == [(30, 25, 70, 65)]
    assert canvas._selected == 0
    _drag(canvas, (40, 30), (400, 30))        # pushed past the right edge
    assert canvas.regions()[0][2] == 200
    canvas.deleteLater()


def test_right_click_removes_the_box_under_the_cursor(qapp):
    canvas = _canvas()
    canvas.add_regions([(20, 20, 60, 60)], [1])
    canvas._selected = 0
    right = Qt.MouseButton.RightButton
    canvas.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, 150, 90, right))
    assert canvas.regions() == [(20, 20, 60, 60)]
    assert canvas._selected == 0
    canvas.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, 30, 30, right))
    assert canvas.labeled_regions() == []
    assert canvas._selected == -1
    assert canvas._drawing is False
    canvas.deleteLater()


def test_mouse_move_without_a_gesture_is_ignored(qapp):
    canvas = _canvas()
    canvas.add_regions([(20, 20, 60, 60)])
    canvas.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, 90, 90))
    assert canvas.regions() == [(20, 20, 60, 60)]
    canvas.deleteLater()


def test_middle_button_does_nothing(qapp):
    canvas = _canvas()
    mid = Qt.MouseButton.MiddleButton
    canvas.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, 30, 30, mid))
    assert (canvas._drawing, canvas._moving, canvas._selected) == (False, False, -1)
    canvas.deleteLater()


@pytest.mark.parametrize("key", [Qt.Key.Key_Delete, Qt.Key.Key_Backspace])
def test_delete_keys_remove_the_selection(qapp, key):
    canvas = _canvas()
    canvas.add_regions([(20, 20, 60, 60), (70, 20, 90, 60)], [1, 2])
    canvas._selected = 0
    canvas.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key,
                                   Qt.KeyboardModifier.NoModifier))
    assert canvas.labeled_regions() == [((70, 20, 90, 60), 2)]
    assert canvas._selected == -1
    canvas.deleteLater()


def test_delete_without_selection_and_other_keys_keep_boxes(qapp):
    canvas = _canvas()
    canvas.add_regions([(20, 20, 60, 60)])
    for key, selected in ((Qt.Key.Key_Delete, -1), (Qt.Key.Key_A, 0)):
        canvas._selected = selected
        canvas.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key,
                                       Qt.KeyboardModifier.NoModifier))
    assert canvas.regions() == [(20, 20, 60, 60)]
    assert canvas._selected == 0
    canvas.deleteLater()


# ---------------------------------------------------------------------------
# Canvas painting
# ---------------------------------------------------------------------------

def test_paint_tints_boxes_by_selection_and_draws_rubber_band(qapp):
    canvas = _canvas()
    canvas.add_regions([(10, 10, 50, 50), (110, 10, 150, 50)])
    canvas._selected = 1
    canvas._drawing = True
    canvas._draw_start = (60, 60)
    canvas._draw_cur = (100, 90)
    img = canvas.grab().toImage()
    background = img.pixelColor(190, 95)
    assert background == QColor(10, 200, 10)
    plain = img.pixelColor(30, 30)               # red tint
    chosen = img.pixelColor(130, 30)             # blue tint
    assert plain.red() > background.red() and plain.blue() <= background.blue()
    assert chosen.blue() > background.blue() and chosen.red() < plain.red()
    band = img.pixelColor(80, 60)                # yellow rubber-band edge
    assert (band.red(), band.green(), band.blue()) == (255, 200, 0)
    canvas.deleteLater()


def test_paint_without_image_does_not_raise(qapp):
    canvas = _ManualCanvas()
    canvas.resize(20, 20)
    assert not canvas.grab().isNull()
    canvas.deleteLater()


# ---------------------------------------------------------------------------
# Detect worker
# ---------------------------------------------------------------------------

def test_detect_worker_coerces_box_values_to_int(qapp, monkeypatch):
    from safety_review import _detection, _workers
    monkeypatch.setattr(_workers, "_resolve_detector", lambda mode: "det")
    seen = []

    def _labeled(det, src, conf, mode):
        seen.append((det, src, conf, mode))
        return [((1.7, 2.2, 3.9, 4.0), 2.0)]

    monkeypatch.setattr(_detection, "_detect_labeled", _labeled)
    worker = _DetectWorker("x.png", _constants.MODE_REAL, 0.3)
    got = []
    worker.done.connect(got.append)
    worker.run()
    assert seen == [("det", "x.png", 0.3, _constants.MODE_REAL)]
    assert got == [[((1, 2, 3, 4), 2)]]


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

def test_dialog_builds_controls(qapp, tmp_path):
    from safety_review._class_config import get_classes
    dlg, _src = _dialog(tmp_path)
    assert [dlg._mode_combo.itemData(i) for i in range(dlg._mode_combo.count())] == [
        _constants.MODE_AUTO, _constants.MODE_REAL, _constants.MODE_ANIME]
    assert [dlg._style_combo.itemData(i) for i in range(dlg._style_combo.count())] == [
        _constants.STYLE_MOSAIC, _constants.STYLE_BLUR, _constants.STYLE_BLACK]
    assert [dlg._shape_combo.itemData(i) for i in range(dlg._shape_combo.count())] == [
        _constants.SHAPE_ELLIPSE, _constants.SHAPE_RECT]
    assert dlg._class_combo.count() == len(get_classes())
    assert dlg._block_spin.value() == _constants.DEFAULT_BLOCK_SIZE
    assert dlg._overwrite_check.isChecked() is False
    assert dlg._apply_btn.isEnabled() is True
    dlg._class_combo.setCurrentIndex(2)
    assert dlg._canvas._current_class == 2
    dlg.deleteLater()


def test_dialog_with_unreadable_image_disables_apply(qapp, tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"nope")
    dlg = ManualReviewDialog(SimpleNamespace(main_window=None), str(bad))
    assert dlg._apply_btn.isEnabled() is False
    assert dlg._canvas.image_size() == (0, 0)
    dlg.deleteLater()


def test_auto_detect_gates_deps_then_starts_worker(qapp, tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(_DetectWorker, "start", lambda self: started.append(self))
    calls = []

    def _deps(parent, on_ready, mode=_constants.MODE_REAL, precise=False):
        calls.append((parent, mode, precise))
        on_ready()

    _patch_everywhere(monkeypatch, "_ensure_deps", _deps)
    dlg, src = _dialog(tmp_path)
    dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData(_constants.MODE_ANIME))
    dlg._auto_detect()
    assert calls == [(None, _constants.MODE_ANIME, False)]
    assert dlg._detect_btn.isEnabled() is False
    assert dlg._detect_btn.text() == "Detecting..."
    worker = dlg._detect_worker
    assert started == [worker]
    assert (worker._src, worker._mode) == (src, _constants.MODE_ANIME)
    assert worker._conf == pytest.approx(
        _constants._MODE_DEFAULTS[_constants.MODE_ANIME]["confidence"])
    assert worker.parent() is dlg
    worker.done.emit([((5, 5, 30, 30), 1)])
    assert dlg._canvas.labeled_regions() == [((5, 5, 30, 30), 1)]
    assert dlg._detect_worker is None
    assert dlg._detect_btn.text() == "Auto-detect & prefill"
    dlg.deleteLater()


def test_on_detected_toasts_the_added_count(qapp, tmp_path):
    dlg, _src = _dialog(tmp_path)
    toast = _with_toast(dlg)
    dlg._on_detected([((5, 5, 30, 30), 1), ((0, 0, 1, 1), 2)])
    assert toast.calls == [("info", "Added 1 detected region(s)")]
    dlg.deleteLater()


def test_detect_failure_logs_resets_and_toasts(qapp, tmp_path, caplog):
    dlg, _src = _dialog(tmp_path)
    dlg._detect_btn.setEnabled(False)
    dlg._on_detect_failed("bad model")         # no toast host: just resets
    assert dlg._detect_btn.isEnabled() is True
    toast = _with_toast(dlg)
    with caplog.at_level("ERROR", logger="Imervue.plugin.safety_review"):
        dlg._on_detect_failed("bad model")
    assert "Manual auto-detect failed: bad model" in caplog.text
    assert toast.calls == [("error", "Detection failed — draw the boxes by hand.")]
    dlg.deleteLater()


def test_reject_and_close_stop_the_detect_worker(qapp, tmp_path, monkeypatch):
    stops = []
    monkeypatch.setattr(ManualReviewDialog, "_stop_detect_worker",
                        lambda self: stops.append(1))
    dlg, _src = _dialog(tmp_path)
    dlg.reject()
    assert dlg.result() == QDialog.DialogCode.Rejected
    dlg.close()
    assert stops == [1, 1]
    dlg.deleteLater()


def test_dataset_dir_prefers_remembered_folder(qapp, tmp_path, monkeypatch):
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    asked = []
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: asked.append(1) or ""))
    user_setting_dict["safety_review_dataset_dir"] = str(tmp_path)
    dlg, _src = _dialog(tmp_path)
    assert dlg._dataset_dir() == str(tmp_path)
    assert asked == []
    dlg.deleteLater()


def test_dataset_dir_prompts_and_remembers(qapp, tmp_path, monkeypatch):
    from Imervue.user_settings import user_setting_dict as settings_mod
    saves = []
    monkeypatch.setattr(settings_mod, "schedule_save", lambda: saves.append(1))
    settings_mod.user_setting_dict["safety_review_dataset_dir"] = str(tmp_path / "gone")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: "D:/ds"))
    dlg, _src = _dialog(tmp_path)
    assert dlg._dataset_dir() == "D:/ds"
    assert settings_mod.user_setting_dict["safety_review_dataset_dir"] == "D:/ds"
    assert saves == [1]
    dlg.deleteLater()


def test_dataset_dir_cancelled_returns_none(qapp, tmp_path, monkeypatch):
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict.pop("safety_review_dataset_dir", None)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: ""))
    dlg, _src = _dialog(tmp_path)
    assert dlg._dataset_dir() is None
    assert "safety_review_dataset_dir" not in user_setting_dict
    dlg.deleteLater()


def test_add_to_dataset_without_folder_exports_nothing(qapp, tmp_path, monkeypatch):
    from safety_review import _dataset
    exported = []
    monkeypatch.setattr(_dataset, "export_label", lambda *a: exported.append(a))
    dlg, _src = _dialog(tmp_path)
    monkeypatch.setattr(dlg, "_dataset_dir", lambda: None)
    dlg._add_to_dataset()
    assert exported == []
    dlg.deleteLater()


def test_add_to_dataset_os_error_is_logged(qapp, tmp_path, monkeypatch, caplog):
    from safety_review import _dataset

    def _fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(_dataset, "export_label", _fail)
    dlg, _src = _dialog(tmp_path)
    toast = _with_toast(dlg)
    monkeypatch.setattr(dlg, "_dataset_dir", lambda: str(tmp_path))
    with caplog.at_level("ERROR", logger="Imervue.plugin.safety_review"):
        dlg._add_to_dataset()
    assert "Dataset export failed" in caplog.text
    assert toast.calls == []
    dlg.deleteLater()


def test_add_to_dataset_passes_labels_and_toasts(qapp, tmp_path, monkeypatch):
    from safety_review import _dataset
    from safety_review._class_config import get_classes
    seen = []
    monkeypatch.setattr(_dataset, "export_label",
                        lambda *a: seen.append(a) or 3)
    dlg, src = _dialog(tmp_path)
    toast = _with_toast(dlg)
    dlg._canvas.add_regions([(10, 10, 40, 30)], [4])
    monkeypatch.setattr(dlg, "_dataset_dir", lambda: "D:/ds")
    dlg._add_to_dataset()
    assert seen == [("D:/ds", src, [((10, 10, 40, 30), 4)], 60, 40, get_classes())]
    assert toast.calls == [("success", "Added to dataset (3 labels)")]
    dlg.deleteLater()


def test_output_path_overwrite_is_the_source(qapp, tmp_path):
    dlg, src = _dialog(tmp_path)
    assert dlg._output_path() == str(tmp_path / "img_censored.png")
    dlg._overwrite_check.setChecked(True)
    assert dlg._output_path() == src
    dlg.deleteLater()


def test_apply_overwrite_reloads_viewer_toasts_and_accepts(qapp, tmp_path, monkeypatch):
    reloads = []
    _patch_everywhere(monkeypatch, "_reload_grid_or_deepzoom", reloads.append)
    calls = []
    _patch_everywhere(monkeypatch, "_process_manual_image",
                      lambda *a, **k: calls.append((a, k)))
    dlg, src = _dialog(tmp_path)
    toast = _with_toast(dlg)
    dlg._overwrite_check.setChecked(True)
    dlg._block_spin.setValue(9)
    dlg._canvas.add_regions([(10, 10, 40, 30), (0, 0, 20, 20)])
    dlg._apply()
    assert calls == [((src, src, [(10, 10, 40, 30), (0, 0, 20, 20)], 9),
                      {"style": _constants.STYLE_MOSAIC,
                       "shape": _constants.SHAPE_ELLIPSE})]
    assert reloads == [dlg._gui]
    assert toast.calls == [("success", "Applied 2 censor region(s)")]
    assert dlg.result() == QDialog.DialogCode.Accepted
    dlg.deleteLater()


def test_apply_failure_is_logged_and_dialog_stays_open(qapp, tmp_path, monkeypatch, caplog):
    def _boom(*args, **kwargs):
        raise ValueError("bad image")

    _patch_everywhere(monkeypatch, "_process_manual_image", _boom)
    dlg, _src = _dialog(tmp_path)
    toast = _with_toast(dlg)
    dlg._canvas.add_regions([(10, 10, 40, 30)])
    with caplog.at_level("ERROR", logger="Imervue.plugin.safety_review"):
        dlg._apply()
    assert "Manual censor apply failed" in caplog.text
    assert toast.calls == []
    assert dlg.result() != QDialog.DialogCode.Accepted
    dlg.deleteLater()


def test_manual_dialog_module_keeps_public_names():
    for name in ("ManualReviewDialog", "_DetectWorker", "_ManualCanvas",
                 "_load_pixmap"):
        assert hasattr(_manual_dialog, name), name
