"""The shortcut registry's remaps reach the actions that own the keys.

The Paint "Keyboard Shortcuts" dialog saved remaps for 23 actions, but only
fit / actual size / colour swap / colour reset read them, once, when the
workspace was built. Remapping a tool, a layer command, undo / redo or the
brush-size keys did nothing, and Ctrl+[ / Ctrl+] (move layer) and Ctrl+D
(deselect) were advertised without being bound at all.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QWidget

from Imervue.paint import tool_state as ts
from Imervue.paint.shortcut_binding import (
    apply_registry_bindings,
    fixed_shortcut_keys,
    registry_shortcut,
    tag_registry_shortcut,
)
from Imervue.paint.shortcut_registry import DEFAULT_SHORTCUTS, ShortcutRegistry
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    for key in ("paint_state", "paint_shortcuts"):
        user_setting_dict.pop(key, None)
    ts.reset_tool_state()
    yield
    for key in ("paint_state", "paint_shortcuts"):
        user_setting_dict.pop(key, None)
    ts.reset_tool_state()


@pytest.fixture
def host(qapp):
    widget = QWidget()
    yield widget
    widget.deleteLater()


def _keys(obj) -> list[str]:
    if isinstance(obj, QShortcut):
        return [obj.key().toString()]
    return [k.toString() for k in obj.shortcuts()]


# ---------------------------------------------------------------------------
# Tagging and rebinding
# ---------------------------------------------------------------------------


def test_tag_rejects_an_id_the_registry_does_not_know(host):
    action = QAction("x", host)
    assert tag_registry_shortcut(action, "paint.no_such_action") is False
    assert action.objectName() == ""
    assert apply_registry_bindings(host, {"paint.no_such_action": "Y"}) == 0


def test_apply_rebinds_a_tagged_action(host):
    action = QAction("Brush", host)
    action.setShortcut(QKeySequence("B"))
    assert tag_registry_shortcut(action, "paint.tool.brush") is True
    assert apply_registry_bindings(host, {"paint.tool.brush": "Y"}) == 1
    assert _keys(action) == ["Y"]
    # Applying the same binding again changes nothing; remapping again works.
    assert apply_registry_bindings(host, {"paint.tool.brush": "Y"}) == 0
    assert apply_registry_bindings(host, {"paint.tool.brush": "Shift+Y"}) == 1
    assert _keys(action) == ["Shift+Y"]


def test_apply_keeps_an_alias_the_registry_does_not_own(host):
    redo = QAction("Redo", host)
    redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
    tag_registry_shortcut(redo, "paint.edit.redo")
    apply_registry_bindings(host, {"paint.edit.redo": "Ctrl+Alt+Z"})
    assert _keys(redo) == ["Ctrl+Y", "Ctrl+Alt+Z"]


def test_apply_prepends_when_the_default_key_is_missing(host):
    action = QAction("Brush", host)
    action.setShortcut(QKeySequence("F9"))
    tag_registry_shortcut(action, "paint.tool.brush")
    apply_registry_bindings(host, {"paint.tool.brush": "Y"})
    assert _keys(action) == ["Y", "F9"]


def test_apply_skips_untagged_and_empty_bindings(host):
    plain = QAction("Plain", host)
    plain.setObjectName("paint.tool.brush")   # named, but never tagged
    plain.setShortcut(QKeySequence("B"))
    tagged = QAction("Eraser", host)
    tagged.setShortcut(QKeySequence("E"))
    tag_registry_shortcut(tagged, "paint.tool.eraser")
    assert apply_registry_bindings(host, {"paint.tool.brush": "Y", "paint.tool.eraser": ""}) == 0
    assert _keys(plain) == ["B"]
    assert _keys(tagged) == ["E"]


def test_registry_shortcut_starts_on_the_default_key_and_rebinds(host):
    shortcut = registry_shortcut(host, "paint.color.swap")
    assert _keys(shortcut) == ["X"]
    apply_registry_bindings(host, {"paint.color.swap": "Shift+X"})
    assert _keys(shortcut) == ["Shift+X"]


def test_registry_shortcut_rejects_an_unknown_id(host):
    with pytest.raises(KeyError):
        registry_shortcut(host, "paint.no_such_action")


# ---------------------------------------------------------------------------
# PaintWorkspace wiring
# ---------------------------------------------------------------------------


def _tagged(ws) -> dict[str, list]:
    owners: dict[str, list] = {}
    for obj in [*ws.findChildren(QAction), *ws.findChildren(QShortcut)]:
        if obj.property("paint_registry_key") is not None:
            owners.setdefault(obj.objectName(), []).append(obj)
    return owners


@pytest.fixture
def workspace(qapp):
    from Imervue.paint.paint_workspace import PaintWorkspace
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_every_registry_entry_has_exactly_one_owner_on_its_default_key(workspace):
    owners = _tagged(workspace)
    assert sorted(owners) == sorted(e.action_id for e in DEFAULT_SHORTCUTS)
    for entry in DEFAULT_SHORTCUTS:
        (obj,) = owners[entry.action_id]
        assert entry.default_key in _keys(obj), entry.action_id


def test_remap_reaches_menu_actions_shortcuts_and_tooltips(workspace):
    registry = ShortcutRegistry.with_defaults()
    registry.set("paint.tool.brush", "Y")
    registry.set("paint.layer.add", "Ctrl+Alt+L")
    registry.set("paint.brush.size_inc", "F7")
    registry.set("paint.edit.redo", "Ctrl+Alt+Z")
    workspace.apply_shortcut_registry(registry)

    owners = _tagged(workspace)
    assert _keys(owners["paint.tool.brush"][0]) == ["Y"]
    assert _keys(owners["paint.layer.add"][0]) == ["Ctrl+Alt+L"]
    assert _keys(owners["paint.brush.size_inc"][0]) == ["F7"]
    assert _keys(owners["paint.edit.redo"][0]) == ["Ctrl+Y", "Ctrl+Alt+Z"]
    assert workspace._tool_bar.action_for("brush").toolTip().endswith("(Y)")   # noqa: SLF001
    tips = [b.toolTip() for b, _label, _id in workspace._layer_dock._shortcut_buttons]   # noqa: SLF001
    assert any(tip.endswith("(Ctrl+Alt+L)") for tip in tips)


def test_saved_remaps_apply_when_the_workspace_is_built(qapp):
    from Imervue.paint.paint_workspace import PaintWorkspace
    registry = ShortcutRegistry.with_defaults()
    registry.set("paint.tool.eraser", "Shift+F2")
    user_setting_dict["paint_shortcuts"] = registry.to_dict()
    ws = PaintWorkspace()
    try:
        assert _keys(_tagged(ws)["paint.tool.eraser"][0]) == ["Shift+F2"]
    finally:
        ws.deleteLater()


def test_accepting_the_shortcut_dialog_rebinds_at_once(workspace, monkeypatch):
    import Imervue.paint.shortcut_dialog as dialog_mod

    seen = {}

    class _Accepting:
        def __init__(self, registry, parent=None, *, reserved=None):
            registry.set("paint.tool.hand", "Shift+H")
            self._registry = registry
            seen["reserved"] = reserved

        def exec(self):
            return QDialog.DialogCode.Accepted

        def registry(self):
            return self._registry

    monkeypatch.setattr(dialog_mod, "ShortcutDialog", _Accepting)
    workspace._settings_menu_bridge.open_shortcuts()   # noqa: SLF001
    assert _keys(_tagged(workspace)["paint.tool.hand"][0]) == ["Shift+H"]
    # The dialog is told which keys other actions already hold.
    assert seen["reserved"]["Ctrl+S"] == "Save as PSD…"
    assert "B" not in seen["reserved"]   # a registry key, not a reserved one


# ---------------------------------------------------------------------------
# Keys held outside the registry
# ---------------------------------------------------------------------------


def test_fixed_keys_skip_tagged_disabled_and_widget_scoped(host):
    tagged = QAction("Brush", host)
    tagged.setShortcut(QKeySequence("B"))
    tag_registry_shortcut(tagged, "paint.tool.brush")
    save = QAction("&Save", host)
    save.setShortcut(QKeySequence("Ctrl+S"))
    disabled = QAction("Off", host)
    disabled.setShortcut(QKeySequence("F2"))
    disabled.setEnabled(False)
    local = QAction("Local", host)
    local.setShortcut(QKeySequence("F3"))
    local.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    QShortcut(QKeySequence("1"), host)
    scoped = QShortcut(QKeySequence("F4"), host)
    scoped.setContext(Qt.ShortcutContext.WidgetShortcut)
    QAction("No key", host)
    assert fixed_shortcut_keys(host, "other") == {"Ctrl+S": "Save", "1": "other"}


def test_fixed_keys_include_what_the_window_binds(qapp):
    from PySide6.QtWidgets import QMainWindow
    window = QMainWindow()
    try:
        page = QWidget()
        window.setCentralWidget(page)
        QShortcut(QKeySequence("Ctrl+L"), window)
        window.menuBar().addMenu("File").addAction("Quit").setShortcut(QKeySequence("Ctrl+Q"))
        assert fixed_shortcut_keys(page, "other") == {"Ctrl+L": "other", "Ctrl+Q": "Quit"}
    finally:
        window.deleteLater()


def test_new_layer_and_deselect_shortcuts_drive_the_document(workspace):
    owners = _tagged(workspace)
    document = workspace._canvas.document()   # noqa: SLF001
    calls = []
    document.move_active_layer = lambda *, up: calls.append(up)
    owners["paint.layer.move_up"][0].activated.emit()
    owners["paint.layer.move_down"][0].activated.emit()
    assert calls == [True, False]
    cleared = []
    document.set_selection = cleared.append
    owners["paint.edit.deselect"][0].activated.emit()
    assert cleared == [None]
