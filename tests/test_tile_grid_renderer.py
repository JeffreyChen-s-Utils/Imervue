"""Tests for the thumbnail fade-in alpha helper (no GL context needed)."""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from Imervue.gpu_image_view.tile_grid_renderer import TileGridRenderer
from Imervue.gpu_image_view.view_animator import THUMB_FADE_MS


def _renderer(load_times):
    return TileGridRenderer(SimpleNamespace(_tile_load_times=load_times))


def test_unknown_tile_is_fully_opaque():
    # Tiles without a recorded arrival time (already on screen) never fade.
    assert _renderer({})._tile_alpha("x.png") == 1.0


def test_just_loaded_tile_is_not_yet_opaque():
    renderer = _renderer({"a.png": time.monotonic()})
    assert 0.0 <= renderer._tile_alpha("a.png") < 1.0


def test_old_tile_is_fully_opaque():
    elapsed_past_window = (THUMB_FADE_MS / 1000) + 1
    renderer = _renderer({"a.png": time.monotonic() - elapsed_past_window})
    assert renderer._tile_alpha("a.png") == pytest.approx(1.0)
