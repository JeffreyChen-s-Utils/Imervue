"""Tests for the histogram engine + dock + workspace push."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.histogram import (
    HISTOGRAM_BINS,
    Histogram,
    compute_histogram,
    empty_histogram,
    merge_histograms,
    normalise,
)
from Imervue.paint.histogram_dock import HistogramDock
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _solid_canvas(rgb: tuple[int, int, int], h: int = 8, w: int = 8):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = rgb[0]
    arr[..., 1] = rgb[1]
    arr[..., 2] = rgb[2]
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# compute_histogram
# ---------------------------------------------------------------------------


def test_solid_white_canvas_hist_concentrates_at_255():
    arr = _solid_canvas((255, 255, 255), 4, 4)
    hist = compute_histogram(arr)
    assert int(hist.r[255]) == 16
    assert int(hist.r[:255].sum()) == 0
    assert int(hist.luma[255]) == 16


def test_solid_black_canvas_hist_concentrates_at_0():
    arr = _solid_canvas((0, 0, 0), 4, 4)
    hist = compute_histogram(arr)
    assert int(hist.r[0]) == 16
    assert int(hist.luma[0]) == 16


def test_per_channel_count_matches_pixel_count():
    arr = _solid_canvas((10, 20, 30), 5, 5)
    hist = compute_histogram(arr)
    # Total over all bins == pixel count.
    assert int(hist.r.sum()) == 25
    assert int(hist.g.sum()) == 25
    assert int(hist.b.sum()) == 25
    assert int(hist.luma.sum()) == 25


def test_red_channel_lands_in_correct_bin():
    arr = _solid_canvas((100, 50, 200), 2, 2)
    hist = compute_histogram(arr)
    assert int(hist.r[100]) == 4
    assert int(hist.g[50]) == 4
    assert int(hist.b[200]) == 4


def test_compute_histogram_rejects_non_rgba():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        compute_histogram(bad)


def test_compute_histogram_returns_int64_arrays():
    arr = _solid_canvas((50, 50, 50), 2, 2)
    hist = compute_histogram(arr)
    assert hist.r.dtype == np.int64
    assert hist.luma.dtype == np.int64


def test_compute_histogram_each_channel_has_256_bins():
    arr = _solid_canvas((50, 50, 50), 2, 2)
    hist = compute_histogram(arr)
    assert hist.r.shape == (HISTOGRAM_BINS,)
    assert hist.g.shape == (HISTOGRAM_BINS,)
    assert hist.b.shape == (HISTOGRAM_BINS,)
    assert hist.luma.shape == (HISTOGRAM_BINS,)


# ---------------------------------------------------------------------------
# Histogram.channel
# ---------------------------------------------------------------------------


def test_channel_lookup_returns_correct_array():
    arr = _solid_canvas((20, 40, 80), 1, 1)
    hist = compute_histogram(arr)
    assert int(hist.channel("r")[20]) == 1
    assert int(hist.channel("g")[40]) == 1
    assert int(hist.channel("b")[80]) == 1


def test_channel_unknown_raises():
    hist = empty_histogram()
    with pytest.raises(ValueError):
        hist.channel("alpha")


def test_channels_lists_documented_set():
    assert set(Histogram.channels()) == {"r", "g", "b", "luma"}


# ---------------------------------------------------------------------------
# empty_histogram + normalise + merge_histograms
# ---------------------------------------------------------------------------


def test_empty_histogram_all_zeros():
    hist = empty_histogram()
    assert int(hist.r.sum()) == 0
    assert int(hist.luma.sum()) == 0


def test_empty_histogram_does_not_alias_channels():
    """Each channel must be its own array — mutating one must not
    bleed into the others."""
    hist = empty_histogram()
    hist.r[0] = 99
    assert int(hist.g[0]) == 0
    assert int(hist.luma[0]) == 0


def test_normalise_returns_zero_to_one():
    arr = np.array([0, 5, 10, 5, 0], dtype=np.int64)
    out = normalise(arr)
    assert out.dtype == np.float32
    assert pytest.approx(out.max()) == pytest.approx(1.0)
    assert pytest.approx(out.min()) == pytest.approx(0.0)


def test_normalise_all_zero_returns_all_zero():
    arr = np.zeros(256, dtype=np.int64)
    out = normalise(arr)
    assert (out == 0).all()


def test_normalise_rejects_2d():
    with pytest.raises(ValueError):
        normalise(np.zeros((4, 4), dtype=np.int64))


def test_merge_histograms_sums_bins():
    a = compute_histogram(_solid_canvas((50, 50, 50), 1, 2))
    b = compute_histogram(_solid_canvas((100, 100, 100), 1, 2))
    merged = merge_histograms([a, b])
    assert int(merged.r[50]) == 2
    assert int(merged.r[100]) == 2


def test_merge_histograms_empty_iterable_returns_empty():
    merged = merge_histograms([])
    assert int(merged.r.sum()) == 0


# ---------------------------------------------------------------------------
# Dock smoke tests
# ---------------------------------------------------------------------------


def test_dock_starts_with_luma_channel(qapp):
    dock = HistogramDock()
    try:
        assert dock.channel() == "luma"
    finally:
        dock.deleteLater()


def test_dock_set_histogram_does_not_crash(qapp):
    dock = HistogramDock()
    try:
        arr = _solid_canvas((128, 64, 32))
        dock.set_histogram(compute_histogram(arr))
    finally:
        dock.deleteLater()


def test_dock_view_channel_change_flips_active(qapp):
    dock = HistogramDock()
    try:
        view = dock.view()
        view.set_channel("r")
        assert dock.channel() == "r"
        view.set_channel("not_a_channel")  # ignored
        assert dock.channel() == "r"
    finally:
        dock.deleteLater()


# ---------------------------------------------------------------------------
# Workspace push
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_workspace_attaches_histogram_dock(workspace):
    assert isinstance(workspace._histogram_dock, HistogramDock)  # noqa: SLF001


def test_workspace_pushes_histogram_via_navigator_refresh(workspace):
    """The same coalesce timer that updates the navigator also
    pushes the histogram — verify by manually calling the refresh."""
    layer = workspace.canvas().document().active_layer()
    layer.image[..., :3] = (200, 100, 50)
    workspace._refresh_navigator_preview()  # noqa: SLF001
    # The dock now holds a non-empty histogram for the painted layer.
    hist = workspace._histogram_dock._view._histogram   # noqa: SLF001
    assert int(hist.r.sum()) > 0


def test_workspace_window_menu_lists_histogram(workspace):
    actions = workspace._window_dock_actions  # noqa: SLF001
    assert "paint_dock_histogram" in actions
