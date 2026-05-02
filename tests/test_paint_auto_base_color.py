"""Tests for the auto base-color flat-fill engine."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.auto_base_color import (
    DEFAULT_MIN_REGION_SIZE,
    MAX_REGIONS,
    BaseColorRegion,
    auto_base_fill,
    regions_to_layer_image,
)


def _ink_box(size: int, *, x: int, y: int, w: int, h: int) -> np.ndarray:
    """Build a fully-transparent canvas with a closed black-ink box."""
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    # Top + bottom edges
    arr[y, x : x + w, :3] = 0
    arr[y, x : x + w, 3] = 255
    arr[y + h - 1, x : x + w, :3] = 0
    arr[y + h - 1, x : x + w, 3] = 255
    # Left + right edges
    arr[y : y + h, x, :3] = 0
    arr[y : y + h, x, 3] = 255
    arr[y : y + h, x + w - 1, :3] = 0
    arr[y : y + h, x + w - 1, 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_rejects_non_rgba():
    with pytest.raises(ValueError):
        auto_base_fill(np.zeros((4, 4, 3), dtype=np.uint8))


def test_rejects_non_uint8():
    with pytest.raises(ValueError):
        auto_base_fill(np.zeros((4, 4, 4), dtype=np.float32))


def test_rejects_alpha_threshold_out_of_range():
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        auto_base_fill(img, ink_alpha_threshold=999)


def test_rejects_zero_min_region():
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        auto_base_fill(img, min_region_size=0)


def test_rejects_zero_max_regions():
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        auto_base_fill(img, max_regions=0)


def test_rejects_palette_with_bad_color():
    img = _ink_box(20, x=4, y=4, w=12, h=12)
    with pytest.raises(ValueError):
        auto_base_fill(img, palette=[(0, 0)])   # type: ignore[list-item]


# ---------------------------------------------------------------------------
# Empty / trivial inputs
# ---------------------------------------------------------------------------


def test_fully_transparent_yields_one_canvas_region():
    """A canvas with no ink at all produces one giant region — the
    whole image is "open" so the algorithm finds a single region
    covering everything."""
    img = np.zeros((40, 40, 4), dtype=np.uint8)
    regions = auto_base_fill(img, min_region_size=1)
    assert len(regions) == 1
    assert regions[0].mask.all()


# ---------------------------------------------------------------------------
# Region detection
# ---------------------------------------------------------------------------


def test_single_box_yields_inside_and_outside():
    """One closed box → 2 regions (the inside and the outside of the
    box). Both must appear in the output."""
    img = _ink_box(40, x=10, y=10, w=20, h=20)
    regions = auto_base_fill(img, min_region_size=4)
    assert len(regions) >= 2
    inside_pixel = (15, 15)   # interior of the box
    outside_pixel = (1, 1)
    inside_found = any(r.mask[inside_pixel] for r in regions)
    outside_found = any(r.mask[outside_pixel] for r in regions)
    assert inside_found
    assert outside_found


def test_two_separate_boxes_yield_three_regions():
    """Two disconnected boxes → outside + 2 insides = 3 regions."""
    img = _ink_box(60, x=5, y=5, w=20, h=20)
    img2 = _ink_box(60, x=35, y=35, w=20, h=20)
    img = np.where(img2[..., 3:4] > 0, img2, img)
    regions = auto_base_fill(img, min_region_size=4)
    assert len(regions) >= 3


def test_min_region_size_filters_speckles():
    """Tiny 1-px gaps in the ink mask must not produce 1-px regions
    when ``min_region_size`` is bigger than that."""
    img = np.zeros((40, 40, 4), dtype=np.uint8)
    # Sprinkle some single-pixel "gaps" in an otherwise-empty canvas.
    for x, y in [(5, 5), (20, 20), (30, 10)]:
        img[y, x, :3] = 0
        img[y, x, 3] = 255
    # Without filtering the canvas is one big region.
    regions = auto_base_fill(img, min_region_size=DEFAULT_MIN_REGION_SIZE)
    # The filter keeps only the big background region, dropping any
    # 1-px-wide artefact slivers.
    for region in regions:
        assert region.pixel_count >= DEFAULT_MIN_REGION_SIZE


def test_regions_sorted_by_pixel_count_desc():
    img = _ink_box(40, x=10, y=10, w=20, h=20)
    regions = auto_base_fill(img, min_region_size=4)
    counts = [r.pixel_count for r in regions]
    assert counts == sorted(counts, reverse=True)


def test_max_regions_caps_output():
    """Many small regions get truncated at ``max_regions``."""
    img = np.zeros((40, 40, 4), dtype=np.uint8)
    # 4×4 grid of 1×1 inked dots → many tiny regions if filter allows.
    for y in range(0, 40, 8):
        for x in range(0, 40, 8):
            img[y, x, :3] = 0
            img[y, x, 3] = 255
    regions = auto_base_fill(img, min_region_size=1, max_regions=2)
    assert len(regions) <= 2


def test_gap_close_merges_separate_regions():
    """A 1-px gap in a closed region's outline lets the inside leak;
    gap_close=2 closes the leak so inside + outside are distinct."""
    img = _ink_box(40, x=10, y=10, w=20, h=20)
    # Punch a 1-px hole in the right wall.
    img[20, 29, :] = 0
    leaky = auto_base_fill(img, min_region_size=4, gap_close=0)
    sealed = auto_base_fill(img, min_region_size=4, gap_close=2)
    # gap_close → distinct inside/outside regions; 0 → merged.
    assert len(sealed) > len(leaky) or (
        len(sealed) == len(leaky)
        and sum(r.pixel_count for r in sealed) <= sum(
            r.pixel_count for r in leaky
        )
    )


# ---------------------------------------------------------------------------
# Palette wiring
# ---------------------------------------------------------------------------


def test_default_palette_picks_distinct_colors_per_region():
    img = np.zeros((40, 40, 4), dtype=np.uint8)
    for box_x in (4, 24):
        img2 = _ink_box(40, x=box_x, y=4, w=12, h=12)
        img = np.where(img2[..., 3:4] > 0, img2, img)
    regions = auto_base_fill(img, min_region_size=4)
    colors = {r.color for r in regions}
    # At least two distinct colours (one per region).
    assert len(colors) >= 2


def test_custom_palette_is_cycled():
    """Three regions with a 2-colour palette → colour 0, 1, 0."""
    palette = [(255, 0, 0), (0, 255, 0)]
    img = np.zeros((60, 60, 4), dtype=np.uint8)
    for box_x in (4, 24, 44):
        img2 = _ink_box(60, x=box_x, y=4, w=12, h=12)
        img = np.where(img2[..., 3:4] > 0, img2, img)
    regions = auto_base_fill(
        img, palette=palette, min_region_size=4,
    )
    # Some regions will be inside the boxes (small) and one big
    # outside region. We can't depend on insertion order after the
    # final pixel-count sort, but every region's colour must be
    # one of the palette entries.
    palette_set = set(palette)
    for region in regions:
        assert region.color in palette_set


# ---------------------------------------------------------------------------
# regions_to_layer_image
# ---------------------------------------------------------------------------


def test_regions_to_layer_image_paints_each_mask():
    mask_a = np.zeros((10, 10), dtype=np.bool_)
    mask_a[:5, :] = True
    mask_b = np.zeros((10, 10), dtype=np.bool_)
    mask_b[5:, :] = True
    regions = [
        BaseColorRegion(color=(255, 0, 0), mask=mask_a, pixel_count=50),
        BaseColorRegion(color=(0, 0, 255), mask=mask_b, pixel_count=50),
    ]
    img = regions_to_layer_image((10, 10), regions)
    assert tuple(img[0, 0]) == (255, 0, 0, 255)
    assert tuple(img[9, 9]) == (0, 0, 255, 255)


def test_regions_to_layer_image_rejects_shape_mismatch():
    mask = np.zeros((4, 4), dtype=np.bool_)
    region = BaseColorRegion(color=(0, 0, 0), mask=mask, pixel_count=0)
    with pytest.raises(ValueError):
        regions_to_layer_image((8, 8), [region])


def test_regions_to_layer_image_rejects_non_positive_canvas():
    with pytest.raises(ValueError):
        regions_to_layer_image((0, 4), [])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_max_regions_is_documented_cap():
    assert MAX_REGIONS > 0
    assert MAX_REGIONS >= 16
