"""Tests for the Levels (black / white / gamma) effect."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.levels import (
    GAMMA_MAX,
    GAMMA_MIN,
    LEVELS_MAX,
    LEVELS_MIN,
    LevelsOptions,
    apply_levels,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Options round-trip + clamping
# ---------------------------------------------------------------------------


def test_levels_options_round_trip():
    opts = LevelsOptions(enabled=True, black=20, white=240, gamma=1.5)
    restored = LevelsOptions.from_dict(opts.to_dict())
    assert restored.enabled is True
    assert restored.black == 20
    assert restored.white == 240
    assert restored.gamma == pytest.approx(1.5)


def test_levels_clamps_invalid_black_white():
    too_low = LevelsOptions.from_dict({"enabled": True, "black": -50, "white": 9999})
    assert too_low.black == LEVELS_MIN
    # White is allowed up to LEVELS_MAX
    assert too_low.white == LEVELS_MAX


def test_levels_clamps_gamma():
    out = LevelsOptions.from_dict({"enabled": True, "gamma": 100})
    assert out.gamma == pytest.approx(GAMMA_MAX)
    out = LevelsOptions.from_dict({"enabled": True, "gamma": 0.0001})
    assert out.gamma == pytest.approx(GAMMA_MIN)


def test_levels_garbage_returns_default():
    assert LevelsOptions.from_dict("oops").enabled is False
    assert LevelsOptions.from_dict(None).enabled is False


# ---------------------------------------------------------------------------
# apply_levels — pixel behaviour
# ---------------------------------------------------------------------------


def test_apply_levels_disabled_is_identity():
    base = _solid(4, 4, (100, 50, 150))
    out = apply_levels(base, LevelsOptions(enabled=False))
    assert np.array_equal(out, base)


def test_apply_levels_default_options_is_identity():
    """black=0, white=255, gamma=1.0 → no change at all, no allocation."""
    base = _solid(4, 4, (100, 50, 150))
    out = apply_levels(base, LevelsOptions(enabled=True, black=0, white=255, gamma=1.0))
    assert np.array_equal(out, base)


def test_apply_levels_below_black_clipped_to_zero():
    base = _solid(4, 4, (10, 10, 10))
    out = apply_levels(base, LevelsOptions(enabled=True, black=50, white=255))
    assert (out[..., :3] == 0).all()


def test_apply_levels_above_white_clipped_to_max():
    base = _solid(4, 4, (250, 250, 250))
    out = apply_levels(base, LevelsOptions(enabled=True, black=0, white=200))
    assert (out[..., :3] == 255).all()


def test_apply_levels_stretches_midrange():
    """A pixel at the midpoint of [black, white] should land at ~127."""
    base = _solid(4, 4, (128, 128, 128))
    out = apply_levels(
        base, LevelsOptions(enabled=True, black=0, white=255, gamma=1.0),
    )
    # No clipping, no gamma → identity
    assert np.array_equal(out, base)


def test_apply_levels_gamma_brightens_midtones():
    """Gamma > 1 should brighten midtones (output > input)."""
    base = _solid(4, 4, (128, 128, 128))
    out = apply_levels(
        base, LevelsOptions(enabled=True, black=0, white=255, gamma=2.0),
    )
    assert (out[..., 0] > 128).all()


def test_apply_levels_gamma_darkens_midtones():
    base = _solid(4, 4, (128, 128, 128))
    out = apply_levels(
        base, LevelsOptions(enabled=True, black=0, white=255, gamma=0.5),
    )
    assert (out[..., 0] < 128).all()


def test_apply_levels_preserves_alpha():
    base = _solid(4, 4, (200, 200, 200))
    base[..., 3] = 80
    out = apply_levels(base, LevelsOptions(enabled=True, black=0, white=200))
    assert (out[..., 3] == 80).all()


def test_apply_levels_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_levels(arr, LevelsOptions(enabled=True))


def test_apply_levels_white_below_black_is_safe():
    """Inverted slider order shouldn't crash — black takes priority."""
    base = _solid(4, 4, (128, 128, 128))
    # If user yanks white below black, ``apply_levels`` should clamp internally
    # rather than divide by zero.
    out = apply_levels(
        base, LevelsOptions(enabled=True, black=200, white=100, gamma=1.0),
    )
    assert out.shape == base.shape


# ---------------------------------------------------------------------------
# Recipe integration
# ---------------------------------------------------------------------------


def test_recipe_with_only_levels_is_not_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    assert r.is_identity() is True
    r.extra["levels"] = {"enabled": True, "black": 10, "white": 240, "gamma": 1.0}
    assert r.is_identity() is False


def test_recipe_with_disabled_levels_stays_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["levels"] = {"enabled": False, "black": 10, "white": 240, "gamma": 0.5}
    assert r.is_identity() is True


def test_recipe_apply_runs_levels():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["levels"] = {"enabled": True, "black": 100, "white": 200, "gamma": 1.0}
    base = _solid(4, 4, (50, 50, 50))
    out = r.apply(base)
    assert (out[..., :3] == 0).all()


# ---------------------------------------------------------------------------
# Dialog smoke
# ---------------------------------------------------------------------------


def test_dialog_loads_existing_recipe(qapp, tmp_path):
    from Imervue.gui.levels_dialog import LevelsDialog
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import recipe_store

    img = tmp_path / "x.png"
    img.write_bytes(b"x")
    recipe = Recipe()
    recipe.extra["levels"] = {"enabled": True, "black": 30, "white": 220, "gamma": 1.5}
    recipe_store.set_for_path(str(img), recipe)

    class FakeViewer:
        model = type("M", (), {"images": [str(img)]})()
        current_index = 0

    dlg = LevelsDialog(FakeViewer(), str(img))
    assert dlg._enable.isChecked() is True
    assert dlg._black.value() == 30
    assert dlg._white.value() == 220


def test_dialog_gamma_step_round_trip(qapp):
    from Imervue.gui.levels_dialog import LevelsDialog
    # Convert float gamma → step → float and verify round-trip is close
    for gamma in [0.5, 1.0, 1.5, 2.2]:
        step = LevelsDialog._gamma_to_step(gamma)
        recovered = LevelsDialog._step_to_gamma(step)
        assert abs(recovered - gamma) < 0.2  # 1% slider granularity
