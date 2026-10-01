"""Tests for InputController's rubber-band (box) zoom.

The pure region-fit math lives in ``view_nav.zoom_to_region`` and is unit-tested
in ``test_view_nav``; this module covers the one stateful decision the
controller makes around it — fitting the boxed region into the *content area*
(canvas minus the reserved overlay band) rather than the full canvas, so a
height-limited selection isn't over-zoomed with its bottom rows hidden behind
the minimap / filmstrip. No Qt / GL needed: a ``SimpleNamespace`` stand-in
supplies the view state the offset math reads (same approach as
``test_browse_features``).
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.gpu_image_view import fit_view
from Imervue.gpu_image_view.browse_features import BrowseFeatures
from Imervue.gpu_image_view.input_controller import InputController


class _Point:
    """Minimal QPointF stand-in: ``_apply_zoom_band`` calls ``.x()`` / ``.y()``."""

    def __init__(self, x: float, y: float) -> None:
        self._x = x
        self._y = y

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y


def _band_view(img_w, img_h, canvas, *, zoom=1.0, offset=(0.0, 0.0)):
    deep = SimpleNamespace(levels=[np.zeros((img_h, img_w, 4), dtype=np.uint8)])
    view = SimpleNamespace(
        deep_zoom=deep,
        zoom=zoom,
        dz_offset_x=offset[0],
        dz_offset_y=offset[1],
        _last_resize_size=canvas,
        tile_grid_mode=False,
        _filmstrip_enabled=False,
        model=SimpleNamespace(images=[0]),
        _user_locked_view=False,
        _update_status_info=lambda: None,
        update=lambda: None,
    )
    view._browse = BrowseFeatures(view)
    return view


def test_zoom_band_fits_region_into_content_area_not_full_canvas():
    # Square 1000px image/canvas → 152px reserved band → 848px content height.
    # A tall, narrow box (200x800) is height-limited: it must fill the 848px
    # content area (zoom 848/800 = 1.06), NOT the full 1000px canvas (zoom
    # 1.25), which would push its bottom 152 rows behind the overlay band.
    view = _band_view(1000, 1000, (1000, 1000))
    content_h = 1000 - fit_view.reserved_overlay_height(view)
    region_h = 800

    InputController(view)._apply_zoom_band(_Point(400, 100), _Point(600, 900))

    assert view.zoom == pytest.approx(content_h / region_h)
    # The boxed region (image rows 100..900) lands entirely within the content
    # area — its bottom row maps to exactly content_h, clear of the band.
    region_bottom_screen = view.dz_offset_y + 900 * view.zoom
    assert region_bottom_screen == pytest.approx(content_h)
    assert view._user_locked_view is True


def test_zoom_band_width_limited_region_unaffected_by_band():
    # A wide box (800x200) is width-limited, so the reserved band never binds
    # the zoom (the height term stays larger). Guards against the content-area
    # fix over-correcting selections the band has no say in.
    view = _band_view(1000, 1000, (1000, 1000))
    region_w = 800

    InputController(view)._apply_zoom_band(_Point(100, 400), _Point(900, 600))

    assert view.zoom == pytest.approx(1000 / region_w)


def _tile_view(images):
    """Minimal stand-in exposing the state ``enter_deep_zoom`` reads/writes."""
    return SimpleNamespace(
        model=SimpleNamespace(images=list(images)),
        current_index=0,
        tile_grid_mode=True,
        grid_offset_x=5,
        grid_offset_y=7,
        tile_scale=1.5,
        loaded=[],
    )


def test_minimap_recenter_centres_in_content_area_not_full_canvas():
    # 1000x1000 image in a 1000x1000 canvas → 152 px reserved band, content 848.
    # A click at the minimap's vertical centre (image row 500) must be centred at
    # content_h/2, NOT the full canvas centre (which would land it ~76 px low).
    view = _band_view(1000, 1000, (1000, 1000), zoom=2.0)
    InputController(view)._recenter_on_minimap(_Point(50, 50), (0, 0, 100, 100), 2.0)
    content_h = 1000 - fit_view.reserved_overlay_height(view)
    assert view.dz_offset_y == pytest.approx(content_h / 2 - 500 * 2.0)


def test_enter_deep_zoom_opens_clicked_tile():
    view = _tile_view(["/p/a.png", "/p/b.png"])
    view.load_deep_zoom_image = view.loaded.append
    InputController(view).enter_deep_zoom("/p/b.png")
    assert view.tile_grid_mode is False
    assert view.current_index == 1
    assert view.loaded == ["/p/b.png"]
    # The wall scroll/scale is snapshotted so exiting deep zoom restores it.
    assert view._saved_tile_state == {
        "grid_offset_x": 5, "grid_offset_y": 7, "tile_scale": 1.5,
    }


def test_enter_deep_zoom_ignores_tile_removed_from_model():
    # Stale rect: the folder dropped this path after the last wall paint. The
    # click must be a no-op — stay on the wall, start no doomed load that the
    # completion guard would discard into a stuck "Loading…" view.
    view = _tile_view(["/p/a.png", "/p/b.png"])
    view.load_deep_zoom_image = view.loaded.append
    InputController(view).enter_deep_zoom("/p/gone.png")
    assert view.tile_grid_mode is True     # unchanged — still on the wall
    assert view.current_index == 0
    assert view.loaded == []
    assert not hasattr(view, "_saved_tile_state")



class _Event:
    """Stand-in for a QMouseEvent: position and global position."""

    def __init__(self, x: float, y: float) -> None:
        self._pos = _Point(x, y)

    def position(self):
        return self._pos

    def globalPosition(self):  # noqa: N802 - Qt's name
        return SimpleNamespace(toPoint=lambda: (0, 0))


def _wall(selection_mode=False):
    view = _tile_view(["/p/a.png", "/p/b.png"])
    view.tile_rects = [(0, 0, 100, 100, "/p/a.png"), (110, 0, 210, 100, "/p/b.png")]
    view.tile_selection_mode = selection_mode
    view.selected_tiles = set()
    view._drag_selecting = False
    view._middle_dragging = False
    view._drag_start_pos = _Point(50, 50)   # set by the press
    view._drag_end_pos = _Point(50, 50)
    view._hover_last_path = None
    armed = []
    view._hover_controller = SimpleNamespace(arm=lambda path, _pos: armed.append(path),
                                             disarm=lambda: None)
    view.load_deep_zoom_image = view.loaded.append
    view.update = lambda: None
    return view, armed


@pytest.mark.parametrize("selection_mode", [False, True])
def test_a_plain_click_forgets_where_the_press_was(selection_mode):
    """Left set, the press point read as a drag in progress from then on."""
    view, _armed = _wall(selection_mode)
    InputController(view).handle_tile_release(_Event(150, 50))
    assert view._drag_start_pos is None
    assert view._drag_end_pos is None


def test_a_click_on_empty_wall_forgets_it_too():
    view, _armed = _wall()
    assert InputController(view).handle_tile_release(_Event(500, 500)) is False
    assert view._drag_start_pos is None


def test_hover_works_again_after_a_click():
    """The hover preview (and the hovered-tile target of the rating keys) died after one click."""
    from Imervue.gpu_image_view.hover_preview_binding import update_hover_preview
    view, armed = _wall(selection_mode=True)   # a click that toggles, staying on the wall
    InputController(view).handle_tile_release(_Event(150, 50))
    update_hover_preview(view, _Event(50, 50))
    assert armed == ["/p/a.png"]
    assert view._hover_last_path == "/p/a.png"
