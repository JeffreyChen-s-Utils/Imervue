"""Tests for the comic stamp generators + StampDock smoke."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.comic_stamps import (
    STAMP_LIBRARY,
    cloud_balloon,
    jagged_shout,
    oval_balloon,
    panel_border,
    rect_balloon,
    render_stamp,
    sound_burst,
    stamp_by_key,
)


@pytest.mark.parametrize(
    "generator,kwargs", [
        (oval_balloon, {"width": 100, "height": 60}),
        (rect_balloon, {"width": 80, "height": 50}),
        (cloud_balloon, {"width": 100, "height": 80}),
        (jagged_shout, {"width": 90, "height": 90}),
        (panel_border, {"width": 120, "height": 80}),
    ],
)
def test_generator_returns_correct_rgba_shape(generator, kwargs):
    arr = generator(**kwargs)
    assert arr.dtype == np.uint8
    assert arr.shape == (kwargs["height"], kwargs["width"], 4)
    # The drawn outline must include at least one fully-opaque pixel.
    assert int(arr[..., 3].max()) == 255


def test_sound_burst_is_square():
    arr = sound_burst(64)
    assert arr.shape == (64, 64, 4)
    # Centre pixel sits on either the inner-circle outline or the
    # blank centre — check the burst rays reach the edge.
    edge_alpha = arr[0, 32, 3]
    centre_alpha = arr[32, 32, 3]
    # At least one ray must touch the canvas edge column.
    assert int(arr[:, 32, 3].max()) == 255
    # Sanity: the centre is more transparent than the bright ray
    # reaching the edge from the centre.
    assert int(edge_alpha) >= int(centre_alpha)


def test_library_contains_unique_keys():
    keys = [s.key for s in STAMP_LIBRARY]
    assert len(keys) == len(set(keys))
    assert len(STAMP_LIBRARY) >= 5


def test_stamp_by_key_resolves_known_entries():
    stamp = stamp_by_key("paint_stamp_oval_balloon")
    assert stamp.kind == "balloon"
    assert callable(stamp.generator)


def test_stamp_by_key_raises_on_unknown():
    with pytest.raises(KeyError):
        stamp_by_key("paint_stamp_does_not_exist")


def test_render_stamp_dispatches_burst_to_square_size():
    """A 200x80 request for the burst stamp clamps to a 80x80 square."""
    arr = render_stamp("paint_stamp_sound_burst", 200, 80)
    assert arr.shape == (80, 80, 4)


def test_render_stamp_dispatches_balloon_to_full_size():
    arr = render_stamp("paint_stamp_oval_balloon", 120, 60)
    assert arr.shape == (60, 120, 4)


def test_generator_rejects_non_positive_size():
    with pytest.raises(ValueError):
        oval_balloon(0, 50)
    with pytest.raises(ValueError):
        oval_balloon(50, -1)


# ---------------------------------------------------------------------------
# Dock smoke
# ---------------------------------------------------------------------------


def test_stamp_dock_emits_key_on_click(qapp):
    from Imervue.paint.stamp_dock import StampDock
    dock = StampDock()
    try:
        emitted: list[str] = []
        dock.stamp_chosen.connect(emitted.append)
        # Find the first button and trigger its click.
        from PySide6.QtWidgets import QToolButton
        buttons = dock.findChildren(QToolButton)
        assert len(buttons) >= 5
        buttons[0].click()
        assert emitted, "expected stamp_chosen to fire on click"
        assert emitted[0].startswith("paint_stamp_")
    finally:
        dock.deleteLater()


def test_stamp_dock_one_button_per_library_entry(qapp):
    from Imervue.paint.stamp_dock import StampDock
    from PySide6.QtWidgets import QToolButton

    dock = StampDock()
    try:
        buttons = dock.findChildren(QToolButton)
        assert len(buttons) == len(STAMP_LIBRARY)
    finally:
        dock.deleteLater()
