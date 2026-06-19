"""Tests for LSB steganography encode/decode."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.steganography import capacity_bytes, hide_message, reveal_message


def _rgba(h=64, w=64, seed=0):
    rng = np.random.default_rng(seed)
    rgb = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_round_trip_ascii():
    img = _rgba()
    out = hide_message(img, "hello world")
    assert reveal_message(out) == "hello world"


def test_round_trip_unicode():
    img = _rgba()
    message = "héllo 世界 🎨"
    assert reveal_message(hide_message(img, message)) == message


def test_empty_message_round_trips():
    assert reveal_message(hide_message(_rgba(), "")) == ""


def test_reveal_on_clean_image_is_empty_or_safe():
    # A random image almost never decodes to a valid non-empty UTF-8 message.
    result = reveal_message(_rgba(seed=42))
    assert isinstance(result, str)


def test_capacity_and_too_long():
    img = _rgba(8, 8)
    cap = capacity_bytes(img)
    assert cap > 0
    with pytest.raises(ValueError):
        hide_message(img, "x" * (cap + 1))


def test_hide_only_touches_lsb():
    img = _rgba()
    out = hide_message(img, "data")
    # High 7 bits of the RGB channels are unchanged (only the LSB may flip).
    assert np.array_equal(out[..., :3] & 0xFE, img[..., :3] & 0xFE)
    assert np.array_equal(out[..., 3], img[..., 3])  # alpha untouched


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        reveal_message(np.zeros((8, 8), dtype=np.uint8))
