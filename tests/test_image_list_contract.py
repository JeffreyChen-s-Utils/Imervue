"""Observable image-list sorting and asynchronous row contracts."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPersistentModelIndex, Qt
from PySide6.QtGui import QImage

from Imervue.gui.image_list_view import ImageListModel


@pytest.mark.parametrize("column", [-1, 0, 3, 4, 5, 6, 7, 99])
@pytest.mark.parametrize("descending", [False, True])
def test_sort_preserves_duplicate_row_identity(qapp, column, descending):
    model = ImageListModel(["z10.png", "z2.jpg", "z2.jpg"])
    rows = model._rows[:]
    tracked = [QPersistentModelIndex(model.index(i, 3)) for i in range(3)]
    order = Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder
    model.sort(column, order)
    for row, index in zip(rows, tracked, strict=True):
        assert model._rows[index.row()] is row
    if column in (-1, 4, 5, 7):
        assert model._rows == rows
    elif column == 6:
        assert model._rows == (
            [rows[0], rows[1], rows[2]] if descending else [rows[1], rows[2], rows[0]]
        )
    else:
        assert model._rows == (
            [rows[0], rows[1], rows[2]] if descending else [rows[1], rows[2], rows[0]]
        )


def test_reset_retains_index_and_accepts_late_same_path_result(qapp):
    metadata = SimpleNamespace(peek=lambda path: None)
    model = ImageListModel(["same.png"], metadata)
    model._in_flight.add("same.png")
    model._stale.add("same.png")
    model._retry["same.png"] = 2
    model.set_paths(["same.png", "same.png"])
    assert model._metadata_index is metadata
    changes = []
    model.dataChanged.connect(lambda a, b, roles: changes.append((a.row(), b.row(), roles)))
    model._on_fetched("same.png", QImage(), 4, 8, 2.0, 3.0, True)
    assert model._rows[0].fetched
    assert not model._rows[1].fetched
    assert (model._rows[0].width, model._rows[0].height) == (4, 8)
    assert changes == [(0, 0, [Qt.ItemDataRole.DecorationRole, Qt.ItemDataRole.DisplayRole])]
    assert not model._in_flight and not model._stale and not model._retry


def test_repeated_refetch_restarts_only_after_stale_completion(qapp):
    model = ImageListModel(["same.png"])
    started = []
    model._pool = SimpleNamespace(start=started.append)
    model._ensure_fetched(model._rows[0])
    model.refetch(["same.png"])
    model.refetch(["same.png"])
    assert len(started) == 1
    model._on_fetched("same.png", QImage(), 1, 1, 1.0, 1.0, True)
    assert len(started) == 2
    assert not model._rows[0].fetched
    model._on_fetched("same.png", QImage(), 2, 2, 2.0, 2.0, True)
    assert model._rows[0].width == 2
    assert model._rows[0].fetched
