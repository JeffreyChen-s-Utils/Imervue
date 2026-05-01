"""Tests for the auto page-number stamper."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.page_numbering import (
    DEFAULT_PAGE_NUMBER_LAYER,
    PAGE_NUMBER_CORNERS,
    stamp_page_numbers,
)
from Imervue.paint.paint_project import PaintProject, ProjectPage


def _project_with_pages(n: int, *, h: int = 64, w: int = 48) -> PaintProject:
    project = PaintProject(name="proj")
    for i in range(n):
        doc = PaintDocument()
        doc.load_image(np.zeros((h, w, 4), dtype=np.uint8))
        project.add_page(ProjectPage(document=doc, name=f"P{i + 1}"))
    return project


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_rejects_unknown_corner():
    project = _project_with_pages(1)
    with pytest.raises(ValueError, match="corner"):
        stamp_page_numbers(project, corner="centre")


def test_rejects_negative_margin():
    project = _project_with_pages(1)
    with pytest.raises(ValueError, match="margin"):
        stamp_page_numbers(project, margin=-1)


def test_rejects_zero_font_size():
    project = _project_with_pages(1)
    with pytest.raises(ValueError, match="font_size"):
        stamp_page_numbers(project, font_size=0)


def test_rejects_blank_layer_name():
    project = _project_with_pages(1)
    with pytest.raises(ValueError, match="layer_name"):
        stamp_page_numbers(project, layer_name="   ")


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


def test_stamp_returns_count_of_pages_stamped(qapp):
    project = _project_with_pages(3)
    assert stamp_page_numbers(project) == 3


def test_stamp_adds_a_layer_per_page(qapp):
    project = _project_with_pages(2)
    before = [p.document.layer_count for p in project.pages]
    stamp_page_numbers(project)
    after = [p.document.layer_count for p in project.pages]
    assert all(a == b + 1 for a, b in zip(after, before, strict=True))


def test_stamped_layer_uses_requested_name(qapp):
    project = _project_with_pages(1)
    stamp_page_numbers(project, layer_name="Folio")
    assert project.pages[0].document.active_layer().name == "Folio"


def test_default_layer_name_is_page_number(qapp):
    project = _project_with_pages(1)
    stamp_page_numbers(project)
    assert (
        project.pages[0].document.active_layer().name
        == DEFAULT_PAGE_NUMBER_LAYER
    )


# ---------------------------------------------------------------------------
# Numbering / corner placement
# ---------------------------------------------------------------------------


def test_start_at_offsets_the_first_page_number(qapp):
    """``start_at=5`` means the first page gets number 5, not 1."""
    project = _project_with_pages(2)
    stamp_page_numbers(project, start_at=5)
    # The stamped layer's pixels live in different corners between
    # the two pages? No — same corner. But the rendered glyphs differ
    # because the digit is "5" vs "6". A trivial sanity check: the
    # two layers' pixels are NOT identical.
    a = project.pages[0].document.active_layer().image
    b = project.pages[1].document.active_layer().image
    assert not np.array_equal(a, b)


@pytest.mark.parametrize("corner", list(PAGE_NUMBER_CORNERS))
def test_each_corner_paints_inside_its_quadrant(qapp, corner):
    """A stamp at a given corner must produce inked pixels inside
    that corner's quadrant of the canvas — guards against an x/y
    swap bug in :func:`_corner_offset`."""
    project = _project_with_pages(1, h=128, w=128)
    stamp_page_numbers(project, corner=corner, font_size=24, margin=4)
    layer = project.pages[0].document.active_layer().image
    inked = layer[..., 3] > 0
    assert inked.any()
    ys, xs = np.where(inked)
    cy = layer.shape[0] // 2
    cx = layer.shape[1] // 2
    if corner == "top_left":
        assert ys.mean() < cy and xs.mean() < cx
    elif corner == "top_right":
        assert ys.mean() < cy and xs.mean() > cx
    elif corner == "bottom_left":
        assert ys.mean() > cy and xs.mean() < cx
    elif corner == "bottom_right":
        assert ys.mean() > cy and xs.mean() > cx


def test_stamp_skips_empty_pages(qapp):
    """A page whose document never had a document.load_image (no
    shape) is skipped silently rather than crashing the verb."""
    project = PaintProject(name="proj")
    project.add_page(ProjectPage(document=PaintDocument(), name="P1"))
    # Add a real page so the project has at least one stampable page.
    real = PaintDocument()
    real.load_image(np.zeros((32, 32, 4), dtype=np.uint8))
    project.add_page(ProjectPage(document=real, name="P2"))
    assert stamp_page_numbers(project) == 1


def test_stamp_invalidates_each_pages_composite(qapp):
    """The stamp layer is added via ``add_layer`` which already
    invalidates the composite cache; verify the post-stamp
    ``composite()`` returns a fresh, non-empty buffer."""
    project = _project_with_pages(1)
    stamp_page_numbers(project)
    composite = project.pages[0].document.composite()
    assert composite is not None
    assert composite.shape[2] == 4
