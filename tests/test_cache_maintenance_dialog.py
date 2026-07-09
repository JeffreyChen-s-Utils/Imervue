"""Tests for the thumbnail cache maintenance dialog."""
from __future__ import annotations

import pytest

from Imervue.gui.cache_maintenance_dialog import CacheMaintenanceDialog, _format_bytes


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (2048, "2.0 KB"),
        (5 * 1024**2, "5.0 MB"),
        (3 * 1024**3, "3.0 GB"),
        (5000 * 1024**3, "5000.0 GB"),
    ],
)
def test_format_bytes(size, expected):
    assert _format_bytes(size) == expected


class _FakeCache:
    def __init__(self, size):
        self.size = size
        self.clear_calls = 0

    def total_bytes(self):
        return self.size

    def clear(self):
        self.clear_calls += 1
        self.size = 0


def test_dialog_shows_size_and_clears_cache(qapp, monkeypatch):
    fake = _FakeCache(2048)
    monkeypatch.setattr(
        "Imervue.gui.cache_maintenance_dialog.thumbnail_disk_cache", fake,
    )
    dialog = CacheMaintenanceDialog(None)
    try:
        assert "2.0 KB" in dialog._size.text()

        dialog._clear()
        assert fake.clear_calls == 1
        assert "0 B" in dialog._size.text()
    finally:
        dialog.deleteLater()
