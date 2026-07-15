"""Tests for the layer-dock row → layer-index mapping under a search filter.

The dock lists layers newest-first and, when the "Search layers…" field is
active, only the matching rows. Clicking a row used arithmetic that ignored the
filter and selected the wrong layer; it now maps through the visible indices.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.docks.layers import _layer_index_for_row


# ---------------------------------------------------------------------------
# _layer_index_for_row — the pure mapping
# ---------------------------------------------------------------------------

def test_unfiltered_reduces_to_newest_first():
    vis = {0, 1, 2, 3, 4}
    assert [_layer_index_for_row(vis, r) for r in range(5)] == [4, 3, 2, 1, 0]


def test_filtered_maps_rows_to_true_indices():
    vis = {1, 3}  # only layers 1 and 3 survive the search
    assert _layer_index_for_row(vis, 0) == 3   # newest-first
    assert _layer_index_for_row(vis, 1) == 1


def test_out_of_range_row_returns_minus_one():
    assert _layer_index_for_row({1, 3}, 2) == -1
    assert _layer_index_for_row(set(), 0) == -1


# ---------------------------------------------------------------------------
# End-to-end through the real dock
# ---------------------------------------------------------------------------

def test_row_click_selects_the_true_layer_with_search_active(qapp):
    from Imervue.paint.dock_panels import LayerDock
    from Imervue.paint.document import PaintDocument

    doc = PaintDocument()
    doc.load_image(np.zeros((8, 8, 4), dtype=np.uint8))
    doc.add_layer(name="keep-a")
    doc.add_layer(name="drop")
    doc.add_layer(name="keep-b")

    dock = LayerDock(doc)
    try:
        dock._search_query = "keep"          # noqa: SLF001
        dock.refresh()
        keep_rows = sorted(doc.find_layers("keep"), reverse=True)  # newest-first
        assert len(keep_rows) == 2
        # Clicking the 2nd filtered row must activate the 2nd keep layer — the
        # old count-1-row arithmetic would land on the filtered-out "drop".
        dock._on_row_changed(1)              # noqa: SLF001
        assert doc.active_layer_index() == keep_rows[1]
    finally:
        dock.deleteLater()
