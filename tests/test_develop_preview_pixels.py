"""CPU preview fidelity, geometry, ownership and cooperative cancellation."""
from __future__ import annotations

from threading import Event
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from Imervue.image.develop_preview import (
    PREVIEW_MAX_PIXELS, PreviewCache, PreviewCancelledError, PreviewRequest, render_preview,
)
from Imervue.image.recipe import Recipe


def _request(source, recipe=None):
    return PreviewRequest(1, "source.png", source, recipe or Recipe(), Event())


@pytest.mark.parametrize("rotation", range(4))
@pytest.mark.parametrize("flip_h,flip_v", [(False, False), (True, False), (False, True)])
def test_full_render_matches_export_pipeline(rotation, flip_h, flip_v):
    array = np.random.default_rng(19).integers(0, 256, (31, 48, 4), dtype=np.uint8)
    source = Image.fromarray(array)
    recipe = Recipe(rotate_steps=rotation, flip_h=flip_h, flip_v=flip_v,
                    crop=(3, 5, 20, 15), exposure=.2, temperature=.1, shadows=.2,
                    vibrance=.1, tone_curve_r=[(0, 0), (.5, .6), (1, 1)])
    result = render_preview(_request(source, recipe), PreviewCache(), full=True)
    np.testing.assert_array_equal(np.array(result.image), recipe.apply(array))
    np.testing.assert_array_equal(np.array(source), array)
    assert result.full_quality
    assert result.geometry_base is result.image


@pytest.mark.parametrize("crop", [(0, 0, 0, 5), (9999, 0, 50, 50), (-100, -100, 900, 700)])
def test_reduced_geometry_matches_clipped_or_invalid_crop(crop):
    source = Image.new("RGBA", (1800, 1400), (11, 23, 37, 127))
    recipe = Recipe(rotate_steps=1, flip_h=True, crop=crop, brightness=.2)
    result = render_preview(_request(source, recipe), PreviewCache(), full=False)
    expected = recipe.apply(np.array(source))
    assert result.geometry_base.size == (expected.shape[1], expected.shape[0])
    assert result.image.width * result.image.height <= PREVIEW_MAX_PIXELS
    assert not result.full_quality
    assert np.all(np.array(result.image)[..., 3] == 127)


def test_small_source_is_full_even_for_drag_request():
    source = Image.new("RGBA", (32, 19), (15, 25, 35, 45))
    recipe = Recipe(exposure=.5)
    result = render_preview(_request(source, recipe), PreviewCache(), full=False)
    assert result.full_quality
    np.testing.assert_array_equal(np.array(result.image), recipe.apply(np.array(source)))


def test_geometry_thumbnail_reused_but_color_and_source_changes_are_not():
    source = Image.new("RGBA", (1800, 1400), (11, 23, 37, 255))
    cache = PreviewCache()
    first = render_preview(_request(source, Recipe(exposure=.2)), cache, full=False)
    entry = cache.entry
    second = render_preview(_request(source, Recipe(exposure=.5)), cache, full=False)
    assert cache.entry is entry
    assert first.geometry_base is second.geometry_base
    assert not np.array_equal(np.array(first.image), np.array(second.image))
    render_preview(_request(source, Recipe(rotate_steps=1)), cache, full=False)
    assert cache.entry is not entry
    other = Image.new("RGBA", source.size, (47, 63, 79, 255))
    render_preview(_request(other), cache, full=False)
    assert cache.entry.source is other
    cache.clear()
    assert cache.entry is None


def test_cancel_before_work_avoids_large_allocations():
    request = _request(Image.new("RGBA", (1800, 1400)), Recipe(rotate_steps=1))
    request.cancelled.set()
    with patch.object(Image.Image, "transpose", side_effect=AssertionError("must not allocate")), \
            pytest.raises(PreviewCancelledError):
        render_preview(request, PreviewCache(), full=False)


def test_cancel_between_stages_stops_obsolete_recipe(monkeypatch):
    request = _request(Image.new("RGBA", (48, 31)), Recipe(exposure=.2, temperature=.1))
    stages = []
    original = Recipe.apply_stages

    def stage(recipe, array, first=None, last=None):
        stages.append(first)
        output = original(recipe, array, first, last)
        request.cancelled.set()
        return output

    monkeypatch.setattr(Recipe, "apply_stages", stage)
    with pytest.raises(PreviewCancelledError):
        render_preview(request, PreviewCache(), full=True)
    assert stages == ["geometry"]


def test_preview_scales_mask_coordinates_without_changing_saved_recipe():
    source = Image.new("RGBA", (1600, 1600), (45, 63, 79, 255))
    recipe = Recipe(extra={"masks": [{"kind": "brush", "params": {
        "points": [{"x": 800., "y": 400., "r": 80.}]}, "adjustments": {"exposure": .5}}]})
    before = recipe.to_dict()
    seen = []
    original = Recipe.apply_stages

    def inspect(current, array, first=None, last=None):
        if first == "masks":
            seen.append(current.extra["masks"][0]["params"]["points"][0].copy())
        return original(current, array, first, last)

    with patch.object(Recipe, "apply_stages", inspect):
        result = render_preview(_request(source, recipe), PreviewCache(), full=False)
    assert result.image.size == (800, 800)
    assert seen == [{"x": 400., "y": 200., "r": 40.}]
    assert recipe.to_dict() == before
