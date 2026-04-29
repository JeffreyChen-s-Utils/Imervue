"""Tests for the channel-mixer effect."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.channel_mixer import (
    OFFSET_MAX,
    OFFSET_MIN,
    WEIGHT_MAX,
    WEIGHT_MIN,
    ChannelMixerOptions,
    apply_channel_mixer,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Options round-trip
# ---------------------------------------------------------------------------


def test_default_options_are_identity_matrix():
    opts = ChannelMixerOptions()
    # red: [1,0,0], green: [0,1,0], blue: [0,0,1], offsets: [0,0,0]
    assert opts.red == [1.0, 0.0, 0.0]
    assert opts.green == [0.0, 1.0, 0.0]
    assert opts.blue == [0.0, 0.0, 1.0]
    assert opts.offsets == [0.0, 0.0, 0.0]


def test_round_trip_via_dict():
    opts = ChannelMixerOptions(
        enabled=True, red=[0.3, 0.5, 0.2],
        green=[0.4, 0.4, 0.2], blue=[0.3, 0.3, 0.4],
        offsets=[0.1, -0.1, 0.0], monochrome=True,
    )
    restored = ChannelMixerOptions.from_dict(opts.to_dict())
    assert restored.enabled is True
    assert restored.monochrome is True
    assert restored.red == pytest.approx([0.3, 0.5, 0.2])
    assert restored.offsets == pytest.approx([0.1, -0.1, 0.0])


def test_clamp_weights_out_of_range():
    out = ChannelMixerOptions.from_dict({
        "enabled": True,
        "red": [99, -99, 0.5],
    })
    assert out.red[0] == pytest.approx(WEIGHT_MAX)
    assert out.red[1] == pytest.approx(WEIGHT_MIN)
    assert out.red[2] == pytest.approx(0.5)


def test_clamp_offsets_out_of_range():
    out = ChannelMixerOptions.from_dict({
        "enabled": True,
        "offsets": [99, -99, 0.5],
    })
    assert out.offsets[0] == pytest.approx(OFFSET_MAX)
    assert out.offsets[1] == pytest.approx(OFFSET_MIN)


def test_garbage_returns_default():
    assert ChannelMixerOptions.from_dict("oops").enabled is False
    assert ChannelMixerOptions.from_dict({"red": "not a list"}).red == [1.0, 0.0, 0.0]


def test_short_row_falls_back_to_default():
    """3-element rows are required — anything else uses the default."""
    out = ChannelMixerOptions.from_dict({"enabled": True, "red": [0.5, 0.5]})
    assert out.red == [1.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# apply_channel_mixer behaviour
# ---------------------------------------------------------------------------


def test_disabled_is_identity():
    base = _solid(4, 4, (100, 50, 200))
    out = apply_channel_mixer(base, ChannelMixerOptions(enabled=False))
    assert np.array_equal(out, base)


def test_default_matrix_is_identity():
    base = _solid(4, 4, (100, 50, 200))
    out = apply_channel_mixer(base, ChannelMixerOptions(enabled=True))
    assert np.array_equal(out, base)


def test_swap_rg_rows_swaps_channels():
    """Swap red and green output rows → input R becomes output G."""
    base = _solid(4, 4, (200, 50, 0))
    opts = ChannelMixerOptions(
        enabled=True,
        red=[0.0, 1.0, 0.0],   # output red ← input green
        green=[1.0, 0.0, 0.0], # output green ← input red
        blue=[0.0, 0.0, 1.0],
    )
    out = apply_channel_mixer(base, opts)
    assert out[0, 0, 0] == 50   # was green
    assert out[0, 0, 1] == 200  # was red
    assert out[0, 0, 2] == 0


def test_monochrome_applies_red_row_to_all_outputs():
    base = _solid(4, 4, (200, 50, 0))
    opts = ChannelMixerOptions(
        enabled=True,
        red=[0.3, 0.59, 0.11],  # luma weights
        monochrome=True,
    )
    out = apply_channel_mixer(base, opts)
    # All three output channels should be ~equal (0.3 * 200 + 0.59 * 50 + 0.11 * 0)
    expected = int(0.3 * 200 + 0.59 * 50 + 0.11 * 0)
    assert all(abs(int(out[0, 0, c]) - expected) <= 1 for c in range(3))
    # And all three channels are equal — that's the definition of monochrome
    assert out[0, 0, 0] == out[0, 0, 1] == out[0, 0, 2]


def test_offset_shifts_channel():
    base = _solid(4, 4, (100, 100, 100))
    opts = ChannelMixerOptions(
        enabled=True,
        offsets=[0.2, 0.0, -0.2],  # +51 / 0 / -51 in 0..255
    )
    out = apply_channel_mixer(base, opts)
    assert int(out[0, 0, 0]) > 100
    assert int(out[0, 0, 1]) == 100
    assert int(out[0, 0, 2]) < 100


def test_clipping_protects_against_overflow():
    base = _solid(4, 4, (255, 255, 255))
    opts = ChannelMixerOptions(
        enabled=True,
        red=[2.0, 2.0, 2.0],  # would overflow without clipping
    )
    out = apply_channel_mixer(base, opts)
    assert out[0, 0, 0] == 255  # clipped, not wrapped


def test_alpha_preserved():
    base = _solid(4, 4, (100, 100, 100))
    base[..., 3] = 33
    opts = ChannelMixerOptions(enabled=True, monochrome=True,
                               red=[1.0, 0.0, 0.0])
    out = apply_channel_mixer(base, opts)
    assert (out[..., 3] == 33).all()


def test_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_channel_mixer(arr, ChannelMixerOptions(enabled=True))


# ---------------------------------------------------------------------------
# Recipe integration
# ---------------------------------------------------------------------------


def test_recipe_with_only_channel_mixer_is_not_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    assert r.is_identity() is True
    r.extra["channel_mixer"] = {
        "enabled": True, "monochrome": True,
        "red": [0.3, 0.59, 0.11],
        "green": [0, 1, 0], "blue": [0, 0, 1],
        "offsets": [0, 0, 0],
    }
    assert r.is_identity() is False


def test_recipe_with_disabled_channel_mixer_stays_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["channel_mixer"] = {"enabled": False, "monochrome": True}
    assert r.is_identity() is True


# ---------------------------------------------------------------------------
# Dialog smoke
# ---------------------------------------------------------------------------


def test_dialog_loads_existing_recipe(qapp, tmp_path):
    from Imervue.gui.channel_mixer_dialog import ChannelMixerDialog
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import recipe_store

    img = tmp_path / "x.png"
    img.write_bytes(b"x")
    recipe = Recipe()
    recipe.extra["channel_mixer"] = {
        "enabled": True, "monochrome": True,
        "red": [0.3, 0.59, 0.11],
        "green": [0, 1, 0], "blue": [0, 0, 1],
        "offsets": [0.1, 0, 0],
    }
    recipe_store.set_for_path(str(img), recipe)

    class FakeViewer:
        model = type("M", (), {"images": [str(img)]})()
        current_index = 0

    dlg = ChannelMixerDialog(FakeViewer(), str(img))
    assert dlg._enable.isChecked() is True
    assert dlg._monochrome.isChecked() is True
    assert dlg._red_inputs[0].value() == pytest.approx(0.3)
    assert dlg._offset_inputs[0].value() == pytest.approx(0.1)
