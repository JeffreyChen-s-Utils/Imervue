"""Tests for comic page templates and project bootstrap."""
from __future__ import annotations

import pytest

from Imervue.paint.page_templates import (
    DEFAULT_TEMPLATE_NAME,
    PAGE_TEMPLATES,
    PageTemplate,
    available_template_names,
    make_blank_page,
    project_from_template,
    template_by_name,
)


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------


def test_default_template_name_is_in_registry():
    assert DEFAULT_TEMPLATE_NAME in available_template_names()


def test_available_template_names_in_canonical_order():
    """First template is B5 — manga's most common physical size."""
    names = available_template_names()
    assert names[0] == "manga_b5"


def test_template_set_includes_documented_formats():
    names = set(available_template_names())
    assert {
        "manga_b5", "manga_b4", "manga_a4", "manga_a5",
        "webtoon_strip", "square_2400",
    } <= names


def test_template_by_name_finds_built_in():
    tpl = template_by_name("manga_b5")
    assert tpl.width_mm == 182.0
    assert tpl.height_mm == 257.0


def test_template_by_name_raises_on_unknown():
    with pytest.raises(KeyError, match="unknown page template"):
        template_by_name("does_not_exist")


# ---------------------------------------------------------------------------
# Pixel-size math
# ---------------------------------------------------------------------------


def test_b5_at_350_dpi_is_print_ready():
    """JIS B5 = 182 × 257 mm. At 350 DPI that's 2508 × 3541 px."""
    tpl = template_by_name("manga_b5")
    w, h = tpl.pixel_size
    assert w == 2508
    assert h == 3541


def test_a4_at_350_dpi():
    """A4 = 210 × 297 mm. At 350 DPI that's 2894 × 4093 px."""
    tpl = template_by_name("manga_a4")
    w, h = tpl.pixel_size
    assert w == 2894
    assert h == 4093


def test_webtoon_strip_pixel_size_is_800_by_3200():
    tpl = template_by_name("webtoon_strip")
    assert tpl.pixel_size == (800, 3200)


def test_square_2400_pixel_size_is_square():
    tpl = template_by_name("square_2400")
    assert tpl.pixel_size == (2400, 2400)


def test_pixel_size_floors_at_one():
    """A vanishingly small mm + DPI must still produce a valid 1×1 page."""
    tpl = PageTemplate(name="tiny", width_mm=0.0, height_mm=0.0, dpi=1)
    assert tpl.pixel_size == (1, 1)


# ---------------------------------------------------------------------------
# make_blank_page
# ---------------------------------------------------------------------------


def test_make_blank_page_creates_paintable_document():
    tpl = template_by_name("manga_a5")
    page = make_blank_page(tpl, name="Cover")
    assert page.name == "Cover"
    assert page.document.layer_count == 1
    img = page.document.active_layer().image
    expected_w, expected_h = tpl.pixel_size
    assert img.shape == (expected_h, expected_w, 4)
    # Default fill is opaque white.
    assert tuple(img[0, 0]) == (255, 255, 255, 255)


def test_make_blank_page_honours_custom_fill():
    tpl = PageTemplate(
        name="cream", width_mm=20.0, height_mm=20.0, dpi=72,
        fill_rgba=(250, 240, 220, 255),
    )
    page = make_blank_page(tpl)
    img = page.document.active_layer().image
    assert tuple(img[0, 0]) == (250, 240, 220, 255)


def test_make_blank_page_rejects_oversize_template():
    huge = PageTemplate(name="huge", width_mm=2000.0, height_mm=2000.0, dpi=600)
    with pytest.raises(ValueError, match="oversize"):
        make_blank_page(huge)


# ---------------------------------------------------------------------------
# project_from_template
# ---------------------------------------------------------------------------


def test_project_from_template_seeds_one_page_by_default():
    project = project_from_template(template_by_name("manga_a5"))
    assert project.page_count == 1
    assert project.active_page_index == 0


def test_project_from_template_can_seed_multiple_pages():
    project = project_from_template(
        template_by_name("manga_a5"), page_count=4,
    )
    assert project.page_count == 4
    assert [p.name for p in project.pages] == [
        "Page 1", "Page 2", "Page 3", "Page 4",
    ]


def test_project_from_template_passes_metadata():
    project = project_from_template(
        template_by_name("manga_b5"),
        project_name="My Manga",
        author="Test Author",
    )
    assert project.name == "My Manga"
    assert project.author == "Test Author"


