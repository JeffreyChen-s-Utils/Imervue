"""Tests for frequency separation."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.image.frequency_separation import (
    NEUTRAL_GREY,
    RADIUS_MAX,
    RADIUS_MIN,
    FrequencySeparationResult,
    recombine_frequencies,
    separate_frequencies,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


def _gradient(h, w):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = np.linspace(0, 255, w, dtype=np.uint8)
    arr[..., 1] = arr[..., 0]
    arr[..., 2] = arr[..., 0]
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Pure pipeline behaviour
# ---------------------------------------------------------------------------


def test_separate_returns_two_uint8_layers():
    base = _solid(16, 16, (100, 100, 100))
    result = separate_frequencies(base, radius=4)
    assert isinstance(result, FrequencySeparationResult)
    assert result.low_frequency.shape == base.shape
    assert result.high_frequency.shape == base.shape
    assert result.low_frequency.dtype == np.uint8
    assert result.high_frequency.dtype == np.uint8


def test_separate_solid_input_high_layer_is_neutral_grey():
    """A flat-colour input has no detail — high freq should be all 128."""
    base = _solid(16, 16, (123, 45, 67))
    result = separate_frequencies(base, radius=8)
    assert (result.high_frequency[..., :3] == NEUTRAL_GREY).all()


def test_separate_solid_input_low_layer_matches_input():
    base = _solid(16, 16, (123, 45, 67))
    result = separate_frequencies(base, radius=8)
    # Low-freq blur of a flat colour = the same colour (within ±1 from rounding)
    diff = np.abs(result.low_frequency[..., :3].astype(np.int16)
                  - base[..., :3].astype(np.int16))
    assert int(diff.max()) <= 1


def test_recombine_round_trip_is_close_to_original():
    base = _gradient(64, 64)
    result = separate_frequencies(base, radius=4)
    recovered = recombine_frequencies(
        result.low_frequency, result.high_frequency,
    )
    diff = np.abs(recovered[..., :3].astype(np.int16)
                  - base[..., :3].astype(np.int16))
    # Slight loss is unavoidable from clipping/rounding, but should be small
    assert int(diff.max()) <= 2


def test_separate_radius_clamped():
    base = _solid(16, 16, (100, 100, 100))
    # Radius below RADIUS_MIN is clamped — no exception, no crash
    result = separate_frequencies(base, radius=0)
    assert result.high_frequency.shape == base.shape
    result = separate_frequencies(base, radius=999)
    assert result.high_frequency.shape == base.shape


def test_separate_alpha_preserved():
    base = _solid(8, 8, (100, 100, 100))
    base[..., 3] = 80
    result = separate_frequencies(base, radius=4)
    assert (result.low_frequency[..., 3] == 80).all()
    assert (result.high_frequency[..., 3] == 80).all()


def test_separate_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        separate_frequencies(arr, radius=4)


def test_recombine_rejects_mismatched_shapes():
    a = _solid(4, 4, (100, 100, 100))
    b = _solid(8, 8, (100, 100, 100))
    with pytest.raises(ValueError):
        recombine_frequencies(a, b)


def test_radius_constants_are_sane():
    assert RADIUS_MIN >= 1
    assert RADIUS_MAX <= 256
    assert RADIUS_MIN < RADIUS_MAX


# ---------------------------------------------------------------------------
# Dialog smoke (writes to disk)
# ---------------------------------------------------------------------------


def test_dialog_writes_two_layer_files(qapp, tmp_path):
    from Imervue.gui.frequency_separation_dialog import FrequencySeparationDialog

    # Create a real image on disk
    src = tmp_path / "subject.png"
    arr = _gradient(32, 32)
    Image.fromarray(arr, mode="RGBA").save(str(src))

    class FakeViewer:
        model = type("M", (), {"images": [str(src)]})()
        current_index = 0
        main_window = None

    dlg = FrequencySeparationDialog(FakeViewer(), str(src))
    dlg._radius.setValue(4)
    dlg._commit()

    assert (tmp_path / "subject_low.png").exists()
    assert (tmp_path / "subject_high.png").exists()


def test_dialog_handles_missing_file(qapp, tmp_path):
    """Pointing at a path that doesn't exist should fail cleanly."""
    from Imervue.gui.frequency_separation_dialog import FrequencySeparationDialog

    bogus = tmp_path / "does_not_exist.png"

    class FakeViewer:
        model = type("M", (), {"images": [str(bogus)]})()
        current_index = 0
        main_window = None

    dlg = FrequencySeparationDialog(FakeViewer(), str(bogus))
    # Should not raise — _commit catches OSError and notifies via toast
    dlg._commit()
