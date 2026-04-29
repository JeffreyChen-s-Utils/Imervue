"""Tests for the procedural film-grain effect."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.film_grain import (
    INTENSITY_MAX,
    SIZE_MAX,
    SIZE_MIN,
    FilmGrainOptions,
    apply_film_grain,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Options round-trip
# ---------------------------------------------------------------------------


def test_round_trip_via_dict():
    opts = FilmGrainOptions(enabled=True, intensity=0.4, size=3,
                            monochrome=False, seed=42)
    restored = FilmGrainOptions.from_dict(opts.to_dict())
    assert restored.enabled is True
    assert restored.intensity == pytest.approx(0.4)
    assert restored.size == 3
    assert restored.monochrome is False
    assert restored.seed == 42


def test_size_clamped_to_safe_range():
    too_low = FilmGrainOptions.from_dict({"enabled": True, "size": 0})
    too_high = FilmGrainOptions.from_dict({"enabled": True, "size": 99})
    assert too_low.size == SIZE_MIN
    assert too_high.size == SIZE_MAX


def test_intensity_clamped():
    too_high = FilmGrainOptions.from_dict({"enabled": True, "intensity": 9})
    assert too_high.intensity == pytest.approx(INTENSITY_MAX)


def test_garbage_returns_default():
    assert FilmGrainOptions.from_dict("oops").enabled is False
    assert FilmGrainOptions.from_dict(None).intensity == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# apply_film_grain behaviour
# ---------------------------------------------------------------------------


def test_disabled_is_identity():
    base = _solid(8, 8, (100, 100, 100))
    out = apply_film_grain(base, FilmGrainOptions(enabled=False))
    assert np.array_equal(out, base)


def test_zero_intensity_is_identity():
    base = _solid(8, 8, (100, 100, 100))
    opts = FilmGrainOptions(enabled=True, intensity=0.0)
    out = apply_film_grain(base, opts)
    assert np.array_equal(out, base)


def test_grain_modifies_pixels():
    base = _solid(64, 64, (128, 128, 128))
    opts = FilmGrainOptions(enabled=True, intensity=0.5, seed=1)
    out = apply_film_grain(base, opts)
    assert not np.array_equal(out, base)


def test_grain_is_deterministic_with_seed():
    """Same seed → same noise. Critical for reproducible re-exports."""
    base = _solid(64, 64, (128, 128, 128))
    opts = FilmGrainOptions(enabled=True, intensity=0.5, seed=99)
    a = apply_film_grain(base, opts)
    b = apply_film_grain(base, opts)
    assert np.array_equal(a, b)


def test_grain_differs_between_seeds():
    base = _solid(64, 64, (128, 128, 128))
    a = apply_film_grain(base, FilmGrainOptions(enabled=True, intensity=0.5, seed=1))
    b = apply_film_grain(base, FilmGrainOptions(enabled=True, intensity=0.5, seed=2))
    assert not np.array_equal(a, b)


def test_grain_auto_seed_is_size_dependent():
    """Different image sizes get different grain even when seed=0 (auto)."""
    big = _solid(64, 64, (128, 128, 128))
    small = _solid(32, 32, (128, 128, 128))
    opts = FilmGrainOptions(enabled=True, intensity=0.5, seed=0)
    out_big = apply_film_grain(big, opts)
    out_small = apply_film_grain(small, opts)
    # Different shapes obviously can't be array_equal — just verify both
    # actually had grain applied
    assert not np.array_equal(out_big, big)
    assert not np.array_equal(out_small, small)


def test_monochrome_grain_is_identical_per_channel():
    """Monochrome mode: R, G, B deltas must all match."""
    base = _solid(32, 32, (128, 128, 128))
    opts = FilmGrainOptions(enabled=True, intensity=0.5, seed=7,
                            monochrome=True)
    out = apply_film_grain(base, opts).astype(np.int16)
    delta = out[..., :3] - 128
    assert np.array_equal(delta[..., 0], delta[..., 1])
    assert np.array_equal(delta[..., 1], delta[..., 2])


def test_colour_grain_differs_per_channel():
    base = _solid(64, 64, (128, 128, 128))
    opts = FilmGrainOptions(enabled=True, intensity=0.7, seed=7,
                            monochrome=False)
    out = apply_film_grain(base, opts)
    # R and G channels should not be identical
    assert not np.array_equal(out[..., 0], out[..., 1])


def test_alpha_preserved():
    base = _solid(8, 8, (100, 100, 100))
    base[..., 3] = 80
    opts = FilmGrainOptions(enabled=True, intensity=0.5)
    out = apply_film_grain(base, opts)
    assert (out[..., 3] == 80).all()


def test_clip_to_uint8_range():
    base = _solid(32, 32, (255, 255, 255))
    opts = FilmGrainOptions(enabled=True, intensity=1.0, seed=11)
    out = apply_film_grain(base, opts)
    # No overflow allowed
    assert out.max() <= 255
    assert out.min() >= 0


def test_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_film_grain(arr, FilmGrainOptions(enabled=True))


# ---------------------------------------------------------------------------
# Recipe integration
# ---------------------------------------------------------------------------


def test_recipe_with_only_grain_is_not_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["film_grain"] = {"enabled": True, "intensity": 0.5}
    assert r.is_identity() is False


def test_recipe_disabled_grain_stays_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["film_grain"] = {"enabled": False, "intensity": 0.5}
    assert r.is_identity() is True


# ---------------------------------------------------------------------------
# Dialog smoke
# ---------------------------------------------------------------------------


def test_dialog_loads_existing_recipe(qapp, tmp_path):
    from Imervue.gui.film_grain_dialog import FilmGrainDialog
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import recipe_store

    img = tmp_path / "x.png"
    img.write_bytes(b"x")
    recipe = Recipe()
    recipe.extra["film_grain"] = {
        "enabled": True, "intensity": 0.4, "size": 2,
        "monochrome": False, "seed": 42,
    }
    recipe_store.set_for_path(str(img), recipe)

    class FakeViewer:
        model = type("M", (), {"images": [str(img)]})()
        current_index = 0

    dlg = FilmGrainDialog(FakeViewer(), str(img))
    assert dlg._enable.isChecked() is True
    assert dlg._intensity.value() == 40
    assert dlg._size.value() == 2
    assert dlg._monochrome.isChecked() is False
    assert dlg._seed.value() == 42
