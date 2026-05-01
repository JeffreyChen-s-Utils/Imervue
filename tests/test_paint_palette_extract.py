"""Tests for the median-cut palette extractor."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.palette_extract import (
    DEFAULT_PALETTE_SIZE,
    PALETTE_MAX,
    PALETTE_MIN,
    PaletteEntry,
    extract_palette,
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_rejects_non_rgba():
    with pytest.raises(ValueError):
        extract_palette(np.zeros((4, 4, 3), dtype=np.uint8))


def test_rejects_non_uint8():
    with pytest.raises(ValueError):
        extract_palette(np.zeros((4, 4, 4), dtype=np.float32))


def test_rejects_n_colors_below_min():
    img = np.full((4, 4, 4), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        extract_palette(img, n_colors=PALETTE_MIN - 1)


def test_rejects_n_colors_above_max():
    img = np.full((4, 4, 4), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        extract_palette(img, n_colors=PALETTE_MAX + 1)


def test_rejects_alpha_threshold_out_of_range():
    img = np.full((4, 4, 4), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        extract_palette(img, alpha_threshold=999)


# ---------------------------------------------------------------------------
# Empty / trivial inputs
# ---------------------------------------------------------------------------


def test_fully_transparent_image_returns_empty():
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    assert extract_palette(img) == []


def test_single_flat_colour_collapses_to_one_entry():
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[..., :3] = (200, 100, 50)
    img[..., 3] = 255
    palette = extract_palette(img, n_colors=4)
    assert len(palette) == 1
    assert palette[0].color == (200, 100, 50)
    assert palette[0].pixel_count == 16


# ---------------------------------------------------------------------------
# Multi-colour inputs
# ---------------------------------------------------------------------------


def test_two_colour_image_yields_two_entries():
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[:, :2, :3] = (255, 0, 0)
    img[:, 2:, :3] = (0, 0, 255)
    palette = extract_palette(img, n_colors=2)
    assert len(palette) == 2
    colors = {e.color for e in palette}
    assert colors == {(255, 0, 0), (0, 0, 255)}


def test_palette_sorted_by_pixel_count_non_increasing():
    """Output ordering is by pixel count descending — this guards
    the sort step in :func:`extract_palette`. Median cut tries to
    produce equal-sized buckets, so the assertion is non-strict; the
    important property is that no later entry has *more* pixels
    than an earlier one."""
    img = np.zeros((6, 6, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[:, :4, :3] = (200, 0, 0)
    img[:, 4:, :3] = (0, 200, 0)
    palette = extract_palette(img, n_colors=2)
    assert palette[0].pixel_count >= palette[1].pixel_count


def test_palette_returns_at_most_n_colors():
    """Even on a high-variety canvas, the palette caps at ``n_colors``."""
    rng = np.random.default_rng(seed=42)
    img = rng.integers(0, 256, (32, 32, 4), dtype=np.uint8)
    img[..., 3] = 255
    palette = extract_palette(img, n_colors=4)
    assert len(palette) <= 4


def test_palette_handles_translucent_pixels_via_threshold():
    """Pixels below the alpha threshold are skipped — only opaque
    paint contributes to the extracted palette."""
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[:2, :, :3] = (255, 0, 0)
    img[:2, :, 3] = 255
    img[2:, :, :3] = (0, 255, 0)
    img[2:, :, 3] = 16   # below default threshold 32 → ignored
    palette = extract_palette(img, n_colors=4)
    assert len(palette) == 1
    assert palette[0].color == (255, 0, 0)


def test_palette_entry_dataclass_fields():
    entry = PaletteEntry(color=(10, 20, 30), pixel_count=99)
    assert entry.color == (10, 20, 30)
    assert entry.pixel_count == 99


# ---------------------------------------------------------------------------
# Median-cut behavioural checks
# ---------------------------------------------------------------------------


def test_median_cut_separates_distant_clusters():
    """Two well-separated clusters in colour space land in distinct
    palette entries — guards against a regression where the
    longest-axis selector picks a degenerate axis."""
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[:2, :, :3] = (10, 10, 10)
    img[2:, :, :3] = (240, 240, 240)
    palette = extract_palette(img, n_colors=2)
    assert len(palette) == 2
    # One entry is dark, the other is light.
    luminance = sorted(sum(e.color) for e in palette)
    assert luminance[0] < 100
    assert luminance[1] > 600


def test_default_palette_size_is_within_bounds():
    assert PALETTE_MIN <= DEFAULT_PALETTE_SIZE <= PALETTE_MAX


# ---------------------------------------------------------------------------
# inject_palette_into_state — bridge into ToolState.color_history
# ---------------------------------------------------------------------------


def test_inject_replaces_color_history():
    from Imervue.paint import tool_state as ts
    from Imervue.paint.palette_extract import inject_palette_into_state
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    try:
        state = ts.load_tool_state()
        state.color_history.extend([(1, 1, 1), (2, 2, 2)])
        palette = [
            PaletteEntry(color=(255, 0, 0), pixel_count=10),
            PaletteEntry(color=(0, 0, 255), pixel_count=5),
        ]
        injected = inject_palette_into_state(state, palette)
        assert injected == 2
        assert state.color_history == [(255, 0, 0), (0, 0, 255)]
    finally:
        user_setting_dict.pop("paint_state", None)
        ts.reset_tool_state()


def test_inject_caps_at_history_max():
    from Imervue.paint import tool_state as ts
    from Imervue.paint.palette_extract import inject_palette_into_state
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    try:
        state = ts.load_tool_state()
        oversized = [
            PaletteEntry(color=(i, i, i), pixel_count=1)
            for i in range(ts.COLOR_HISTORY_MAX + 5)
        ]
        injected = inject_palette_into_state(state, oversized)
        assert injected == ts.COLOR_HISTORY_MAX
        assert len(state.color_history) == ts.COLOR_HISTORY_MAX
    finally:
        user_setting_dict.pop("paint_state", None)
        ts.reset_tool_state()


def test_inject_emits_history_channel():
    from Imervue.paint import tool_state as ts
    from Imervue.paint.palette_extract import inject_palette_into_state
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    try:
        state = ts.load_tool_state()
        seen: list[str] = []
        state.subscribe(seen.append)
        palette = [PaletteEntry(color=(10, 20, 30), pixel_count=1)]
        inject_palette_into_state(state, palette)
        assert ts.EVENT_HISTORY in seen
    finally:
        user_setting_dict.pop("paint_state", None)
        ts.reset_tool_state()
