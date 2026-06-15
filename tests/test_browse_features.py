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
    return SimpleNamespace(
        _filmstrip_enabled=True,
        _transition_enabled=True,
        _smooth_nav_enabled=False,
        updates=0,
        update=lambda: None,
    )


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
