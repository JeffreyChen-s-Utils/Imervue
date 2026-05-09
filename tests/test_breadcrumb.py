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


# ---------------------------------------------------------------------------
# Phase 22 — segment tooltip carries the full path so a truncated
# label still tells the user where the breadcrumb leads.
# ---------------------------------------------------------------------------


def test_segment_buttons_have_full_path_tooltips(qapp, tmp_path):
    """Each breadcrumb button's tooltip is the absolute folder
    path so users can hover to see where a click would land."""
    from PySide6.QtWidgets import QPushButton
    from Imervue.gui.breadcrumb_bar import BreadcrumbBar
    deep = tmp_path / "alpha" / "beta" / "gamma"
    deep.mkdir(parents=True)
    bar = BreadcrumbBar(main_window=None)
    try:
        bar.set_path(str(deep))
        buttons = [
            bar._layout.itemAt(i).widget()  # noqa: SLF001
            for i in range(bar._layout.count())  # noqa: SLF001
            if isinstance(bar._layout.itemAt(i).widget(), QPushButton)  # noqa: SLF001
        ]
        tips = [btn.toolTip() for btn in buttons]
        assert tips
        # Trailing segment points at the deep path the bar shows.
        assert tips[-1] == str(deep)
        # Every tip is a non-empty path string.
        for tip in tips:
            assert tip
    finally:
        bar.deleteLater()
