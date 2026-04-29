"""Tests for gradient-map effect."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.gradient_map import (
    INTENSITY_MAX,
    INTENSITY_MIN,
    GradientMapOptions,
    apply_gradient_map,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Options round-trip
# ---------------------------------------------------------------------------


def test_default_options_have_grayscale_endpoints():
    opts = GradientMapOptions()
    assert opts.stops[0] == (0.0, [0, 0, 0])
    assert opts.stops[-1] == (1.0, [255, 255, 255])


def test_round_trip_preserves_stops():
    stops = [(0.0, [10, 20, 30]), (0.5, [100, 50, 0]), (1.0, [255, 200, 100])]
    opts = GradientMapOptions(enabled=True, intensity=0.7, stops=stops)
    restored = GradientMapOptions.from_dict(opts.to_dict())
    assert restored.intensity == pytest.approx(0.7)
    assert restored.stops == [(0.0, [10, 20, 30]),
                              (0.5, [100, 50, 0]),
                              (1.0, [255, 200, 100])]


def test_intensity_clamped():
    too_low = GradientMapOptions.from_dict({"enabled": True, "intensity": -1})
    too_high = GradientMapOptions.from_dict({"enabled": True, "intensity": 5})
    assert too_low.intensity == pytest.approx(INTENSITY_MIN)
    assert too_high.intensity == pytest.approx(INTENSITY_MAX)


def test_stops_anchored_to_endpoints():
    """Missing 0.0 / 1.0 endpoints get extrapolated from the closest stop."""
    opts = GradientMapOptions.from_dict({
        "enabled": True,
        "stops": [(0.3, [255, 0, 0]), (0.7, [0, 0, 255])],
    })
    assert opts.stops[0][0] == 0.0
    assert opts.stops[-1][0] == 1.0


def test_garbage_stops_fall_back_to_default():
    opts = GradientMapOptions.from_dict({"enabled": True, "stops": "not a list"})
    assert opts.stops[0] == (0.0, [0, 0, 0])
    assert opts.stops[-1] == (1.0, [255, 255, 255])


def test_garbage_options_fall_back():
    assert GradientMapOptions.from_dict("oops").enabled is False


# ---------------------------------------------------------------------------
# apply_gradient_map behaviour
# ---------------------------------------------------------------------------


def test_disabled_is_identity():
    base = _solid(4, 4, (100, 50, 200))
    out = apply_gradient_map(base, GradientMapOptions(enabled=False))
    assert np.array_equal(out, base)


def test_zero_intensity_is_identity():
    base = _solid(4, 4, (100, 50, 200))
    opts = GradientMapOptions(enabled=True, intensity=0.0)
    out = apply_gradient_map(base, opts)
    assert np.array_equal(out, base)


def test_full_intensity_replaces_with_gradient():
    """Full intensity + sepia gradient on mid-grey input → sepia midtone colour."""
    base = _solid(4, 4, (128, 128, 128))
    opts = GradientMapOptions(
        enabled=True, intensity=1.0,
        stops=[(0.0, [50, 30, 10]), (1.0, [220, 200, 150])],
    )
    out = apply_gradient_map(base, opts)
    # Midpoint of the two stops is approximately (135, 115, 80)
    r, g, b = int(out[0, 0, 0]), int(out[0, 0, 1]), int(out[0, 0, 2])
    assert 130 <= r <= 145
    assert 110 <= g <= 125
    assert 75 <= b <= 90


def test_partial_intensity_blends_toward_gradient():
    base = _solid(4, 4, (128, 128, 128))
    opts = GradientMapOptions(
        enabled=True, intensity=0.5,
        stops=[(0.0, [255, 0, 0]), (1.0, [255, 0, 0])],  # solid red gradient
    )
    out = apply_gradient_map(base, opts)
    # 50% original (grey) + 50% red → reddish midtone
    assert int(out[0, 0, 0]) > 128
    assert int(out[0, 0, 1]) < 128
    assert int(out[0, 0, 2]) < 128


def test_alpha_preserved():
    base = _solid(4, 4, (100, 100, 100))
    base[..., 3] = 64
    opts = GradientMapOptions(enabled=True, intensity=1.0)
    out = apply_gradient_map(base, opts)
    assert (out[..., 3] == 64).all()


def test_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_gradient_map(arr, GradientMapOptions(enabled=True))


# ---------------------------------------------------------------------------
# Recipe integration
# ---------------------------------------------------------------------------


def test_recipe_with_only_gradient_is_not_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    assert r.is_identity() is True
    r.extra["gradient_map"] = {"enabled": True, "intensity": 1.0,
                               "stops": [(0.0, [0, 0, 0]), (1.0, [255, 255, 255])]}
    assert r.is_identity() is False


def test_recipe_disabled_gradient_stays_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["gradient_map"] = {"enabled": False, "intensity": 1.0,
                               "stops": [(0.0, [0, 0, 0]), (1.0, [255, 0, 0])]}
    assert r.is_identity() is True


# ---------------------------------------------------------------------------
# Dialog smoke
# ---------------------------------------------------------------------------


def test_dialog_loads_existing_recipe(qapp, tmp_path):
    from Imervue.gui.gradient_map_dialog import GRADIENT_PRESETS, GradientMapDialog
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import recipe_store

    img = tmp_path / "x.png"
    img.write_bytes(b"x")
    sepia_stops = next(s for (pid, s) in GRADIENT_PRESETS if pid == "sepia")
    recipe = Recipe()
    recipe.extra["gradient_map"] = {
        "enabled": True, "intensity": 0.6,
        "stops": list(sepia_stops),
    }
    recipe_store.set_for_path(str(img), recipe)

    class FakeViewer:
        model = type("M", (), {"images": [str(img)]})()
        current_index = 0

    dlg = GradientMapDialog(FakeViewer(), str(img))
    assert dlg._enable.isChecked() is True
    assert dlg._preset_combo.currentData() == "sepia"
    assert dlg._intensity.value() == 60


def test_dialog_unknown_stops_default_to_first_preset(qapp, tmp_path):
    from Imervue.gui.gradient_map_dialog import GradientMapDialog
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import recipe_store

    img = tmp_path / "y.png"
    img.write_bytes(b"y")
    recipe = Recipe()
    recipe.extra["gradient_map"] = {
        "enabled": True, "intensity": 1.0,
        "stops": [(0.0, [10, 10, 10]), (1.0, [200, 100, 50])],  # custom
    }
    recipe_store.set_for_path(str(img), recipe)

    class FakeViewer:
        model = type("M", (), {"images": [str(img)]})()
        current_index = 0

    dlg = GradientMapDialog(FakeViewer(), str(img))
    # Custom stops fall back to the first preset (mono) rather than crashing
    assert dlg._preset_combo.currentIndex() == 0
