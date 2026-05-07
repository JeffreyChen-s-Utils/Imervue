"""Tests for the dock extensions that close MediBang feature gaps.

Three flows:

* Layer dock's ``+◐`` adjustment-layer popup creates a layer with a
  pre-installed :class:`Adjustment`.
* Brush dock's stabiliser / scatter / colour-jitter / follow-tilt
  controls round-trip into ``ToolState.brush``.
* Comic-project page-browser dock binds to ``workspace._paint_project``,
  reflects pages on refresh, and add / remove / duplicate / move
  invariants hold.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.dock_panels import BrushDock, LayerDock
from Imervue.paint.document import PaintDocument
from Imervue.paint.page_dock import PageDock
from Imervue.paint.paint_project import PaintProject, ProjectPage
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _doc_with_one_layer(h: int = 16, w: int = 16) -> PaintDocument:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 3] = 255
    doc = PaintDocument()
    doc.load_image(arr)
    return doc


# ---------------------------------------------------------------------------
# 1. Layer dock — adjustment-layer popup adds a layer with the right kind.
# ---------------------------------------------------------------------------


def test_layer_dock_add_adjustment_creates_layer_with_adjustment(qapp):
    """The dedicated ``+◐`` button opens a popup with one entry per
    documented ``ADJUSTMENT_KINDS`` value. Picking ``"curves"`` must
    add a fresh layer and pre-install an ``Adjustment(kind='curves')``
    so the next composite runs the curves transform without further
    user setup."""
    from Imervue.paint.adjustments import ADJUSTMENT_KINDS

    doc = _doc_with_one_layer()
    dock = LayerDock(document=doc)
    try:
        before = doc.layer_count
        dock._add_adjustment_layer(   # noqa: SLF001
            "curves",
            {"per_channel": {"rgb": [(0.0, 0.0), (1.0, 1.0)]}},
        )
        assert doc.layer_count == before + 1
        new_layer = doc.layer_at(-1)
        assert new_layer.adjustment is not None
        assert new_layer.adjustment.kind == "curves"
        assert new_layer.name.startswith("Curves")

        # Menu exposes one action per documented kind.
        menu = dock._build_adjustment_menu()   # noqa: SLF001
        assert len(menu.actions()) == len(ADJUSTMENT_KINDS)
    finally:
        dock.deleteLater()


# ---------------------------------------------------------------------------
# 2. Brush dock — stabiliser / scatter / colour-jitter / follow-tilt sliders
#    round-trip through ToolState.brush.
# ---------------------------------------------------------------------------


def test_brush_dock_extra_controls_round_trip(qapp):
    state = ts.load_tool_state()
    dock = BrushDock(state)
    try:
        # Move every slider + checkbox.
        dock._stabilizer.setValue(60)   # noqa: SLF001
        dock._scatter.setValue(35)      # noqa: SLF001
        dock._color_jitter.setValue(20)  # noqa: SLF001
        dock._follow_tilt.setChecked(True)   # noqa: SLF001

        # State picked up the new values.
        assert state.brush.stabilizer == pytest.approx(0.60, abs=1e-6)
        assert state.brush.scatter == pytest.approx(0.35, abs=1e-6)
        assert state.brush.color_jitter == pytest.approx(0.20, abs=1e-6)
        assert state.brush.follow_tilt is True

        # Reverse direction: state-only update propagates back to the
        # dock (sliders re-read on the EVENT_BRUSH channel).
        state.set_brush(stabilizer=0.10, follow_tilt=False)
        assert dock._stabilizer.value() == 10   # noqa: SLF001
        assert dock._follow_tilt.isChecked() is False   # noqa: SLF001
    finally:
        dock.deleteLater()


# ---------------------------------------------------------------------------
# 3. Page browser dock — list reflects project pages, mutations refresh.
# ---------------------------------------------------------------------------


class _StubWorkspace:
    """Plain object with the slot the dock pokes — keeps the tests
    Qt-window-free since nothing in the dock requires a real workspace."""

    def __init__(self):
        self._paint_project = None


def _project_with_pages(n: int) -> PaintProject:
    project = PaintProject(name="Test Project")
    for i in range(n):
        doc = PaintDocument()
        doc.load_image(np.zeros((8, 8, 4), dtype=np.uint8))
        project.pages.append(
            ProjectPage(document=doc, name=f"Page {i + 1}"),
        )
    return project


def test_page_dock_no_project_shows_empty_state(qapp):
    ws = _StubWorkspace()
    dock = PageDock(ws)
    try:
        # No pages listed; status label says "no project".
        assert dock._list.count() == 0   # noqa: SLF001
        text = dock._status.text().lower()   # noqa: SLF001
        assert "no project" in text or "(no" in text
    finally:
        dock.deleteLater()


def test_page_dock_refresh_reflects_project_pages(qapp):
    ws = _StubWorkspace()
    ws._paint_project = _project_with_pages(3)
    dock = PageDock(ws)
    try:
        assert dock._list.count() == 3   # noqa: SLF001
        labels = [
            dock._list.item(i).text()   # noqa: SLF001
            for i in range(dock._list.count())   # noqa: SLF001
        ]
        # Every label is the documented "<index>. <name>" form.
        assert labels[0].startswith("1. Page")
        assert labels[2].startswith("3. Page")
    finally:
        dock.deleteLater()


def test_page_dock_add_appends_new_page(qapp):
    ws = _StubWorkspace()
    ws._paint_project = _project_with_pages(2)
    dock = PageDock(ws)
    try:
        dock._on_add()   # noqa: SLF001
        assert ws._paint_project.page_count == 3   # noqa: SLF001
        assert dock._list.count() == 3   # noqa: SLF001
    finally:
        dock.deleteLater()


def test_page_dock_remove_keeps_at_least_one(qapp):
    """The project model refuses to drop the last page — the dock
    must surface that without raising."""
    ws = _StubWorkspace()
    ws._paint_project = _project_with_pages(1)
    dock = PageDock(ws)
    try:
        dock._on_remove()   # noqa: SLF001 — silently no-ops on the last page
        assert ws._paint_project.page_count == 1   # noqa: SLF001
    finally:
        dock.deleteLater()


def test_page_dock_duplicate_inserts_a_clone(qapp):
    ws = _StubWorkspace()
    ws._paint_project = _project_with_pages(2)
    dock = PageDock(ws)
    try:
        before = ws._paint_project.page_count
        dock._on_duplicate()   # noqa: SLF001
        assert ws._paint_project.page_count == before + 1
        # The clone's name carries the "copy" suffix the dock adds.
        names = [p.name for p in ws._paint_project.pages]
        assert any("copy" in n.lower() for n in names)
    finally:
        dock.deleteLater()


def test_page_dock_double_click_emits_page_selected(qapp):
    """Double-clicking a row fires ``page_selected`` with the row's
    project index — the workspace handler swaps the canvas's
    document to that page."""
    ws = _StubWorkspace()
    ws._paint_project = _project_with_pages(3)
    dock = PageDock(ws)
    try:
        emitted: list[int] = []
        dock.page_selected.connect(emitted.append)
        item = dock._list.item(2)   # noqa: SLF001
        dock._on_double_clicked(item)   # noqa: SLF001
        assert emitted == [2]
    finally:
        dock.deleteLater()
