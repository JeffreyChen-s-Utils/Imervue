"""Contract: the layers dialog's list rows, editor sync, edits and reordering.

Pins the default parameters each kind starts with, the one-line row summary,
which editor page and parameter text a selected layer shows, how each editor
control writes back to the layer (and refreshes its row), the colour / file
pickers per kind, add / remove / move selection rules and the serialised stack
emitted on Apply.
"""
from __future__ import annotations

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QFileDialog

from Imervue.gui.layers_dialog import (
    LayersDialog,
    _describe_layer,
    add_default_layer,
    move_layer_down,
    move_layer_up,
)
from Imervue.image.layers import MAX_LAYERS, Layer, layers_from_dict_list
from Imervue.image.recipe import Recipe

_TEXT_DEFAULTS = {
    "text": "",
    "corner": "bottom-right",
    "color": [255, 255, 255],
    "font_fraction": 0.035,
    "shadow": True,
}


def _dialog(layers: list[dict] | None = None) -> LayersDialog:
    recipe = Recipe()
    if layers is not None:
        recipe.extra["layers"] = layers
    return LayersDialog(recipe, None)


def _select_combo(combo, value) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return
    raise AssertionError(value)


def _rows(dlg: LayersDialog) -> list[str]:
    return [dlg._list.item(i).text() for i in range(dlg._list.count())]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "params"),
    [
        ("text", _TEXT_DEFAULTS),
        ("image", {"path": ""}),
        ("lut", {"path": "", "intensity": 1.0}),
    ],
)
def test_add_default_layer_params_per_kind(kind, params):
    layers: list[Layer] = []
    layer = add_default_layer(layers, kind)
    assert layers == [layer]
    assert layer.kind == kind
    assert layer.enabled is True
    assert layer.opacity == pytest.approx(1.0)
    assert layer.blend_mode == "normal"
    assert layer.params == params


def test_add_default_layer_defaults_to_text_kind():
    layers: list[Layer] = []
    assert add_default_layer(layers).params == _TEXT_DEFAULTS


def test_add_default_layer_one_below_cap_still_adds():
    layers = [Layer() for _ in range(MAX_LAYERS - 1)]
    assert add_default_layer(layers, "image") is not None
    assert len(layers) == MAX_LAYERS


@pytest.mark.parametrize("idx", [-1, 2, 5])
def test_move_layer_up_out_of_range_is_noop(idx):
    layers = [Layer(kind="text"), Layer(kind="image")]
    assert move_layer_up(layers, idx) == idx
    assert [lyr.kind for lyr in layers] == ["text", "image"]


@pytest.mark.parametrize("idx", [-1, 2, 5])
def test_move_layer_down_out_of_range_is_noop(idx):
    layers = [Layer(kind="text"), Layer(kind="image")]
    assert move_layer_down(layers, idx) == idx
    assert [lyr.kind for lyr in layers] == ["text", "image"]


def test_move_helpers_on_empty_list():
    assert move_layer_up([], 0) == 0
    assert move_layer_down([], 0) == 0


@pytest.mark.parametrize(
    ("layer", "expected"),
    [
        (Layer(kind="text", params={"text": "hi"}), "Text • normal • 100% — hi"),
        (Layer(kind="text", params={}), "Text • normal • 100% — (empty)"),
        (
            Layer(kind="image", opacity=0.5, blend_mode="screen",
                  params={"path": "C:\\pics\\a.png"}),
            "Image • screen • 50% — a.png",
        ),
        (Layer(kind="lut", params={"path": "/luts/film.cube"}),
         "Lut • normal • 100% — film.cube"),
        (Layer(kind="lut", params={"path": ""}), "Lut • normal • 100% — (none)"),
        (Layer(kind="image", params={"path": "dir/"}), "Image • normal • 100% — dir/"),
        (Layer(kind="text", enabled=False, params={"text": "x"}),
         "Text • normal • 100% — x [off]"),
        (Layer(kind="other", opacity=0.256), "Other • normal • 25% — "),
    ],
)
def test_describe_layer_rows(layer, expected):
    assert _describe_layer(layer) == expected


