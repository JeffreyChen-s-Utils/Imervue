"""Annotation handle geometry preserves endpoint and degenerate behavior."""
import pytest
from PySide6.QtCore import QRectF

from Imervue.gui.annotation_geometry import handle_positions, resize_points


def test_handle_order_matches_clockwise_canvas_cursor_names():
    assert handle_positions(QRectF(10, 20, 40, 60)) == [
        (10, 20), (30, 20), (50, 20), (50, 50),
        (50, 80), (30, 80), (10, 80), (10, 50),
    ]


@pytest.mark.parametrize("points", [[], [(10, 20)]])
def test_resize_keeps_degenerate_point_sequences(points):
    assert resize_points(points, "se", 50, 60) is points


def test_resize_normalizes_reversed_endpoints_and_preserves_interior_points():
    original = [(40, 60), (35, 45), (20, 30)]
    assert resize_points(original, "nw", -4, -6) == [(16, 24), (35, 45), (40, 60)]
    assert original == [(40, 60), (35, 45), (20, 30)]


def test_resize_can_cross_opposite_endpoint_without_reordering_the_result():
    assert resize_points([(0, 0), (10, 10)], "nw", 20, 30) == [(20, 30), (10, 10)]
