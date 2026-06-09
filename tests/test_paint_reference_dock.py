"""Tests for the reference-image dock + view."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPoint
from PySide6.QtGui import QPixmap, Qt, QWheelEvent

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.reference_dock import (
    REFERENCE_DEFAULT_SCALE,
    REFERENCE_MAX_SCALE,
    REFERENCE_MIN_SCALE,
    ReferenceDock,
    _ReferenceView,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _png(tmp_path, w: int = 32, h: int = 32):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 3] = 255
    arr[h // 2, w // 2, 0] = 200
    path = tmp_path / "ref.png"
    Image.fromarray(arr, mode="RGBA").save(path)
    return path


# ---------------------------------------------------------------------------
# _ReferenceView — scale + has_image
# ---------------------------------------------------------------------------


def test_view_starts_at_default_scale_with_no_image(qapp):
    view = _ReferenceView()
    try:
        assert view.scale_factor() == REFERENCE_DEFAULT_SCALE
        assert view.has_image() is False
    finally:
        view.deleteLater()


def test_view_set_image_updates_state(qapp):
    view = _ReferenceView()
    try:
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.red)
        view.set_image(pix)
        assert view.has_image() is True
        view.set_image(None)
        assert view.has_image() is False
    finally:
        view.deleteLater()


def test_view_set_scale_clamps_to_min_max(qapp):
    view = _ReferenceView()
    try:
        view.set_scale(0.001)
        assert view.scale_factor() == REFERENCE_MIN_SCALE
        view.set_scale(1000.0)
        assert view.scale_factor() == REFERENCE_MAX_SCALE
    finally:
        view.deleteLater()


def test_view_reset_view_returns_to_default(qapp):
    view = _ReferenceView()
    try:
        view.set_scale(2.5)
        view.reset_view()
        assert view.scale_factor() == REFERENCE_DEFAULT_SCALE
    finally:
        view.deleteLater()


def test_view_set_scale_no_change_does_not_re_emit(qapp):
    """Repeat-set with same value must short-circuit so listeners
    don't churn on a no-op."""
    view = _ReferenceView()
    try:
        emissions: list[float] = []
        view.scale_changed.connect(lambda v: emissions.append(v))
        view.set_scale(2.0)
        before = list(emissions)
        view.set_scale(2.0)   # no-op
        assert emissions == before
    finally:
        view.deleteLater()


def test_view_wheel_with_no_image_is_noop(qapp):
    view = _ReferenceView()
    try:
        evt = QWheelEvent(
            QPoint(10, 10), QPoint(10, 10),
            QPoint(0, 0), QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        before = view.scale_factor()
        view.wheelEvent(evt)
        assert view.scale_factor() == before
    finally:
        view.deleteLater()


# ---------------------------------------------------------------------------
# ReferenceDock — load / clear / has_image
# ---------------------------------------------------------------------------


def test_dock_starts_empty(qapp):
    dock = ReferenceDock()
    try:
        assert dock.has_image() is False
    finally:
        dock.deleteLater()


def test_dock_loads_image_from_path(qapp, tmp_path):
    dock = ReferenceDock()
    try:
        path = _png(tmp_path)
        ok = dock.load_image_from_path(path)
        assert ok is True
        assert dock.has_image() is True
    finally:
        dock.deleteLater()


def test_dock_load_emits_path(qapp, tmp_path):
    dock = ReferenceDock()
    try:
        emitted: list[str] = []
        dock.image_loaded.connect(lambda p: emitted.append(p))
        path = _png(tmp_path)
        dock.load_image_from_path(path)
        assert emitted == [str(path)]
    finally:
        dock.deleteLater()


def test_dock_load_missing_file_returns_false(qapp, tmp_path):
    dock = ReferenceDock()
    try:
        ok = dock.load_image_from_path(tmp_path / "no_such_file.png")
        assert ok is False
        assert dock.has_image() is False
    finally:
        dock.deleteLater()


def test_dock_clear_drops_image_and_emits_empty(qapp, tmp_path):
    dock = ReferenceDock()
    try:
        emissions: list[str] = []
        dock.image_loaded.connect(lambda p: emissions.append(p))
        dock.load_image_from_path(_png(tmp_path))
        dock.clear_image()
        assert dock.has_image() is False
        assert emissions[-1] == ""
    finally:
        dock.deleteLater()


# ---------------------------------------------------------------------------
# Workspace integration
# ---------------------------------------------------------------------------


def test_workspace_attaches_reference_dock(qapp):
    ws = PaintWorkspace()
    try:
        assert isinstance(ws._reference_dock, ReferenceDock)  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_workspace_window_menu_lists_reference_dock(qapp):
    ws = PaintWorkspace()
    try:
        actions = ws._window_dock_actions  # noqa: SLF001
        # The Window menu indexes actions by translation key.
        assert "paint_dock_reference" in actions
    finally:
        ws.deleteLater()
