"""Tests for the synced pan/zoom view state in the compare dialog labels."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QPixmap, QWheelEvent

from Imervue.gpu_image_view.actions.compare_dialog import CompareDialog, _ImageLabel


def _wheel_event(label, delta_y: int) -> QWheelEvent:
    pos = QPointF(label.width() / 2, label.height() / 2)
    return QWheelEvent(
        pos, pos, QPoint(0, 0), QPoint(0, delta_y),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )


def _label_with_pixmap() -> _ImageLabel:
    label = _ImageLabel()
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.gray)
    label._pixmap = pixmap
    return label


def test_reset_view_restores_defaults(qapp):
    label = _label_with_pixmap()
    try:
        label._zoom, label._pan_x, label._pan_y = 3.0, 10.0, -5.0
        label.reset_view()
        assert (label._zoom, label._pan_x, label._pan_y) == pytest.approx((1.0, 0.0, 0.0))
    finally:
        label.deleteLater()


def test_wheel_zoom_emits_view_changed_and_clamps(qapp):
    label = _label_with_pixmap()
    emitted = []
    label.view_changed.connect(lambda z, x, y: emitted.append((z, x, y)))
    try:
        label.wheelEvent(_wheel_event(label, 120))
        assert emitted and emitted[-1][0] > 1.0

        for _ in range(40):
            label.wheelEvent(_wheel_event(label, 120))
        assert label._zoom == pytest.approx(12.0)

        for _ in range(80):
            label.wheelEvent(_wheel_event(label, -120))
        assert label._zoom == pytest.approx(1.0)
    finally:
        label.deleteLater()


def test_wheel_at_min_zoom_does_not_emit(qapp):
    label = _label_with_pixmap()
    emitted = []
    label.view_changed.connect(lambda z, x, y: emitted.append(z))
    try:
        label.wheelEvent(_wheel_event(label, -120))
        assert label._zoom == pytest.approx(1.0)
        assert emitted == []
    finally:
        label.deleteLater()


def test_sync_view_applies_state_without_re_emitting(qapp):
    label = _label_with_pixmap()
    emitted = []
    label.view_changed.connect(lambda z, x, y: emitted.append(z))
    try:
        label.sync_view(2.0, 4.0, -3.0)
        assert (label._zoom, label._pan_x, label._pan_y) == pytest.approx((2.0, 4.0, -3.0))
        assert emitted == []
    finally:
        label.deleteLater()


def test_sync_sbs_labels_propagates_to_other_labels_only(qapp):
    source = _label_with_pixmap()
    other = _label_with_pixmap()

    class _Stub:
        _sbs_labels = [source, other]

    try:
        source._zoom = 5.0
        CompareDialog._sync_sbs_labels(_Stub(), source, 5.0, 7.0, 9.0)
        assert (other._zoom, other._pan_x, other._pan_y) == pytest.approx((5.0, 7.0, 9.0))
        assert source._zoom == pytest.approx(5.0)
    finally:
        source.deleteLater()
        other.deleteLater()
