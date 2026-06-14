"""Tests for the BrowseFeatures collaborator's settings reload.

Only ``reload_settings`` is unit-testable without a live GL view (the rest of
the collaborator drives the real ``GPUImageView``); it just re-reads three
flags from user settings, so a SimpleNamespace stand-in suffices.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view.browse_features import BrowseFeatures
from Imervue.user_settings.user_setting_dict import user_setting_dict


def _view():
    return SimpleNamespace(
        _filmstrip_enabled=True,
        _transition_enabled=True,
        _smooth_nav_enabled=False,
        updates=0,
        update=lambda: None,
    )


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
