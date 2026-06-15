"""Tests for :class:`PetShadowController`.

The controller folds the pet's three drop-shadow knobs (enabled /
opacity / scale) into one place. It talks to the canvas only through
``set_pet_shadow`` / ``pet_shadow_enabled`` and to settings through two
injected callables, so it is fully testable against a fake canvas with
no Qt / GL surface.
"""
from __future__ import annotations

from Imervue.desktop_pet.pet_shadow_controller import (
    DEFAULT_OPACITY,
    DEFAULT_SCALE,
    MAX_OPACITY,
    MAX_SCALE,
    PetShadowController,
)


class _FakeCanvas:
    """Records the last ``set_pet_shadow`` call and tracks enabled."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._enabled = False

    def set_pet_shadow(self, *, enabled: bool, opacity: float, scale: float) -> None:
        self._enabled = enabled
        self.calls.append({"enabled": enabled, "opacity": opacity, "scale": scale})

    def pet_shadow_enabled(self) -> bool:
        return self._enabled


def _make(settings: dict | None = None):
    store = dict(settings or {})
    canvas = _FakeCanvas()

    def read(key, default):
        return store.get(key, default)

    def persist(**fields):
        store.update(fields)

    return PetShadowController(canvas, read, persist), canvas, store


# ---------------------------------------------------------------
# apply_initial
# ---------------------------------------------------------------


def test_apply_initial_uses_persisted_values():
    ctl, canvas, _ = _make(
        {"pet_shadow_enabled": True, "pet_shadow_opacity": 0.4,
         "pet_shadow_scale": 1.5},
    )
    ctl.apply_initial()
    assert canvas.calls[-1] == {"enabled": True, "opacity": 0.4, "scale": 1.5}


def test_apply_initial_defaults_when_missing():
    ctl, canvas, _ = _make({})
    ctl.apply_initial()
    last = canvas.calls[-1]
    assert last["enabled"] is True
    assert last["opacity"] == DEFAULT_OPACITY
    assert last["scale"] == DEFAULT_SCALE


# ---------------------------------------------------------------
# set_enabled
# ---------------------------------------------------------------


def test_set_enabled_persists_and_applies():
    ctl, canvas, store = _make({"pet_shadow_opacity": 0.5, "pet_shadow_scale": 1.2})
    ctl.set_enabled(False)
    assert store["pet_shadow_enabled"] is False
    assert canvas.calls[-1] == {"enabled": False, "opacity": 0.5, "scale": 1.2}
    assert ctl.is_enabled() is False


def test_set_enabled_true_keeps_other_knobs():
    ctl, canvas, _ = _make({"pet_shadow_opacity": 0.3, "pet_shadow_scale": 0.9})
    ctl.set_enabled(True)
    assert canvas.calls[-1] == {"enabled": True, "opacity": 0.3, "scale": 0.9}
    assert ctl.is_enabled() is True


# ---------------------------------------------------------------
# set_opacity — clamp boundaries
# ---------------------------------------------------------------


def test_set_opacity_clamps_above_max():
    ctl, canvas, store = _make()
    ctl.set_opacity(5.0)
    assert store["pet_shadow_opacity"] == MAX_OPACITY
    assert canvas.calls[-1]["opacity"] == MAX_OPACITY


def test_set_opacity_clamps_below_zero():
    ctl, _, store = _make()
    ctl.set_opacity(-1.0)
    assert store["pet_shadow_opacity"] == 0.0


def test_set_opacity_keeps_enabled_and_scale():
    ctl, canvas, _ = _make({"pet_shadow_scale": 1.7})
    canvas._enabled = True
    ctl.set_opacity(0.6)
    last = canvas.calls[-1]
    assert last == {"enabled": True, "opacity": 0.6, "scale": 1.7}


# ---------------------------------------------------------------
# set_scale — clamp boundaries
# ---------------------------------------------------------------


def test_set_scale_clamps_above_max():
    ctl, _, store = _make()
    ctl.set_scale(99.0)
    assert store["pet_shadow_scale"] == MAX_SCALE


def test_set_scale_clamps_below_zero():
    ctl, _, store = _make()
    ctl.set_scale(-3.0)
    assert store["pet_shadow_scale"] == 0.0


def test_set_scale_just_inside_max_unchanged():
    ctl, _, store = _make()
    ctl.set_scale(MAX_SCALE)
    assert store["pet_shadow_scale"] == MAX_SCALE
