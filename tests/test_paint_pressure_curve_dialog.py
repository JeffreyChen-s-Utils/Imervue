"""Tests for the pressure-curve editor widget + dialog."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF

from Imervue.paint.pressure_curve import PressureCurve
from Imervue.paint.pressure_curve_dialog import (
    PressureCurveDialog,
    PressureCurveEditor,
)


def _rect():
    """Standard 200×200 rect at the origin so coord math is easy to verify."""
    return QRectF(0.0, 0.0, 200.0, 200.0)


# ---------------------------------------------------------------------------
# Editor — initial state
# ---------------------------------------------------------------------------


def test_editor_defaults_to_identity_curve(qapp):
    editor = PressureCurveEditor()
    try:
        pts = editor.points()
        assert pts == [(0.0, 0.0), (1.0, 1.0)]
    finally:
        editor.deleteLater()


def test_editor_constructed_from_existing_curve(qapp):
    curve = PressureCurve(points=((0.0, 0.0), (0.5, 0.8), (1.0, 1.0)))
    editor = PressureCurveEditor(curve=curve)
    try:
        assert editor.points() == [(0.0, 0.0), (0.5, 0.8), (1.0, 1.0)]
    finally:
        editor.deleteLater()


def test_editor_to_curve_round_trips(qapp):
    points = ((0.0, 0.0), (0.4, 0.3), (1.0, 1.0))
    editor = PressureCurveEditor(curve=PressureCurve(points=points))
    try:
        rebuilt = editor.to_curve()
        assert rebuilt.points == points
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------


def test_curve_to_screen_inverts_y(qapp):
    """Y axis flips so (0, 1) is the top of the widget, (1, 0) is the
    bottom-right — matches the visual convention of higher pressure
    output drawn upwards."""
    editor = PressureCurveEditor()
    try:
        rect = _rect()
        top_left = editor._curve_to_screen((0.0, 1.0), rect)  # noqa: SLF001
        assert top_left == QPointF(0.0, 0.0)
        bottom_right = editor._curve_to_screen((1.0, 0.0), rect)  # noqa: SLF001
        assert bottom_right == QPointF(200.0, 200.0)
    finally:
        editor.deleteLater()


def test_screen_to_curve_clamps_out_of_range(qapp):
    editor = PressureCurveEditor()
    try:
        rect = _rect()
        # Click far right of the widget — clamp to 1.0 on x.
        out = editor._screen_to_curve(QPointF(500.0, 0.0), rect)  # noqa: SLF001
        assert out == (1.0, 1.0)
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------------------
# set_points — clamping + sorting
# ---------------------------------------------------------------------------


def test_set_points_clamps_out_of_range(qapp):
    """Each axis is clamped to [0, 1] independently — the result is
    sorted by the (now-clamped) x value."""
    editor = PressureCurveEditor()
    try:
        editor.set_points([(-1.0, 5.0), (2.0, -2.0)])
        # x: -1→0, 2→1; y: 5→1, -2→0. Sorted by x.
        assert editor.points() == [(0.0, 1.0), (1.0, 0.0)]
    finally:
        editor.deleteLater()


def test_set_points_sorts_by_x(qapp):
    editor = PressureCurveEditor()
    try:
        editor.set_points([(1.0, 1.0), (0.5, 0.3), (0.0, 0.0)])
        assert editor.points() == [(0.0, 0.0), (0.5, 0.3), (1.0, 1.0)]
    finally:
        editor.deleteLater()


def test_set_points_emits_changed_signal(qapp):
    editor = PressureCurveEditor()
    try:
        emitted = [0]
        editor.points_changed.connect(lambda: emitted.__setitem__(0, emitted[0] + 1))
        editor.set_points([(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)])
        assert emitted[0] == 1
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------------------
# Insert / remove / move helpers
# ---------------------------------------------------------------------------


def test_insert_point_keeps_sorted_order(qapp):
    editor = PressureCurveEditor()
    try:
        editor._insert_point((0.5, 0.7))  # noqa: SLF001
        editor._insert_point((0.25, 0.4))  # noqa: SLF001
        xs = [p[0] for p in editor.points()]
        assert xs == sorted(xs)
        assert (0.25, 0.4) in editor.points()
        assert (0.5, 0.7) in editor.points()
    finally:
        editor.deleteLater()


def test_insert_point_clamps_x_inside_endpoints(qapp):
    """A new point inserted at x=0 would replace the start endpoint;
    the implementation clamps it to a slot strictly inside (0, 1)."""
    editor = PressureCurveEditor()
    try:
        editor._insert_point((0.0, 0.5))  # noqa: SLF001
        # First point is still (0.0, 0.0); the new point sits at the
        # minimum spacing past it.
        assert editor.points()[0] == (0.0, 0.0)
        assert editor.points()[-1] == (1.0, 1.0)
    finally:
        editor.deleteLater()


def test_move_point_pins_first_at_x_zero(qapp):
    editor = PressureCurveEditor()
    try:
        editor._move_point(0, 0.7, 0.3)  # noqa: SLF001
        # The first endpoint stays at x=0 even when the user drags it.
        assert editor.points()[0][0] == 0.0
        assert editor.points()[0][1] == 0.3
    finally:
        editor.deleteLater()


def test_move_point_pins_last_at_x_one(qapp):
    editor = PressureCurveEditor()
    try:
        editor._move_point(1, 0.5, 0.8)  # noqa: SLF001
        assert editor.points()[-1] == (1.0, 0.8)
    finally:
        editor.deleteLater()


def test_move_middle_point_keeps_inside_neighbours(qapp):
    editor = PressureCurveEditor()
    editor.set_points([(0.0, 0.0), (0.4, 0.3), (1.0, 1.0)])
    try:
        # Drag the middle point past the right endpoint — must clamp.
        editor._move_point(1, 2.0, 0.5)  # noqa: SLF001
        x, _ = editor.points()[1]
        assert x < 1.0
        # Drag it left of the left endpoint — must clamp.
        editor._move_point(1, -1.0, 0.5)  # noqa: SLF001
        x, _ = editor.points()[1]
        assert x > 0.0
    finally:
        editor.deleteLater()


def test_to_curve_after_edits_round_trips_through_apply(qapp):
    """The PressureCurve produced by the editor must work as a
    pressure→output mapping. The endpoints are pinned at identity, so
    apply(0)=0 and apply(1)=1 are guaranteed; the middle point's y is
    a sample at its own x."""
    editor = PressureCurveEditor()
    editor.set_points([(0.0, 0.0), (0.5, 0.8), (1.0, 1.0)])
    try:
        curve = editor.to_curve()
        assert curve.apply(0.0) == 0.0
        assert curve.apply(1.0) == 1.0
        assert curve.apply(0.5) == 0.8
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------------------
# Hit testing
# ---------------------------------------------------------------------------


def test_hit_point_finds_endpoint_at_origin(qapp):
    editor = PressureCurveEditor()
    try:
        rect = _rect()
        # Endpoint (0, 0) maps to screen (0, 200) with the y-flip.
        idx = editor._hit_point(QPointF(2.0, 199.0), rect)  # noqa: SLF001
        assert idx == 0
    finally:
        editor.deleteLater()


def test_hit_point_returns_none_for_empty_space(qapp):
    editor = PressureCurveEditor()
    try:
        rect = _rect()
        idx = editor._hit_point(QPointF(100.0, 100.0), rect)  # noqa: SLF001
        assert idx is None
    finally:
        editor.deleteLater()


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


def test_dialog_returns_curve_after_edits(qapp):
    dialog = PressureCurveDialog(
        curve=PressureCurve(points=((0.0, 0.0), (1.0, 1.0))),
    )
    try:
        dialog.editor().set_points([(0.0, 0.0), (0.4, 0.6), (1.0, 1.0)])
        result = dialog.curve()
        assert result.points == ((0.0, 0.0), (0.4, 0.6), (1.0, 1.0))
    finally:
        dialog.deleteLater()
