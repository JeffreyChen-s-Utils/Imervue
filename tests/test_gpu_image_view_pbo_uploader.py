"""Tests for the PBO uploader's pure-Python decision and bookkeeping
helpers.

The GL-call portions are ``# pragma: no cover`` because exercising
them needs a live OpenGL context. The decision matrix, the
round-robin index, and the buffer-size math live in pure helpers
that this file covers exhaustively.
"""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.pbo_uploader import (
    DEFAULT_MAX_TILE_SIDE,
    PBO_RING_SIZE,
    PBOTextureUploader,
    next_ring_index,
    pbo_buffer_bytes,
    tile_fits_pbo,
)


# ---------------------------------------------------------------
# next_ring_index
# ---------------------------------------------------------------


def test_ring_index_walks_through_buffers():
    """Sweep through the ring once; final wrap returns to 0."""
    seen = []
    idx = 0
    for _ in range(PBO_RING_SIZE * 2):
        seen.append(idx)
        idx = next_ring_index(idx)
    assert seen == [0, 1, 0, 1]   # for ring size 2


def test_ring_index_zero_size_clamps():
    """Defensive: a misconfigured ring (size 0) must not crash on
    modulo zero. Helper returns 0 so the uploader falls back to
    'always use buffer 0' rather than divide-by-zero."""
    assert next_ring_index(5, ring_size=0) == 0


def test_ring_index_negative_size_clamps():
    assert next_ring_index(5, ring_size=-1) == 0


def test_ring_constant_is_two():
    """A doc-fence test — the module documents that two buffers is
    enough; if a future tuning grows the ring this test fails so
    callers depending on size 2 (the index walker tests) get
    updated together."""
    assert PBO_RING_SIZE == 2


# ---------------------------------------------------------------
# pbo_buffer_bytes
# ---------------------------------------------------------------


def test_buffer_bytes_quadratic_in_side():
    """Doubling max_side quadruples the bytes — same shape as a
    plain texture."""
    small = pbo_buffer_bytes(max_side=256)
    big = pbo_buffer_bytes(max_side=512)
    assert big == small * 4


def test_buffer_bytes_default_is_a_megabyte_class():
    """The default max_side should yield a few-MB PBO — small
    enough to ship two of, big enough to cover real tiles."""
    bytes_ = pbo_buffer_bytes()
    # 1024 × 1024 × 4 = 4 MB.
    assert bytes_ == 4 * 1024 * 1024


def test_buffer_bytes_zero_or_negative_returns_zero():
    """A 0-side request → 0 bytes; the uploader treats that as
    'PBO disabled'."""
    assert pbo_buffer_bytes(max_side=0) == 0
    assert pbo_buffer_bytes(max_side=-100) == 0


def test_buffer_bytes_custom_bpp():
    """RGB texture (3 bpp) → smaller PBO than RGBA (4 bpp)."""
    rgba = pbo_buffer_bytes(max_side=256, bytes_per_pixel=4)
    rgb = pbo_buffer_bytes(max_side=256, bytes_per_pixel=3)
    assert rgb == rgba * 3 // 4


# ---------------------------------------------------------------
# tile_fits_pbo
# ---------------------------------------------------------------


def test_tile_fits_within_max_side():
    assert tile_fits_pbo(512, 512) is True
    assert tile_fits_pbo(DEFAULT_MAX_TILE_SIDE, DEFAULT_MAX_TILE_SIDE) is True


def test_tile_exceeds_max_side():
    """Oversized tile → falls back to direct upload. The PBO
    would have to be reallocated, killing the buffer-reuse perf
    we built it for."""
    assert tile_fits_pbo(DEFAULT_MAX_TILE_SIDE + 1, 100) is False
    assert tile_fits_pbo(100, DEFAULT_MAX_TILE_SIDE + 1) is False


def test_tile_with_zero_dim_does_not_fit():
    """A zero-sized tile shouldn't even reach the uploader, but
    if it does the helper says 'no' (don't try to PBO-upload an
    empty buffer)."""
    assert tile_fits_pbo(0, 100) is False
    assert tile_fits_pbo(100, 0) is False


def test_tile_custom_max_side():
    """Caller-overridable ceiling for callers that want a tighter
    threshold (small embedded GL devices)."""
    assert tile_fits_pbo(300, 300, max_side=200) is False
    assert tile_fits_pbo(150, 150, max_side=200) is True


# ---------------------------------------------------------------
# PBOTextureUploader — pure-helper paths
# ---------------------------------------------------------------


def test_uploader_starts_uninitialised():
    """Construction is cheap — the GL allocations wait for
    ``initialise()`` so the GUI thread isn't blocked by GL setup
    during widget construction."""
    up = PBOTextureUploader()
    assert up.initialised is False


def test_uploader_buffer_bytes_matches_module_default():
    up = PBOTextureUploader()
    assert up.buffer_bytes == pbo_buffer_bytes(DEFAULT_MAX_TILE_SIDE)


def test_uploader_buffer_bytes_zero_for_zero_max_side():
    """Zero max_side → the uploader is effectively disabled.
    ``initialise()`` will refuse the allocation."""
    up = PBOTextureUploader(max_side=0)
    assert up.buffer_bytes == 0


def test_decide_uses_direct_when_not_initialised():
    """The decision helper must respect runtime state — a
    freshly-constructed uploader that hasn't called initialise
    yet falls back to direct upload."""
    path = PBOTextureUploader.decide_upload_path(
        100, 100, initialised=False,
    )
    assert path == "direct"


def test_decide_uses_pbo_when_initialised_and_fits():
    path = PBOTextureUploader.decide_upload_path(
        512, 512, initialised=True,
    )
    assert path == "pbo"


def test_decide_uses_direct_when_oversized():
    """Even a perfectly-initialised uploader hands oversized tiles
    to the direct path."""
    path = PBOTextureUploader.decide_upload_path(
        DEFAULT_MAX_TILE_SIDE + 1, 100, initialised=True,
    )
    assert path == "direct"


def test_advance_walks_round_robin():
    """The uploader's index advance must follow the round-robin
    so successive tile uploads land on alternating PBOs."""
    up = PBOTextureUploader()
    assert up.advance() == 0
    assert up.advance() == 1
    assert up.advance() == 0   # wraps back
    assert up.advance() == 1


def test_shutdown_on_uninitialised_is_safe():
    """A reasonable test runner might destroy the uploader before
    initialise was ever called — shutdown must tolerate that."""
    up = PBOTextureUploader()
    up.shutdown()   # no GL calls expected, must not raise


@pytest.mark.parametrize("side", [256, 512, 1024])
def test_decide_path_is_pbo_for_typical_tile_sizes(side):
    """Common tile sizes used by the viewer (256/512/1024) all
    use the PBO path when initialised."""
    path = PBOTextureUploader.decide_upload_path(
        side, side, initialised=True,
    )
    assert path == "pbo"
