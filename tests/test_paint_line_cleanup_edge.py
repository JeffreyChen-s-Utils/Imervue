"""close_small_gaps must not erase ink within max_gap px of the canvas edge.

Morphological closing is extensive (result must contain the input), but the
erosion's border clamp dropped edge-touching lineart. The result is now unioned
with the original mask.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.line_cleanup import close_small_gaps


def test_edge_ink_is_preserved():
    mask = np.zeros((12, 12), dtype=np.bool_)
    mask[0, 0] = True      # corner
    mask[0, 6] = True      # top edge
    mask[6, 6] = True      # interior
    out = close_small_gaps(mask, max_gap=2)
    # Every original ink pixel survives (closing is extensive).
    assert bool(np.all(out[mask]))
    assert out[0, 0]
    assert out[0, 6]


def test_returns_a_fresh_mask():
    mask = np.zeros((8, 8), dtype=np.bool_)
    mask[4, 4] = True
    out = close_small_gaps(mask, max_gap=1)
    assert out is not mask
    assert mask[4, 4]      # input not mutated