# ---------------------------------------------------------------------------
# Dialog: construction and selection sync
# ---------------------------------------------------------------------------


def test_empty_dialog_shows_hint_page(qapp):
    dlg = _dialog()
    assert dlg._list.count() == 0
    assert dlg._list.currentRow() == -1
    assert dlg._editor_stack.currentIndex() == 0
    assert dlg._current_layer() is None


def test_loaded_dialog_selects_first_row_and_syncs_form(qapp):
    dlg = _dialog([
        {"kind": "image", "opacity": 0.4, "blend_mode": "multiply",
         "params": {"path": "/x/y.png"}},
        {"kind": "text", "params": {"text": "second"}},
    ])
    assert dlg._list.currentRow() == 0
    assert dlg._editor_stack.currentIndex() == 1
    assert dlg._kind_combo.currentData() == "image"
    assert dlg._blend_combo.currentData() == "multiply"
    assert dlg._opacity_spin.value() == pytest.approx(0.4)
    assert dlg._param_field.text() == "/x/y.png"
    assert dlg._param_button.text() == "Browse…"
    assert _rows(dlg) == [
        "Image • multiply • 40% — y.png",
        "Text • normal • 100% — second",
    ]


def test_selecting_text_row_shows_colour_button(qapp):
    dlg = _dialog([
        {"kind": "lut", "params": {"path": "a.cube"}},
        {"kind": "text", "params": {"text": "hello"}},
    ])
    dlg._list.setCurrentRow(1)
    assert dlg._kind_combo.currentData() == "text"
    assert dlg._param_field.text() == "hello"
    assert dlg._param_button.text() == "Color"


def test_sync_param_for_unknown_kind_clears_field(qapp):
    dlg = _dialog([{"kind": "text", "params": {"text": "hello"}}])
    layer = dlg._layers[0]
    layer.kind = "mystery"
    dlg._sync_param_from_layer(layer)
    assert dlg._param_field.text() == ""
    assert dlg._param_button.text() == "…"


def test_form_sync_does_not_write_back_to_layer(qapp):
    dlg = _dialog([
        {"kind": "text", "params": {"text": "a"}},
        {"kind": "lut", "opacity": 0.3, "params": {"path": "b.cube", "intensity": 0.5}},
    ])
    dlg._list.setCurrentRow(1)
    assert dlg._layers[0].params == {"text": "a"}
    assert dlg._layers[1].params == {"path": "b.cube", "intensity": 0.5}
    assert dlg._layers[1].opacity == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Dialog: editor -> model
# ---------------------------------------------------------------------------


def test_kind_change_resets_params_and_row(qapp):
    dlg = _dialog([{"kind": "text", "params": {"text": "keep?"}}])
    _select_combo(dlg._kind_combo, "lut")
    layer = dlg._layers[0]
    assert layer.kind == "lut"
    assert layer.params == {"path": "", "intensity": 1.0}
    assert dlg._param_field.text() == ""
    assert dlg._param_button.text() == "Browse…"
    assert _rows(dlg) == ["Lut • normal • 100% — (none)"]


def test_kind_change_to_same_kind_keeps_params(qapp):
    dlg = _dialog([{"kind": "image", "params": {"path": "p.png"}}])
    dlg._on_kind_changed(0)
    assert dlg._layers[0].params == {"path": "p.png"}


def test_editor_handlers_without_selection_are_noops(qapp):
    dlg = _dialog()
    dlg._on_kind_changed(0)
    dlg._on_opacity_changed(0.5)
    dlg._on_blend_changed(0)
    dlg._on_param_text_changed()
    dlg._on_param_button_clicked()
    dlg._refresh_current_row_label()
    assert dlg._layers == []
    assert dlg._list.count() == 0


def test_opacity_change_updates_layer_and_row(qapp):
    dlg = _dialog([{"kind": "text", "params": {"text": "t"}}])
    dlg._opacity_spin.setValue(0.25)
    assert dlg._layers[0].opacity == pytest.approx(0.25)
    assert _rows(dlg) == ["Text • normal • 25% — t"]