def test_project_from_template_rejects_zero_page_count():
    with pytest.raises(ValueError, match=">= 1"):
        project_from_template(template_by_name("manga_b5"), page_count=0)


def test_pages_share_same_pixel_dimensions():
    """Every page in a project starts at the same canvas size — the
    project model assumes uniform page geometry for compositing /
    export workflows."""
    project = project_from_template(
        template_by_name("manga_a5"), page_count=3,
    )
    shapes = {p.document.shape for p in project.pages}
    assert len(shapes) == 1


# ---------------------------------------------------------------------------
# PAGE_TEMPLATES tuple is immutable
# ---------------------------------------------------------------------------


def test_page_templates_is_tuple_for_immutability():
    """A mutable list could be reordered at runtime by accident; the
    UI dropdown depends on stable ordering across the session."""
    assert isinstance(PAGE_TEMPLATES, tuple)


# ---------------------------------------------------------------------------
# PageNavigatorDock — Qt smoke tests
# ---------------------------------------------------------------------------


def test_page_navigator_dock_lists_pages(qapp):
    from Imervue.paint.dock_panels import PageNavigatorDock

    project = project_from_template(
        template_by_name("manga_a5"), page_count=3,
    )
    dock = PageNavigatorDock(project=project)
    try:
        assert dock._list.count() == 3  # noqa: SLF001
        assert dock._list.currentRow() == 0  # noqa: SLF001
    finally:
        dock.deleteLater()


def test_page_navigator_dock_emits_page_activated_on_row_change(qapp):
    from Imervue.paint.dock_panels import PageNavigatorDock

    project = project_from_template(
        template_by_name("manga_a5"), page_count=3,
    )
    dock = PageNavigatorDock(project=project)
    try:
        emitted: list[int] = []
        dock.page_activated.connect(emitted.append)
        dock._list.setCurrentRow(2)  # noqa: SLF001
        assert emitted == [2]
    finally:
        dock.deleteLater()


def test_page_navigator_dock_add_button_emits_request(qapp):
    from Imervue.paint.dock_panels import PageNavigatorDock
    from PySide6.QtWidgets import QToolButton

    project = project_from_template(
        template_by_name("manga_a5"), page_count=1,
    )
    dock = PageNavigatorDock(project=project)
    try:
        emitted = [0]
        dock.add_requested.connect(lambda: emitted.__setitem__(0, emitted[0] + 1))
        buttons = dock.findChildren(QToolButton)
        # First button is "+".
        buttons[0].click()
        assert emitted == [1]
    finally:
        dock.deleteLater()


def test_page_navigator_dock_refresh_after_set_project(qapp):
    from Imervue.paint.dock_panels import PageNavigatorDock

    a = project_from_template(template_by_name("manga_a5"), page_count=1)
    b = project_from_template(template_by_name("manga_b5"), page_count=4)
    dock = PageNavigatorDock(project=a)
    try:
        assert dock._list.count() == 1  # noqa: SLF001
        dock.set_project(b)
        assert dock._list.count() == 4  # noqa: SLF001
    finally:
        dock.deleteLater()


def test_page_navigator_dock_move_up_emits_request(qapp):
    from Imervue.paint.dock_panels import PageNavigatorDock
    from PySide6.QtWidgets import QToolButton

    project = project_from_template(template_by_name("manga_a5"), page_count=3)
    project.set_active_page(2)
    dock = PageNavigatorDock(project=project)
    try:
        emitted: list[tuple[int, int]] = []
        dock.move_requested.connect(lambda src, dst: emitted.append((src, dst)))
        buttons = dock.findChildren(QToolButton)
        # Up button is the third — add, remove, up, down.
        buttons[2].click()
        assert emitted == [(2, 1)]
    finally:
        dock.deleteLater()


def test_page_navigator_dock_move_up_at_top_is_no_op(qapp):
    """Active page is already at index 0; pressing ↑ must do nothing
    rather than emitting a (-1, 0) request that would crash project.move_page."""
    from Imervue.paint.dock_panels import PageNavigatorDock
    from PySide6.QtWidgets import QToolButton

    project = project_from_template(template_by_name("manga_a5"), page_count=3)
    project.set_active_page(0)
    dock = PageNavigatorDock(project=project)
    try:
        emitted: list[tuple[int, int]] = []
        dock.move_requested.connect(lambda src, dst: emitted.append((src, dst)))
        buttons = dock.findChildren(QToolButton)
        buttons[2].click()
        assert emitted == []
    finally:
        dock.deleteLater()
