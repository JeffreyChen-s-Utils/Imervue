"""Tests for the threshold / posterize module + recipe integration."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.posterize import (
    POSTERIZE_MAX_LEVELS,
    POSTERIZE_MIN_LEVELS,
    THRESHOLD_MAX,
    THRESHOLD_MIN,
    PosterizeOptions,
    ThresholdOptions,
    apply_posterize,
    apply_threshold,
)


# ---------------------------------------------------------------------------
# Option dataclass round-trip
# ---------------------------------------------------------------------------


def test_threshold_round_trip():
    opts = ThresholdOptions(enabled=True, level=80)
    restored = ThresholdOptions.from_dict(opts.to_dict())
    assert restored.enabled is True
    assert restored.level == 80


def test_posterize_round_trip():
    opts = PosterizeOptions(enabled=True, levels=8)
    restored = PosterizeOptions.from_dict(opts.to_dict())
    assert restored.enabled is True
    assert restored.levels == 8


def test_threshold_clamps_out_of_range():
    """Stored level outside 0..255 is clamped, not dropped."""
    too_low = ThresholdOptions.from_dict({"enabled": True, "level": -50})
    too_high = ThresholdOptions.from_dict({"enabled": True, "level": 9999})
    assert too_low.level == THRESHOLD_MIN
    assert too_high.level == THRESHOLD_MAX


def test_posterize_clamps_out_of_range():
    too_low = PosterizeOptions.from_dict({"enabled": True, "levels": 1})
    too_high = PosterizeOptions.from_dict({"enabled": True, "levels": 1000})
    assert too_low.levels == POSTERIZE_MIN_LEVELS
    assert too_high.levels == POSTERIZE_MAX_LEVELS


def test_dataclass_from_garbage_returns_default():
    assert ThresholdOptions.from_dict("not-a-dict").enabled is False
    assert PosterizeOptions.from_dict(None).enabled is False


# ---------------------------------------------------------------------------
# apply_threshold
# ---------------------------------------------------------------------------


def _solid(h: int, w: int, rgb: tuple[int, int, int]) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


def test_threshold_disabled_is_identity():
    base = _solid(4, 4, (100, 100, 100))
    out = apply_threshold(base, ThresholdOptions(enabled=False, level=128))
    assert np.array_equal(out, base)


def test_threshold_above_level_becomes_white():
    base = _solid(4, 4, (200, 200, 200))  # luma ≈ 200
    out = apply_threshold(base, ThresholdOptions(enabled=True, level=128))
    assert (out[..., :3] == 255).all()


def test_threshold_below_level_becomes_black():
    base = _solid(4, 4, (50, 50, 50))
    out = apply_threshold(base, ThresholdOptions(enabled=True, level=128))
    assert (out[..., :3] == 0).all()


def test_threshold_preserves_alpha():
    base = _solid(4, 4, (200, 200, 200))
    base[..., 3] = 64
    out = apply_threshold(base, ThresholdOptions(enabled=True, level=128))
    assert (out[..., 3] == 64).all()


def test_threshold_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_threshold(arr, ThresholdOptions(enabled=True))


# ---------------------------------------------------------------------------
# apply_posterize
# ---------------------------------------------------------------------------


def test_posterize_disabled_is_identity():
    base = _solid(4, 4, (123, 211, 78))
    out = apply_posterize(base, PosterizeOptions(enabled=False, levels=4))
    assert np.array_equal(out, base)


def test_posterize_2_levels_is_2_distinct_values_per_channel():
    """At 2 levels, every channel value must collapse to either 0 or 255."""
    base = np.zeros((1, 256, 4), dtype=np.uint8)
    base[..., 0] = np.arange(256, dtype=np.uint8)
    base[..., 1] = np.arange(256, dtype=np.uint8)
    base[..., 2] = np.arange(256, dtype=np.uint8)
    base[..., 3] = 255
    out = apply_posterize(base, PosterizeOptions(enabled=True, levels=2))
    unique = set(np.unique(out[..., :3]).tolist())
    assert unique <= {0, 255}


def test_posterize_levels_count_distinct_values():
    """4 levels → at most 4 distinct values per channel."""
    base = np.zeros((1, 256, 4), dtype=np.uint8)
    base[..., 0] = np.arange(256, dtype=np.uint8)
    base[..., 3] = 255
    out = apply_posterize(base, PosterizeOptions(enabled=True, levels=4))
    distinct = len(set(np.unique(out[..., 0]).tolist()))
    assert distinct <= 4


def test_posterize_preserves_alpha():
    base = _solid(4, 4, (200, 100, 50))
    base[..., 3] = 64
    out = apply_posterize(base, PosterizeOptions(enabled=True, levels=4))
    assert (out[..., 3] == 64).all()


def test_posterize_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_posterize(arr, PosterizeOptions(enabled=True))


# ---------------------------------------------------------------------------
# Recipe integration
# ---------------------------------------------------------------------------


def test_recipe_with_only_threshold_is_not_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    assert r.is_identity() is True
    r.extra["threshold"] = {"enabled": True, "level": 128}
    assert r.is_identity() is False


def test_recipe_with_disabled_threshold_stays_identity():
    """A stored entry with enabled=False must NOT break identity."""
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["threshold"] = {"enabled": False, "level": 128}
    r.extra["posterize"] = {"enabled": False, "levels": 4}
    assert r.is_identity() is True


def test_recipe_apply_runs_threshold():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["threshold"] = {"enabled": True, "level": 128}
    base = _solid(4, 4, (200, 200, 200))
    out = r.apply(base)
    assert (out[..., :3] == 255).all()


def test_recipe_apply_runs_posterize():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["posterize"] = {"enabled": True, "levels": 2}
    base = np.zeros((1, 256, 4), dtype=np.uint8)
    base[..., 0] = np.arange(256, dtype=np.uint8)
    base[..., 3] = 255
    out = r.apply(base)
    unique = set(np.unique(out[..., 0]).tolist())
    assert unique <= {0, 255}


# ---------------------------------------------------------------------------
# Dialog smoke
# ---------------------------------------------------------------------------


def test_dialog_loads_existing_recipe(qapp, tmp_path):
    from Imervue.gui.posterize_dialog import PosterizeDialog
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import recipe_store

    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")  # not real, just a path placeholder
    recipe = Recipe()
    recipe.extra["threshold"] = {"enabled": True, "level": 60}
    recipe.extra["posterize"] = {"enabled": True, "levels": 8}
    recipe_store.set_for_path(str(img), recipe)

    class FakeViewer:
        def __init__(self):
            self.model = type("M", (), {"images": [str(img)]})()
            self.current_index = 0

    dlg = PosterizeDialog(FakeViewer(), str(img))
    assert dlg._threshold_check.isChecked() is True
    assert dlg._threshold_slider.value() == 60
    assert dlg._posterize_check.isChecked() is True
    assert dlg._posterize_slider.value() == 8
