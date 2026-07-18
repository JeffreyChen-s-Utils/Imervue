"""CLAHE must equalize the bottom/right edge of a small image, not blend it
toward identity.

ceil-division tiling leaves empty trailing tiles (identity LUTs) on images
smaller than the tile count; the interpolation used to blend the edge toward
them, under-equalizing it. It now clamps to the last tile with real data.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.clahe import _clahe_plane


def test_small_image_bottom_edge_equalized_like_interior():
    # 10 rows < the default 8 tiles per axis after ceil -> empty trailing tiles.
    # A narrow per-row ramp (range 9) that CLAHE should stretch wide.
    plane = np.tile(np.arange(100, 110, dtype=np.uint8), (10, 1))
    out = _clahe_plane(plane, clip_limit=3.0, tiles=8)

    assert out.shape == plane.shape
    interior_range = int(out[4].max()) - int(out[4].min())
    bottom_range = int(out[-1].max()) - int(out[-1].min())
    assert interior_range > 20                      # CLAHE stretched the input
    # The bottom edge is equalized comparably to the interior (pre-fix it was
    # blended toward the empty identity tile and came out ~25% under-equalized).
    assert bottom_range >= interior_range * 0.9
