"""Tests for the Layer menu + LayerDock UI improvements."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.layer_menu import _LayerMenuBridge
from Imervue.paint.paint_menu_bar import menu_for
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Menu population
# ---------------------------------------------------------------------------


def test_layer_menu_has_documented_actions(qapp):
    ws = PaintWorkspace()
    try:
        layer_menu = menu_for(ws, "layer")
        # 4 layer-stack actions + sep + 5 mask actions + sep
        # + clipping toggle + sep + 4 effect actions + sep
        # + delete = 19 entries.
        assert len(layer_menu.actions()) == 19
    finally:
        ws.deleteLater()


def test_layer_menu_actions_have_translated_labels(qapp):
    ws = PaintWorkspace()
    try:
        layer_menu = menu_for(ws, "layer")
        labels = [a.text() for a in layer_menu.actions() if not a.isSeparator()]
        for label in labels:
            assert not label.startswith("paint_layer_"), label
    finally:
        ws.deleteLater()


def test_layer_menu_actions_have_shortcuts_or_documented_omission(qapp):
    """Most actions get a shortcut, but the rarely-used mask verbs
    (Invert / Apply / Delete Mask) intentionally have none — power
    users tend to wire their own bindings rather than collide with
    Photoshop's mismatched shortcuts here. So we just verify the
    workhorses (Add Layer / Add Vector / Duplicate / Merge / Add
    Mask / Delete Layer) still carry their expected key combo."""
    ws = PaintWorkspace()
    try:
        layer_menu = menu_for(ws, "layer")
        with_shortcut = sum(
            1 for a in layer_menu.actions()
            if not a.isSeparator() and not a.shortcut().isEmpty()
        )
        # 4 layer-stack actions + Add Mask + Add Mask From Selection
        # + Toggle Clipping Mask + Delete Layer = 8 with bindings.
        assert with_shortcut == 8
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Bridge actions
# ---------------------------------------------------------------------------


def test_add_raster_layer_grows_stack(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._layer_menu_bridge   # noqa: SLF001
        before = ws.canvas().document().layer_count
        bridge.add_raster_layer()
        assert ws.canvas().document().layer_count == before + 1
    finally:
        ws.deleteLater()


def test_add_vector_layer_attaches_vector_data(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._layer_menu_bridge   # noqa: SLF001
        bridge.add_vector_layer()
        active = ws.canvas().document().active_layer()
        assert active.vector_data is not None
    finally:
        ws.deleteLater()


def test_duplicate_layer_clones_active(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._layer_menu_bridge   # noqa: SLF001
        before = ws.canvas().document().layer_count
        bridge.duplicate_layer()
        assert ws.canvas().document().layer_count == before + 1
    finally:
        ws.deleteLater()


def test_delete_layer_refuses_last(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._layer_menu_bridge   # noqa: SLF001
        # Workspace seeds with one layer; deleting must be a no-op.
        bridge.delete_layer()
        assert ws.canvas().document().layer_count == 1
    finally:
        ws.deleteLater()


def test_delete_layer_removes_one_when_more_exist(qapp):
    ws = PaintWorkspace()
    try:
        ws.canvas().document().add_layer()
        before = ws.canvas().document().layer_count
        bridge = ws._layer_menu_bridge   # noqa: SLF001
        bridge.delete_layer()
        assert ws.canvas().document().layer_count == before - 1
    finally:
        ws.deleteLater()


def test_merge_down_no_op_when_single_layer(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._layer_menu_bridge   # noqa: SLF001
        before = ws.canvas().document().layer_count
        bridge.merge_down()   # active is bottom layer; no-op
        assert ws.canvas().document().layer_count == before
    finally:
        ws.deleteLater()


def test_workspace_holds_bridge_reference(qapp):
    ws = PaintWorkspace()
    try:
        assert isinstance(ws._layer_menu_bridge, _LayerMenuBridge)  # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# LayerDock — search box + colour-chip + thumbnail
# ---------------------------------------------------------------------------


def test_layer_dock_search_filters_rows(qapp):
    ws = PaintWorkspace()
    try:
        doc = ws.canvas().document()
        doc.add_layer(name="Inks")
        doc.add_layer(name="Flats")
        dock = ws._layer_dock   # noqa: SLF001
        dock._search.setText("Ink")  # noqa: SLF001
        # After filter, only the matching row shows.
        rows = [
            dock._list.item(i).text()  # noqa: SLF001
            for i in range(dock._list.count())  # noqa: SLF001
        ]
        assert any("Inks" in row for row in rows)
        assert not any("Flats" in row for row in rows)
    finally:
        ws.deleteLater()


def test_layer_dock_color_label_shown_as_chip(qapp):
    ws = PaintWorkspace()
    try:
        doc = ws.canvas().document()
        doc.set_layer_color_label(label="red")
        dock = ws._layer_dock   # noqa: SLF001
        dock.refresh()
        first_row_text = dock._list.item(0).text()  # noqa: SLF001
        # The red glyph is prefixed onto the layer name.
        assert "🟥" in first_row_text
    finally:
        ws.deleteLater()


def test_layer_dock_chip_is_stripped_on_inline_rename(qapp):
    """Editing a row inline must not leak the chip glyph back into
    the persisted layer name."""
    from Imervue.paint.dock_panels import _strip_color_chip
    assert _strip_color_chip("🟥 Inks") == "Inks"
    assert _strip_color_chip("Plain") == "Plain"


def test_layer_dock_thumbnail_icon_attached(qapp):
    ws = PaintWorkspace()
    try:
        dock = ws._layer_dock   # noqa: SLF001
        item = dock._list.item(0)  # noqa: SLF001
        # The icon is non-null when the thumbnail render succeeds.
        assert not item.icon().isNull()
    finally:
        ws.deleteLater()


def test_layer_dock_search_clearing_restores_all_rows(qapp):
    ws = PaintWorkspace()
    try:
        doc = ws.canvas().document()
        doc.add_layer(name="Inks")
        doc.add_layer(name="Flats")
        dock = ws._layer_dock   # noqa: SLF001
        dock._search.setText("Ink")  # noqa: SLF001
        filtered_count = dock._list.count()  # noqa: SLF001
        dock._search.setText("")  # noqa: SLF001
        full_count = dock._list.count()  # noqa: SLF001
        assert full_count > filtered_count
    finally:
        ws.deleteLater()


# Pull in unused import so ruff doesn't complain.
_USED_NP = np.array
