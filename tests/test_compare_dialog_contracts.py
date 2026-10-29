"""Contract tests for the compare dialog's views, image math and mode handlers.

Pins what the existing compare tests leave open: what each view paints, how
drags move the pan and the A|B divider, the overlay / difference / split mode
flows and their sliders, the side-by-side grid and its zoom sync, the
selection warnings, and the array helpers' exact output.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPixmap, QWheelEvent

from Imervue.gpu_image_view.actions import compare_dialog as mod
from Imervue.gpu_image_view.actions.compare_dialog import (
    CompareDialog,
    _ImageLabel,
    _SplitLabel,
)


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


@pytest.fixture
def warnings(monkeypatch):
    shown = []
    monkeypatch.setattr(
        mod.QMessageBox, "information", lambda _p, title, text: shown.append((title, text)),
    )
    return shown


def _pixmap(w: int, h: int, colour) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(QColor(colour))
    return pm


def _render(widget, w: int = 200, h: int = 200) -> QImage:
    widget.resize(w, h)
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    widget.render(img)
    return img


def _rgb(img: QImage, x: int, y: int) -> tuple[int, int, int]:
    c = img.pixelColor(x, y)
    return c.red(), c.green(), c.blue()


def _mouse(kind, x: float, y: float, button=Qt.MouseButton.LeftButton) -> QMouseEvent:
    pos = QPointF(x, y)
    return QMouseEvent(kind, pos, pos, button, button, Qt.KeyboardModifier.NoModifier)


def _wheel(delta_y: int) -> QWheelEvent:
    pos = QPointF(10, 10)
    return QWheelEvent(
        pos, pos, QPoint(0, 0), QPoint(0, delta_y),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )


# ---------------------------------------------------------------------------
# _ImageLabel
# ---------------------------------------------------------------------------


def test_image_label_paints_fitted_and_centred(qapp):
    label = _ImageLabel()
    try:
        label._pixmap = _pixmap(40, 20, "red")  # noqa: SLF001
        img = _render(label)
        assert _rgb(img, 100, 100) == (255, 0, 0)
        assert _rgb(img, 100, 20) == (26, 26, 26)
        assert _rgb(img, 100, 180) == (26, 26, 26)
    finally:
        label.deleteLater()


def test_image_label_paints_with_pan_and_zoom(qapp):
    label = _ImageLabel()
    try:
        label._pixmap = _pixmap(40, 20, "red")  # noqa: SLF001
        label.sync_view(1.0, 30.0, 0.0)
        img = _render(label)
        assert _rgb(img, 20, 100) == (26, 26, 26)
        assert _rgb(img, 40, 100) == (255, 0, 0)
        label.sync_view(2.0, 0.0, 0.0)
        img = _render(label)
        assert _rgb(img, 100, 10) == (255, 0, 0)
    finally:
        label.deleteLater()


def test_image_label_without_pixmap_paints_background_only(qapp):
    label = _ImageLabel()
    try:
        img = _render(label)
        assert _rgb(img, 100, 100) == (26, 26, 26)
        label._pixmap = QPixmap()  # noqa: SLF001
        assert _rgb(_render(label), 100, 100) == (26, 26, 26)
    finally:
        label.deleteLater()


def test_image_label_defaults(qapp):
    label = _ImageLabel()
    try:
        assert label._pixmap is None  # noqa: SLF001
        assert label.alignment() == Qt.AlignmentFlag.AlignCenter
        assert (label.minimumWidth(), label.minimumHeight()) == (200, 200)
        assert label.hasMouseTracking()
        assert "#1a1a1a" in label.styleSheet()
    finally:
        label.deleteLater()


def test_image_label_set_qimage_resets_view(qapp):
    label = _ImageLabel()
    try:
        label.sync_view(3.0, 5.0, 6.0)
        qimg = QImage(8, 4, QImage.Format.Format_RGBA8888)
        qimg.fill(QColor("blue"))
        label.set_qimage(qimg)
        assert (label._pixmap.width(), label._pixmap.height()) == (8, 4)  # noqa: SLF001
        assert (label._zoom, label._pan_x, label._pan_y) == pytest.approx((1.0, 0.0, 0.0))  # noqa: SLF001
    finally:
        label.deleteLater()


def test_image_label_drag_pans_and_emits(qapp):
    label = _ImageLabel()
    emitted = []
    label.view_changed.connect(lambda z, x, y: emitted.append((z, x, y)))
    try:
        press = _mouse(QMouseEvent.Type.MouseButtonPress, 10, 10)
        label.mousePressEvent(press)
        assert press.isAccepted()
        label.mouseMoveEvent(_mouse(QMouseEvent.Type.MouseMove, 15, 7, Qt.MouseButton.NoButton))
        label.mouseMoveEvent(_mouse(QMouseEvent.Type.MouseMove, 20, 9, Qt.MouseButton.NoButton))
        assert emitted == [
            pytest.approx((1.0, 5.0, -3.0)), pytest.approx((1.0, 10.0, -1.0)),
        ]
        label.mouseReleaseEvent(_mouse(QMouseEvent.Type.MouseButtonRelease, 20, 9))
        assert label._drag_pos is None  # noqa: SLF001
        label.mouseMoveEvent(_mouse(QMouseEvent.Type.MouseMove, 40, 40, Qt.MouseButton.NoButton))
        assert len(emitted) == 2
    finally:
        label.deleteLater()


def test_image_label_right_button_does_not_start_a_drag(qapp):
    label = _ImageLabel()
    try:
        label.mousePressEvent(
            _mouse(QMouseEvent.Type.MouseButtonPress, 10, 10, Qt.MouseButton.RightButton))
        assert label._drag_pos is None  # noqa: SLF001
        label._drag_pos = QPointF(1, 1)  # noqa: SLF001
        label.mouseReleaseEvent(
            _mouse(QMouseEvent.Type.MouseButtonRelease, 10, 10, Qt.MouseButton.RightButton))
        assert label._drag_pos == QPointF(1, 1)  # noqa: SLF001
    finally:
        label.deleteLater()


def test_image_label_zoom_factor(qapp):
    label = _ImageLabel()
    try:
        label.wheelEvent(_wheel(120))
        assert label._zoom == pytest.approx(1.15)  # noqa: SLF001
        label.wheelEvent(_wheel(-120))
        assert label._zoom == pytest.approx(1.0)  # noqa: SLF001
    finally:
        label.deleteLater()


# ---------------------------------------------------------------------------
# _SplitLabel
# ---------------------------------------------------------------------------


def _split_label() -> _SplitLabel:
    split = _SplitLabel()
    split._pm_a = _pixmap(10, 10, "red")  # noqa: SLF001
    split._pm_b = _pixmap(10, 10, "blue")  # noqa: SLF001
    return split


def test_split_label_paints_a_left_b_right_and_handle(qapp):
    split = _split_label()
    try:
        img = _render(split)
        assert _rgb(img, 40, 160) == (255, 0, 0)
        assert _rgb(img, 160, 160) == (0, 0, 255)
        line = _rgb(img, 100, 10)
        assert min(line) >= 200
        split.set_split(0.25)
        img = _render(split)
        assert _rgb(img, 80, 160) == (0, 0, 255)
        assert _rgb(img, 20, 160) == (255, 0, 0)
    finally:
        split.deleteLater()


def test_split_label_letterboxes_on_dark_background(qapp):
    split = _SplitLabel()
    try:
        split._pm_a = _pixmap(20, 10, "red")  # noqa: SLF001
        split._pm_b = _pixmap(5, 5, "blue")  # noqa: SLF001
        img = _render(split)
        assert _rgb(img, 40, 20) == (26, 26, 26)
        assert _rgb(img, 40, 100) == (255, 0, 0)
        assert _rgb(img, 160, 100) == (0, 0, 255)
        assert _rgb(img, 160, 180) == (26, 26, 26)
    finally:
        split.deleteLater()


@pytest.mark.parametrize("missing", ["a", "b", "null"])
def test_split_label_without_pair_paints_background(qapp, missing):
    split = _split_label()
    try:
        if missing == "a":
            split._pm_a = None  # noqa: SLF001
        elif missing == "b":
            split._pm_b = None  # noqa: SLF001
        else:
            split._pm_b = QPixmap()  # noqa: SLF001
        img = _render(split)
        assert _rgb(img, 40, 160) == (26, 26, 26)
        assert _rgb(img, 100, 10) == (26, 26, 26)
    finally:
        split.deleteLater()


def test_split_label_set_split_clamps_and_emits_only_on_change(qapp):
    split = _SplitLabel()
    emitted = []
    split.split_changed.connect(emitted.append)
    try:
        assert split.split() == pytest.approx(0.5)
        split.set_split(0.5)
        split.set_split(2.0)
        split.set_split(1.0)
        split.set_split(-1)
        assert emitted == [pytest.approx(1.0), pytest.approx(0.0)]
        assert split.split() == pytest.approx(0.0)
    finally:
        split.deleteLater()


def test_split_label_drag_moves_divider(qapp):
    split = _SplitLabel()
    try:
        split.resize(200, 100)
        split.mouseMoveEvent(_mouse(QMouseEvent.Type.MouseMove, 20, 5, Qt.MouseButton.NoButton))
        assert split.split() == pytest.approx(0.5)
        press = _mouse(QMouseEvent.Type.MouseButtonPress, 50, 5)
        split.mousePressEvent(press)
        assert press.isAccepted() and split.split() == pytest.approx(0.25)
        split.mouseMoveEvent(_mouse(QMouseEvent.Type.MouseMove, 150, 5, Qt.MouseButton.NoButton))
        assert split.split() == pytest.approx(0.75)
        split.mouseReleaseEvent(
            _mouse(QMouseEvent.Type.MouseButtonRelease, 150, 5, Qt.MouseButton.RightButton))
        assert split._dragging  # noqa: SLF001
        split.mouseReleaseEvent(_mouse(QMouseEvent.Type.MouseButtonRelease, 150, 5))
        assert not split._dragging  # noqa: SLF001
        split.mouseMoveEvent(_mouse(QMouseEvent.Type.MouseMove, 10, 5, Qt.MouseButton.NoButton))
        assert split.split() == pytest.approx(0.75)
        split.mousePressEvent(
            _mouse(QMouseEvent.Type.MouseButtonPress, 10, 5, Qt.MouseButton.RightButton))
        assert not split._dragging and split.split() == pytest.approx(0.75)  # noqa: SLF001
    finally:
        split.deleteLater()


def test_split_label_defaults(qapp):
    split = _SplitLabel()
    try:
        assert split.cursor().shape() == Qt.CursorShape.SplitHCursor
        assert split.autoFillBackground() and split.hasMouseTracking()
        assert (split.minimumWidth(), split.minimumHeight()) == (200, 200)
    finally:
        split.deleteLater()


# ---------------------------------------------------------------------------
# Image math
# ---------------------------------------------------------------------------


def test_match_sizes_resizes_b_to_a():
    a = np.zeros((4, 6, 4), dtype=np.uint8)
    b = np.full((2, 3, 4), 200, dtype=np.uint8)
    out_a, out_b = mod._match_sizes(a, b)  # noqa: SLF001
    assert out_a is a and out_b.shape == (4, 6, 4) and out_b.dtype == np.uint8
    same_a, same_b = mod._match_sizes(a, a)  # noqa: SLF001
    assert same_a is a and same_b is a


def test_overlay_exact_values_and_alpha_clamp():
    a = np.zeros((2, 2, 4), dtype=np.uint8)
    b = np.full((2, 2, 4), 200, dtype=np.uint8)
    b[..., 3] = 0
    half = mod.compute_overlay(a, b, 0.5)
    assert half[0, 0].tolist() == [100, 100, 100, 255]
    assert mod.compute_overlay(a, b, 5.0)[0, 0].tolist() == [200, 200, 200, 255]
    assert mod.compute_overlay(a, b, -1.0)[0, 0].tolist() == [0, 0, 0, 255]


def test_difference_exact_values_gain_and_mismatched_sizes():
    a = np.zeros((2, 2, 4), dtype=np.uint8)
    a[..., 0] = 100
    b = np.zeros((1, 1, 4), dtype=np.uint8)
    b[..., 0] = 90
    b[..., 3] = 255
    out = mod.compute_difference(a, b, gain=3.0)
    assert out.shape == (2, 2, 4)
    assert out[0, 0].tolist() == [30, 0, 0, 255]
    assert mod.compute_difference(a, b, gain=100.0)[1, 1].tolist() == [255, 0, 0, 255]


def test_ndarray_to_qimage_copies_pixels():
    arr = np.zeros((2, 3, 4), dtype=np.uint8)
    arr[0, 1] = (10, 20, 30, 255)
    qimg = mod._ndarray_to_qimage(arr)  # noqa: SLF001
    arr[0, 1] = 0
    assert (qimg.width(), qimg.height()) == (3, 2)
    assert qimg.format() == QImage.Format.Format_RGBA8888
    c = qimg.pixelColor(1, 0)
    assert (c.red(), c.green(), c.blue(), c.alpha()) == (10, 20, 30, 255)


def test_load_rgba_array_keeps_small_images_and_returns_rgba(tmp_path):
    path = tmp_path / "s.png"
    Image.new("RGB", (6, 3), (1, 2, 3)).save(path)
    arr = mod._load_rgba_array(str(path))  # noqa: SLF001
    assert arr.shape == (3, 6, 4) and arr.dtype == np.uint8
    assert arr[0, 0].tolist() == [1, 2, 3, 255]


# ---------------------------------------------------------------------------
# Dialog mode handlers
# ---------------------------------------------------------------------------


def _images(tmp_path, colours):
    paths = []
    for i, colour in enumerate(colours):
        path = tmp_path / f"img{i}.png"
        Image.new("RGB", (8, 8), colour).save(path)
        paths.append(str(path))
    return paths


def _gui(paths):
    return SimpleNamespace(main_window=None, model=SimpleNamespace(images=list(paths)))


@pytest.fixture
def make_dialog(qapp):
    made = []

    def _make(paths, select=()):
        dlg = CompareDialog(_gui(paths))
        for i in select:
            dlg._list.item(i).setSelected(True)  # noqa: SLF001
        made.append(dlg)
        return dlg

    yield _make
    for dlg in made:
        dlg.deleteLater()


def _label_pixel(label) -> tuple[int, int, int, int]:
    c = label._pixmap.toImage().pixelColor(0, 0)  # noqa: SLF001
    return c.red(), c.green(), c.blue(), c.alpha()


def test_run_overlay_blends_and_slider_refreshes(make_dialog, tmp_path, warnings):
    dlg = make_dialog(_images(tmp_path, [(200, 0, 0), (0, 0, 100)]), select=(0, 1))
    dlg._run_overlay()  # noqa: SLF001
    assert warnings == []
    assert dlg._tabs.currentWidget() is dlg._overlay_widget  # noqa: SLF001
    assert _label_pixel(dlg._overlay_label) == (100, 0, 50, 255)  # noqa: SLF001
    dlg._overlay_slider.setValue(0)  # noqa: SLF001
    assert _label_pixel(dlg._overlay_label) == (200, 0, 0, 255)  # noqa: SLF001
    dlg._overlay_slider.setValue(100)  # noqa: SLF001
    assert _label_pixel(dlg._overlay_label) == (0, 0, 100, 255)  # noqa: SLF001


def test_overlay_slider_before_a_run_does_nothing(make_dialog, tmp_path):
    dlg = make_dialog(_images(tmp_path, ["red", "blue"]))
    dlg._overlay_slider.setValue(10)  # noqa: SLF001
    dlg._refresh_overlay()  # noqa: SLF001
    assert dlg._overlay_label._pixmap is None  # noqa: SLF001


def test_run_difference_and_gain_slider(make_dialog, tmp_path, warnings):
    dlg = make_dialog(_images(tmp_path, [(100, 0, 0), (90, 0, 0)]), select=(0, 1))
    dlg._diff_slider.setValue(300)  # noqa: SLF001
    assert dlg._diff_gain_label.text() == "3.0×"  # noqa: SLF001
    assert dlg._diff_label._pixmap is None  # noqa: SLF001
    dlg._run_difference()  # noqa: SLF001
    assert dlg._tabs.currentWidget() is dlg._diff_widget  # noqa: SLF001
    assert _label_pixel(dlg._diff_label) == (30, 0, 0, 255)  # noqa: SLF001
    dlg._diff_slider.setValue(2000)  # noqa: SLF001
    assert dlg._diff_gain_label.text() == "20.0×"  # noqa: SLF001
    assert _label_pixel(dlg._diff_label) == (200, 0, 0, 255)  # noqa: SLF001
    dlg._refresh_difference()  # noqa: SLF001
    assert warnings == []


def test_difference_refresh_without_pair_is_a_no_op(make_dialog, tmp_path):
    dlg = make_dialog(_images(tmp_path, ["red"]))
    dlg._refresh_difference()  # noqa: SLF001
    assert dlg._diff_label._pixmap is None  # noqa: SLF001


@pytest.mark.parametrize("runner", ["_run_overlay", "_run_difference", "_run_split"])
def test_two_image_modes_need_exactly_two(make_dialog, tmp_path, warnings, runner):
    dlg = make_dialog(_images(tmp_path, ["red", "blue", "green"]), select=(0,))
    before = dlg._tabs.currentWidget()  # noqa: SLF001
    getattr(dlg, runner)()
    dlg._list.item(1).setSelected(True)  # noqa: SLF001
    dlg._list.item(2).setSelected(True)  # noqa: SLF001
    getattr(dlg, runner)()
    assert warnings == [("Compare Images", "Select exactly 2 images.")] * 2
    assert dlg._tabs.currentWidget() is before  # noqa: SLF001
    assert dlg._overlay_arrs is None and dlg._diff_arrs is None  # noqa: SLF001


@pytest.mark.parametrize("runner", ["_run_overlay", "_run_difference"])
def test_unreadable_pair_warns_load_failed(make_dialog, tmp_path, warnings, runner):
    good = _images(tmp_path, ["red"])[0]
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"nope")
    dlg = make_dialog([good, str(bad)], select=(0, 1))
    getattr(dlg, runner)()
    assert warnings == [("Compare Images", "Failed to load one of the images.")]
    assert dlg._overlay_arrs is None and dlg._diff_arrs is None  # noqa: SLF001


def test_run_split_loads_pair_and_syncs_slider_silently(make_dialog, tmp_path, monkeypatch):
    dlg = make_dialog(_images(tmp_path, ["red", "blue"]), select=(0, 1))
    dlg._split_label._split = 0.3  # noqa: SLF001
    moved = []
    dlg._split_slider.valueChanged.connect(moved.append)  # noqa: SLF001
    dlg._run_split()  # noqa: SLF001
    assert moved == []
    assert dlg._split_slider.value() == 30  # noqa: SLF001
    assert not dlg._split_slider.signalsBlocked()  # noqa: SLF001
    assert dlg._tabs.currentWidget() is dlg._split_widget  # noqa: SLF001
    assert dlg._split_label._pm_a.width() == 8  # noqa: SLF001
    assert dlg._split_label._pm_b.width() == 8  # noqa: SLF001


def test_split_slider_and_divider_stay_in_step(make_dialog, tmp_path):
    dlg = make_dialog(_images(tmp_path, ["red", "blue"]))
    moved = []
    dlg._split_slider.valueChanged.connect(moved.append)  # noqa: SLF001
    dlg._split_slider.setValue(80)  # noqa: SLF001
    assert dlg._split_label.split() == pytest.approx(0.8)  # noqa: SLF001
    dlg._split_label.set_split(0.456)  # noqa: SLF001
    assert dlg._split_slider.value() == 46  # noqa: SLF001
    assert moved == [80]
    assert not dlg._split_slider.signalsBlocked()  # noqa: SLF001


def _grid_positions(dlg):
    layout = dlg._sbs_layout  # noqa: SLF001
    out = []
    for label in dlg._sbs_labels:  # noqa: SLF001
        row, col, _rs, _cs = layout.getItemPosition(layout.indexOf(label))
        out.append((row, col))
    return out


def test_side_by_side_grids_and_replaces_labels(make_dialog, tmp_path, warnings):
    paths = _images(tmp_path, ["red", "blue", "green", "white", "black"])
    dlg = make_dialog(paths, select=range(5))
    dlg._run_side_by_side(4)  # noqa: SLF001
    first = list(dlg._sbs_labels)  # noqa: SLF001
    assert _grid_positions(dlg) == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert dlg._tabs.currentWidget() is dlg._sbs_widget  # noqa: SLF001
    dlg._run_side_by_side(2)  # noqa: SLF001
    assert _grid_positions(dlg) == [(0, 0), (0, 1)]
    assert all(dlg._sbs_layout.indexOf(old) == -1 for old in first)  # noqa: SLF001
    assert warnings == []


def test_side_by_side_labels_follow_each_others_zoom(make_dialog, tmp_path):
    dlg = make_dialog(_images(tmp_path, ["red", "blue", "green", "white"]), select=range(4))
    dlg._run_side_by_side(4)  # noqa: SLF001
    labels = dlg._sbs_labels  # noqa: SLF001
    labels[2].wheelEvent(_wheel(120))
    assert [lbl._zoom for lbl in labels] == [pytest.approx(1.15)] * 4  # noqa: SLF001


def test_side_by_side_too_few_leaves_previous_labels(make_dialog, tmp_path, warnings):
    dlg = make_dialog(_images(tmp_path, ["red", "blue", "green"]), select=(0, 1))
    dlg._run_side_by_side(2)  # noqa: SLF001
    kept = list(dlg._sbs_labels)  # noqa: SLF001
    dlg._tabs.setCurrentWidget(dlg._overlay_widget)  # noqa: SLF001
    dlg._run_side_by_side(4)  # noqa: SLF001
    assert warnings == [("Compare Images", "Select at least 4 images.")]
    assert dlg._sbs_labels == kept  # noqa: SLF001
    assert dlg._tabs.currentWidget() is dlg._overlay_widget  # noqa: SLF001


def test_open_compare_dialog_runs_the_dialog(monkeypatch):
    ran = []

    class _Fake:
        def __init__(self, gui):
            ran.append(gui)

        def exec(self):
            ran.append("exec")

    monkeypatch.setattr(mod, "CompareDialog", _Fake)
    gui = object()
    mod.open_compare_dialog(gui)
    assert ran == [gui, "exec"]
