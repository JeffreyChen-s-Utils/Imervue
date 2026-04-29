"""Tests for the procedural lens-flare overlay."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.lens_flare import (
    INTENSITY_MAX,
    SIZE_MAX,
    SIZE_MIN,
    LensFlareOptions,
    apply_lens_flare,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Options round-trip
# ---------------------------------------------------------------------------


def test_default_options_use_warm_yellow():
    opts = LensFlareOptions()
    assert opts.colour == [255, 235, 180]
    assert opts.position == [0.7, 0.3]


def test_round_trip_via_dict():
    opts = LensFlareOptions(
        enabled=True, position=[0.2, 0.8], intensity=0.5,
        size=0.6, colour=[100, 200, 50],
    )
    restored = LensFlareOptions.from_dict(opts.to_dict())
    assert restored.enabled is True
    assert restored.position == pytest.approx([0.2, 0.8])
    assert restored.intensity == pytest.approx(0.5)
    assert restored.size == pytest.approx(0.6)
    assert restored.colour == [100, 200, 50]


def test_position_clamped_to_unit_square():
    out = LensFlareOptions.from_dict({
        "enabled": True, "position": [-1.0, 5.0],
    })
    assert out.position == [0.0, 1.0]


def test_size_clamped():
    too_low = LensFlareOptions.from_dict({"enabled": True, "size": 0.0001})
    too_high = LensFlareOptions.from_dict({"enabled": True, "size": 99})
    assert too_low.size == pytest.approx(SIZE_MIN)
    assert too_high.size == pytest.approx(SIZE_MAX)


def test_intensity_clamped():
    too_high = LensFlareOptions.from_dict({"enabled": True, "intensity": 9})
    assert too_high.intensity == pytest.approx(INTENSITY_MAX)


def test_colour_clamped_per_channel():
    out = LensFlareOptions.from_dict({
        "enabled": True, "colour": [-99, 999, 128],
    })
    assert out.colour == [0, 255, 128]


def test_garbage_returns_default():
    assert LensFlareOptions.from_dict("oops").enabled is False
    assert LensFlareOptions.from_dict({"position": "bad"}).position == [0.7, 0.3]


# ---------------------------------------------------------------------------
# apply_lens_flare behaviour
# ---------------------------------------------------------------------------


def test_disabled_is_identity():
    base = _solid(32, 32, (50, 50, 50))
    out = apply_lens_flare(base, LensFlareOptions(enabled=False))
    assert np.array_equal(out, base)


def test_zero_intensity_is_identity():
    base = _solid(32, 32, (50, 50, 50))
    opts = LensFlareOptions(enabled=True, intensity=0.0)
    out = apply_lens_flare(base, opts)
    assert np.array_equal(out, base)


def test_flare_brightens_pixels_near_centre():
    base = _solid(64, 64, (10, 10, 10))
    opts = LensFlareOptions(
        enabled=True, position=[0.5, 0.5],
        intensity=1.0, size=0.5,
    )
    out = apply_lens_flare(base, opts)
    centre = out[32, 32, :3]
    corner = out[0, 0, :3]
    # The centre should be much brighter than the dark corner
    assert int(centre[0]) > int(corner[0]) + 10


def test_flare_position_controls_brightest_spot():
    base = _solid(64, 64, (10, 10, 10))
    opts_top_left = LensFlareOptions(
        enabled=True, position=[0.0, 0.0], intensity=1.0, size=0.3,
    )
    out = apply_lens_flare(base, opts_top_left)
    # Top-left should now be bright; bottom-right relatively dark
    assert int(out[0, 0, 0]) > int(out[63, 63, 0])


def test_flare_colour_tints_overlay():
    """Pure-blue flare overlay should mostly add to the blue channel."""
    base = _solid(64, 64, (50, 50, 50))
    opts = LensFlareOptions(
        enabled=True, position=[0.5, 0.5],
        intensity=1.0, size=0.4, colour=[0, 0, 255],
    )
    out = apply_lens_flare(base, opts)
    # Centre pixel — blue channel must increase more than red
    delta_r = int(out[32, 32, 0]) - 50
    delta_b = int(out[32, 32, 2]) - 50
    assert delta_b > delta_r + 50


def test_alpha_preserved():
    base = _solid(16, 16, (50, 50, 50))
    base[..., 3] = 80
    opts = LensFlareOptions(enabled=True, intensity=1.0)
    out = apply_lens_flare(base, opts)
    assert (out[..., 3] == 80).all()


def test_clip_to_uint8_range():
    base = _solid(16, 16, (240, 240, 240))
    opts = LensFlareOptions(enabled=True, intensity=1.0,
                            colour=[255, 255, 255], size=0.8)
    out = apply_lens_flare(base, opts)
    assert out.max() <= 255


def test_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_lens_flare(arr, LensFlareOptions(enabled=True))


# ---------------------------------------------------------------------------
# Recipe integration
# ---------------------------------------------------------------------------


def test_recipe_with_only_flare_is_not_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["lens_flare"] = {"enabled": True, "intensity": 0.5}
    assert r.is_identity() is False


def test_recipe_disabled_flare_stays_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["lens_flare"] = {"enabled": False, "intensity": 0.5}
    assert r.is_identity() is True


# ---------------------------------------------------------------------------
# Dialog smoke
# ---------------------------------------------------------------------------


def test_dialog_loads_existing_recipe(qapp, tmp_path):
    from Imervue.gui.lens_flare_dialog import LensFlareDialog
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import recipe_store

    img = tmp_path / "x.png"
    img.write_bytes(b"x")
    recipe = Recipe()
    recipe.extra["lens_flare"] = {
        "enabled": True, "position": [0.25, 0.75],
        "intensity": 0.5, "size": 0.6,
        "colour": [100, 200, 50],
    }
    recipe_store.set_for_path(str(img), recipe)

    class FakeViewer:
        model = type("M", (), {"images": [str(img)]})()
        current_index = 0

    dlg = LensFlareDialog(FakeViewer(), str(img))
    assert dlg._enable.isChecked() is True
    assert dlg._x.value() == 25
    assert dlg._y.value() == 75
    assert dlg._colour == [100, 200, 50]