def test_blend_change_updates_layer_and_row(qapp):
    dlg = _dialog([{"kind": "text", "params": {"text": "t"}}])
    _select_combo(dlg._blend_combo, "overlay")
    assert dlg._layers[0].blend_mode == "overlay"
    assert _rows(dlg) == ["Text • overlay • 100% — t"]


@pytest.mark.parametrize(
    ("kind", "key", "row"),
    [
        ("text", "text", "Text • normal • 100% — new value"),
        ("image", "path", "Image • normal • 100% — new value"),
        ("lut", "path", "Lut • normal • 100% — new value"),
    ],
)
def test_param_text_writes_kind_key(qapp, kind, key, row):
    dlg = _dialog([{"kind": kind, "params": {}}])
    dlg._param_field.setText("new value")
    dlg._on_param_text_changed()
    assert dlg._layers[0].params == {key: "new value"}
    assert _rows(dlg) == [row]


def test_param_text_for_unknown_kind_leaves_params(qapp):
    dlg = _dialog([{"kind": "text", "params": {"text": "t"}}])
    dlg._layers[0].kind = "mystery"
    dlg._param_field.setText("ignored")
    dlg._on_param_text_changed()
    assert dlg._layers[0].params == {"text": "t"}
    assert _rows(dlg) == ["Mystery • normal • 100% — "]


def test_row_label_refresh_tracks_current_row_only(qapp):
    dlg = _dialog([
        {"kind": "text", "params": {"text": "a"}},
        {"kind": "text", "params": {"text": "b"}},
    ])
    dlg._list.setCurrentRow(1)
    dlg._layers[0].params["text"] = "changed-0"
    dlg._layers[1].params["text"] = "changed-1"
    dlg._refresh_current_row_label()
    assert _rows(dlg) == [
        "Text • normal • 100% — a",
        "Text • normal • 100% — changed-1",
    ]


# ---------------------------------------------------------------------------
# Dialog: pickers
# ---------------------------------------------------------------------------


def test_colour_pick_stores_rgb(qapp, monkeypatch):
    seen = {}

    def fake_get_color(initial, parent):
        seen["initial"] = (initial.red(), initial.green(), initial.blue())
        seen["parent"] = parent
        return QColor(10, 20, 30)

    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(fake_get_color))
    dlg = _dialog([{"kind": "text", "params": {"text": "t", "color": [1, 2, 3]}}])
    dlg._on_param_button_clicked()
    assert seen == {"initial": (1, 2, 3), "parent": dlg}
    assert dlg._layers[0].params["color"] == [10, 20, 30]


def test_colour_pick_defaults_initial_to_white_and_ignores_cancel(qapp, monkeypatch):
    seen = {}

    def fake_get_color(initial, _parent):
        seen["initial"] = (initial.red(), initial.green(), initial.blue())
        return QColor()

    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(fake_get_color))
    dlg = _dialog([{"kind": "text", "params": {"text": "t"}}])
    dlg._on_param_button_clicked()
    assert seen["initial"] == (255, 255, 255)
    assert "color" not in dlg._layers[0].params


@pytest.mark.parametrize(
    ("kind", "title", "filter_part"),
    [("image", "Choose image", "*.png"), ("lut", "Choose LUT", "Cube LUT (*.cube)")],
)
def test_file_pick_stores_path(qapp, monkeypatch, kind, title, filter_part):
    seen = {}

    def fake_open(parent, caption, directory, filt):
        seen.update(parent=parent, caption=caption, directory=directory, filt=filt)
        return "/chosen/pick.file", ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(fake_open))
    dlg = _dialog([{"kind": kind, "params": {"path": "old"}}])
    dlg._on_param_button_clicked()
    assert seen["parent"] is dlg
    assert seen["caption"] == title
    assert seen["directory"] == ""
    assert filter_part in seen["filt"]
    assert dlg._layers[0].params["path"] == "/chosen/pick.file"
    assert dlg._param_field.text() == "/chosen/pick.file"
    assert _rows(dlg)[0].endswith("— pick.file")


