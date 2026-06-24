"""Tests for the contact-sheet layout presets."""
from __future__ import annotations

import pytest

from Imervue.export.contact_sheet_layouts import (
    LAYOUT_NAMES,
    cells_per_page,
    layout_grid,
    layout_options,
)


def test_layout_names_include_default():
    assert "default" in LAYOUT_NAMES
    assert len(LAYOUT_NAMES) >= 3


def test_layout_options_resolves_grid_and_caption():
    opts = layout_options("compact")
    assert (opts.rows, opts.cols) == (8, 6)
    assert opts.caption is False
    assert opts.margin_mm == pytest.approx(5.0)


def test_layout_options_applies_output_params():
    opts = layout_options("default", page_size="Letter", title="June", dpi=150)
    assert opts.page_size == "Letter"
    assert opts.title == "June"
    assert opts.dpi == 150


def test_layout_options_defaults_output_params():
    opts = layout_options("proof")
    assert opts.page_size == "A4"
    assert opts.title == ""
    assert opts.dpi == 300


@pytest.mark.parametrize("name", LAYOUT_NAMES)
def test_every_layout_resolves(name):
    opts = layout_options(name)
    assert opts.rows > 0 and opts.cols > 0


def test_layout_grid_and_cells_per_page():
    assert layout_grid("compact") == (8, 6)
    assert cells_per_page("compact") == 48


def test_unknown_layout_raises():
    with pytest.raises(ValueError, match="unknown contact-sheet layout"):
        layout_options("billboard")
    with pytest.raises(ValueError):
        cells_per_page("billboard")
