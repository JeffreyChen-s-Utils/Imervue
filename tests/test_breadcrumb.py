"""Tests for BreadcrumbBar — segment building and clicks."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QLabel, QPushButton


@pytest.fixture
def bar(qapp):
    from Imervue.gui.breadcrumb_bar import BreadcrumbBar
    mw = MagicMock()
    bc = BreadcrumbBar(mw)
    return bc


def _count_segment_buttons(bar) -> int:
    return sum(
        1 for i in range(bar._layout.count())
        if isinstance(bar._layout.itemAt(i).widget(), QPushButton)
    )


def _count_separators(bar) -> int:
    return sum(
        1 for i in range(bar._layout.count())
        if isinstance(bar._layout.itemAt(i).widget(), QLabel)
    )


class TestBreadcrumbBar:
    def test_empty_path_hides_bar(self, bar):
        bar.set_path("")
        assert bar.isVisible() is False

    def test_single_segment(self, bar, tmp_path):
        bar.set_path(str(tmp_path))
        parts = Path(tmp_path).parts
        assert _count_segment_buttons(bar) == len(parts)
        # Separators sit between each pair, so count = parts - 1
        assert _count_separators(bar) == max(len(parts) - 1, 0)

    def test_file_path_uses_parent(self, bar, tmp_path):
        f = tmp_path / "file.png"
        f.write_bytes(b"")
        bar.set_path(str(f))
        # Should render segments of the parent folder, not the file
        parts = Path(tmp_path).parts
        assert _count_segment_buttons(bar) == len(parts)

    def test_rebuild_clears_old_segments(self, bar, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        bar.set_path(str(tmp_path))
        before = _count_segment_buttons(bar)
        bar.set_path(str(sub))
        after = _count_segment_buttons(bar)
        # Sub has one more segment than tmp_path
        assert after == before + 1