@pytest.mark.parametrize("kind", ["image", "lut"])
def test_file_pick_cancel_keeps_path(qapp, monkeypatch, kind):
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *_a: ("", "")),
    )
    dlg = _dialog([{"kind": kind, "params": {"path": "old.png"}}])
    dlg._on_param_button_clicked()
    assert dlg._layers[0].params["path"] == "old.png"
    assert dlg._param_field.text() == "old.png"


def test_param_button_for_unknown_kind_opens_nothing(qapp, monkeypatch):
    def boom(*_a):
        raise AssertionError("no picker expected")

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(boom))
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(boom))
    dlg = _dialog([{"kind": "text", "params": {}}])
    dlg._layers[0].kind = "mystery"
    dlg._on_param_button_clicked()
    assert dlg._layers[0].params == {}


# ---------------------------------------------------------------------------
# Dialog: add / remove / reorder / apply
# ---------------------------------------------------------------------------


def test_add_layer_selects_new_row_and_stops_at_cap(qapp):
    dlg = _dialog()
    dlg._add_layer()
    assert dlg._list.currentRow() == 0
    assert dlg._editor_stack.currentIndex() == 1
    for _ in range(MAX_LAYERS + 2):
        dlg._add_layer()
    assert len(dlg._layers) == MAX_LAYERS
    assert dlg._list.count() == MAX_LAYERS
    assert dlg._list.currentRow() == MAX_LAYERS - 1


def test_remove_layer_selection_rules(qapp):
    dlg = _dialog([
        {"kind": "text", "params": {"text": "a"}},
        {"kind": "text", "params": {"text": "b"}},
        {"kind": "text", "params": {"text": "c"}},
    ])
    dlg._list.setCurrentRow(2)
    dlg._remove_layer()
    assert [lyr.params["text"] for lyr in dlg._layers] == ["a", "b"]
    assert dlg._list.currentRow() == 1
    dlg._list.setCurrentRow(0)
    dlg._remove_layer()
    assert [lyr.params["text"] for lyr in dlg._layers] == ["b"]
    assert dlg._list.currentRow() == 0
    dlg._remove_layer()
    assert dlg._layers == []
    assert dlg._list.count() == 0
    assert dlg._editor_stack.currentIndex() == 0
    dlg._remove_layer()
    assert dlg._layers == []


def test_move_up_and_down_follow_selection(qapp):
    dlg = _dialog([
        {"kind": "text", "params": {"text": "a"}},
        {"kind": "text", "params": {"text": "b"}},
    ])
    dlg._move_up()
    assert _rows(dlg)[0].endswith("— a")
    assert dlg._list.currentRow() == 0
    dlg._move_down()
    assert [lyr.params["text"] for lyr in dlg._layers] == ["b", "a"]
    assert dlg._list.currentRow() == 1
    assert _rows(dlg) == ["Text • normal • 100% — b", "Text • normal • 100% — a"]
    dlg._move_down()
    assert dlg._list.currentRow() == 1
    dlg._move_up()
    assert [lyr.params["text"] for lyr in dlg._layers] == ["a", "b"]
    assert dlg._list.currentRow() == 0


def test_apply_round_trips_edited_stack(qapp):
    stored = [
        {"kind": "image", "enabled": False, "opacity": 0.6, "blend_mode": "screen",
         "params": {"path": "a.png"}},
        {"kind": "lut", "enabled": True, "opacity": 1.0, "blend_mode": "normal",
         "params": {"path": "b.cube", "intensity": 0.7}},
    ]
    dlg = _dialog(stored)
    emitted = []
    dlg.layers_changed.connect(emitted.append)
    dlg._apply()
    assert dlg.result() == LayersDialog.DialogCode.Accepted
    assert emitted == [stored]
    again = layers_from_dict_list(emitted[0])
    assert [lyr.to_dict() for lyr in again] == stored
