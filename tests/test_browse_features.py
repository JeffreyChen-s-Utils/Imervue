"""Tests for the BrowseFeatures collaborator.

``reload_settings`` and ``clamp_pan`` are unit-testable without a live GL view:
the first re-reads three flags from user settings, the second is pure offset
math over the view's deep-zoom state. The rest of the collaborator drives the
real ``GPUImageView``.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from Imervue.gpu_image_view.browse_features import BrowseFeatures
from Imervue.user_settings.user_setting_dict import user_setting_dict

# Square image → minimap reserve of 140 + 12 margin keeps a 152 px bottom band
# clear, so a 1000 px canvas centres pans inside an 848 px content height.
_SQUARE_RESERVE = 152


def _view():
    view = SimpleNamespace(
        _filmstrip_enabled=True,
        _transition_enabled=True,
        _smooth_nav_enabled=False,
        deep_zoom=None,
        tile_grid_mode=False,
        settle_refits=0,
        updates=0,
        update=lambda: None,
    )
    view._schedule_settle_refit = lambda: setattr(
        view, "settle_refits", view.settle_refits + 1)
    return view


def _clamp_view(img_w, img_h, canvas, zoom, offset):
    deep = SimpleNamespace(levels=[np.zeros((img_h, img_w, 4), dtype=np.uint8)])
    return SimpleNamespace(
        deep_zoom=deep,
        zoom=zoom,
        dz_offset_x=offset[0],
        dz_offset_y=offset[1],
        _last_resize_size=canvas,
        tile_grid_mode=False,
        _filmstrip_enabled=False,
        model=SimpleNamespace(images=[0]),
    )


def test_clamp_pan_centres_fit_image_inside_content_area():
    # A fit image (smaller than the canvas) is re-centred; vertically it lands
    # in the content area (848) above the band, not the full 1000 px canvas.
    view = _clamp_view(500, 500, (1000, 1000), 1.0, (12.0, 12.0))
    BrowseFeatures(view).clamp_pan()
    assert view.dz_offset_x == (1000 - 500) / 2
    assert view.dz_offset_y == (1000 - _SQUARE_RESERVE - 500) / 2


def test_clamp_pan_holds_zoomed_image_bottom_above_band():
    # Zoomed past the canvas (extent 2000): panning the bottom edge up stops at
    # the content height so the last rows clear the overlay band rather than
    # hiding under it. Offsets start well past the lower bound so both axes
    # clamp to their minimum.
    view = _clamp_view(500, 500, (1000, 1000), 4.0, (-5000.0, -5000.0))
    BrowseFeatures(view).clamp_pan()
    content_h = 1000 - _SQUARE_RESERVE
    assert view.dz_offset_y == content_h - 2000  # image bottom rests at 848
    assert view.dz_offset_x == 1000 - 2000  # x clamps over the full width


def test_clamp_pan_no_deep_zoom_is_noop():
    view = SimpleNamespace(deep_zoom=None, dz_offset_x=7.0, dz_offset_y=9.0)
    BrowseFeatures(view).clamp_pan()
    assert (view.dz_offset_x, view.dz_offset_y) == (7.0, 9.0)


def test_reload_settings_pulls_flags_from_user_settings():
    view = _view()
    user_setting_dict["filmstrip_enabled"] = False
    user_setting_dict["image_transition_enabled"] = False
    user_setting_dict["smooth_navigation_enabled"] = True
    BrowseFeatures(view).reload_settings()
    assert view._filmstrip_enabled is False
    assert view._transition_enabled is False
    assert view._smooth_nav_enabled is True


def test_reload_settings_uses_defaults_when_unset():
    view = _view()
    for key in ("filmstrip_enabled", "image_transition_enabled",
                "smooth_navigation_enabled"):
        user_setting_dict.pop(key, None)
    view._filmstrip_enabled = False
    view._transition_enabled = False
    view._smooth_nav_enabled = True
    BrowseFeatures(view).reload_settings()
    # Defaults: filmstrip on, transition on, smooth-nav off.
    assert view._filmstrip_enabled is True
    assert view._transition_enabled is True
    assert view._smooth_nav_enabled is False


def test_reload_settings_refits_live_deep_zoom_when_filmstrip_toggled():
    # Toggling the filmstrip changes the reserved band → the shown image must
    # re-fit so it isn't left cropped / gapped.
    view = _view()
    view.deep_zoom = object()
    view._filmstrip_enabled = True
    user_setting_dict["filmstrip_enabled"] = False
    BrowseFeatures(view).reload_settings()
    assert view._filmstrip_enabled is False
    assert view.settle_refits == 1


def test_reload_settings_no_refit_when_filmstrip_unchanged():
    view = _view()
    view.deep_zoom = object()
    view._filmstrip_enabled = True
    user_setting_dict["filmstrip_enabled"] = True  # same as before
    BrowseFeatures(view).reload_settings()
    assert view.settle_refits == 0


def test_reload_settings_no_refit_off_the_deep_zoom_view():
    # On the tile wall (or with no image) there's nothing to re-fit.
    view = _view()  # deep_zoom is None
    view._filmstrip_enabled = True
    user_setting_dict["filmstrip_enabled"] = False
    BrowseFeatures(view).reload_settings()
    assert view.settle_refits == 0


# ---------------------------------------------------------------
# Reading mode: scroll / bottom-anchor against the CONTENT area
# ---------------------------------------------------------------
# Regression: both measured the viewport as ``view.height()``. The minimap /
# filmstrip band is drawn over the bottom of the canvas, so that stopped the
# scroll a band-height short — the foot of every page stayed hidden behind the
# overlay and the edge auto-advance fired against that same wrong edge.

_CANVAS = (1000, 1000)
_CONTENT_H = 1000 - _SQUARE_RESERVE          # 848


def _reading_view(img_h, zoom=1.0, offset_y=0.0, img_w=500):
    deep = SimpleNamespace(levels=[np.zeros((img_h, img_w, 4), dtype=np.uint8)])
    view = SimpleNamespace(
        deep_zoom=deep,
        zoom=zoom,
        dz_offset_x=0.0,
        dz_offset_y=offset_y,
        _last_resize_size=_CANVAS,
        tile_grid_mode=False,
        _filmstrip_enabled=False,
        model=SimpleNamespace(images=[0]),
        updates=0,
        width=lambda: _CANVAS[0],
        height=lambda: _CANVAS[1],
    )
    view.update = lambda: setattr(view, "updates", view.updates + 1)
    view._fit_to_width = lambda: None
    return view


def test_reading_scroll_bottom_stops_at_the_content_area_not_the_canvas():
    # Page 2000 px tall, already scrolled near its end. The lowest reachable
    # offset must bottom the page at the content edge (848) so its last rows
    # clear the band — against the raw 1000 px canvas it would stop 152 px early
    # and those rows would sit under the minimap forever.
    view = _reading_view(2000, offset_y=-1100.0)
    BrowseFeatures(view).reading_wheel(-500.0)
    assert view.dz_offset_y == _CONTENT_H - 2000


def test_reading_scroll_advances_only_past_the_content_edge():
    # Sitting exactly on the content-area bottom edge; one more scroll down is
    # the page turn.
    view = _reading_view(2000, offset_y=float(_CONTENT_H - 2000))
    called = {}
    import Imervue.gpu_image_view.actions.select as select_mod
    original = select_mod.switch_to_next_image
    select_mod.switch_to_next_image = lambda main_gui: called.setdefault("next", main_gui)
    try:
        BrowseFeatures(view).reading_wheel(-50.0)
    finally:
        select_mod.switch_to_next_image = original
    assert called.get("next") is view


def test_reading_page_taller_than_content_scrolls_instead_of_advancing():
    # 900 px page: it fits the 1000 px canvas but NOT the 848 px content area,
    # so it must scroll. Measured against the canvas it counted as "fits" and
    # any scroll turned the page, skipping content hidden under the band.
    view = _reading_view(900)
    called = {}
    import Imervue.gpu_image_view.actions.select as select_mod
    original = select_mod.switch_to_next_image
    select_mod.switch_to_next_image = lambda main_gui: called.setdefault("next", main_gui)
    try:
        BrowseFeatures(view).reading_wheel(-30.0)
    finally:
        select_mod.switch_to_next_image = original
    assert called == {}
    assert view.dz_offset_y == -30.0


def test_reading_scroll_up_within_the_page_does_not_advance():
    view = _reading_view(2000, offset_y=-500.0)
    BrowseFeatures(view).reading_wheel(200.0)
    assert view.dz_offset_y == -300.0
    assert view.updates == 1


def test_reading_bottom_anchor_uses_the_content_area():
    # Paging backwards opens the previous page at its end: the page bottom must
    # rest on the content edge, not under the band.
    view = _reading_view(2000)
    features = BrowseFeatures(view)
    features._anchor_bottom = True
    features.apply_reading_fit()
    assert view.dz_offset_y == _CONTENT_H - 2000


def test_reading_bottom_anchor_is_zero_for_a_page_that_fits():
    view = _reading_view(400)
    features = BrowseFeatures(view)
    features._anchor_bottom = True
    features.apply_reading_fit()
    # Shorter than the content area → no bottom-align, and clamp_pan centres it.
    assert view.dz_offset_y == (_CONTENT_H - 400) / 2


def test_reading_fit_forward_opens_at_the_top():
    view = _reading_view(2000, offset_y=-900.0)
    features = BrowseFeatures(view)
    features._anchor_bottom = False
    features.apply_reading_fit()
    assert view.dz_offset_y == 0.0


def test_reading_bottom_anchor_resets_after_use():
    view = _reading_view(2000)
    features = BrowseFeatures(view)
    features._anchor_bottom = True
    features.apply_reading_fit()
    assert features._anchor_bottom is False
