"""Tests for ``PuppetMenusMixin._build_actions`` on a GL-free host.

Pins every action the puppet workspace creates: its label, whether it is
checkable, and which workspace slot it drives (``triggered`` for plain
actions, ``toggled`` for checkable ones), so restructuring the builder cannot
drop, relabel or rewire an action.
"""
from __future__ import annotations

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from Imervue.puppet.workspace_menus import PuppetMenusMixin

# (attribute, label, checkable, slot)
_ACTIONS = [
    ("_open_action", "Open Puppet…", False, "_open_via_dialog"),
    ("_save_action", "Save As…", False, "_save_via_dialog"),
    ("_import_png_action", "Import PNG…", False, "_import_png_via_dialog"),
    ("_import_psd_action", "Import PSD…", False, "_import_psd_via_dialog"),
    ("_import_cubism_action", "Import Cubism…", False, "_import_cubism_via_dialog"),
    ("_install_deps_action", "Install dependencies…", False, "_install_all_optional_deps"),
    ("_add_rot_action", "Add Rotation Deformer", False, "_add_rotation_deformer"),
    ("_add_warp_action", "Add Warp Deformer", False, "_add_warp_deformer"),
    ("_add_param_action", "Add Parameter", False, "_add_parameter"),
    ("_mirror_action", "Mirror drawable…", False, "_mirror_drawable_via_dialog"),
    ("_edit_motion_action", "Edit motion…", False, "_edit_active_motion"),
    ("_mesh_edit_toggle", "Edit mesh", True, "_toggle_mesh_edit"),
    ("_drag_toggle", "Drag-track head", True, "_toggle_drag"),
    ("_blink_toggle", "Auto-blink", True, "_toggle_blink"),
    ("_lipsync_toggle", "Mic lip-sync", True, "_toggle_lipsync"),
    ("_webcam_toggle", "Webcam tracking", True, "_toggle_webcam"),
    ("_idle_toggle", "Auto idle", True, "_toggle_idle"),
    ("_idle_motion_toggle", "Idle motions", True, "_toggle_idle_motions"),
    ("_capture_action", "Capture frame…", False, "_capture_via_dialog"),
    ("_record_action", "Record…", True, "_toggle_recording"),
    ("_motion_record_toggle", "Record motion", True, "_toggle_motion_record"),
    ("_batch_export_action", "Export all motions…", False, "_batch_export_via_dialog"),
    ("_virtual_camera_toggle", "Virtual camera", True, "_toggle_virtual_camera"),
    ("_ndi_toggle", "NDI output", True, "_toggle_ndi"),
    ("_vts_toggle", "VTS API", True, "_toggle_vts_api"),
    ("_validate_action", "Validate", False, "_run_validator"),
    ("_fit_action", "Fit to Window", False, "_canvas_reset_view"),
    ("_reset_action", "Reset to rest", False, "_reset_to_rest"),
]
_MENUS = [
    ("_recent_menu", "Recent", "_rebuild_recent_menu"),
    ("_examples_menu", "Examples", "_rebuild_examples_menu"),
]
_SLOTS = {slot for *_x, slot in _ACTIONS} | {slot for *_x, slot in _MENUS}


class _Host(PuppetMenusMixin, QWidget):
    """Records every workspace slot call instead of doing the work."""

    def __init__(self):
        super().__init__()
        self.calls: list[tuple] = []
        for slot in _SLOTS:
            setattr(self, slot, lambda *args, s=slot: self.calls.append((s, *args)))


@pytest.fixture
def host(qapp, monkeypatch):
    from Imervue.puppet import workspace_menus
    monkeypatch.setattr(workspace_menus.language_wrapper, "language_word_dict", {})
    widget = _Host()
    widget._build_actions()  # noqa: SLF001
    yield widget
    widget.deleteLater()


def test_every_action_label_and_checkable(host):
    for attr, label, checkable, _slot in _ACTIONS:
        action = getattr(host, attr)
        assert isinstance(action, QAction), attr
        assert action.parent() is host, attr
        assert (action.text(), action.isCheckable()) == (label, checkable), attr


def test_actions_are_distinct_objects(host):
    assert len({id(getattr(host, attr)) for attr, *_x in _ACTIONS}) == len(_ACTIONS)


@pytest.mark.parametrize(("attr", "checkable", "slot"),
                         [(a, c, s) for a, _l, c, s in _ACTIONS])
def test_action_drives_its_slot(host, attr, checkable, slot):
    action = getattr(host, attr)
    action.trigger()
    expected = (slot, True) if checkable else (slot,)
    assert host.calls == [expected]


def test_checkable_action_reports_both_toggle_directions(host):
    host._drag_toggle.trigger()  # noqa: SLF001
    host._drag_toggle.trigger()  # noqa: SLF001
    assert host.calls == [("_toggle_drag", True), ("_toggle_drag", False)]


@pytest.mark.parametrize(("attr", "title", "slot"), _MENUS)
def test_submenus_rebuild_before_showing(host, attr, title, slot):
    menu = getattr(host, attr)
    assert isinstance(menu, QMenu)
    assert menu.title() == title
    assert menu.parent() is host
    menu.aboutToShow.emit()
    assert host.calls == [(slot,)]


def test_labels_come_from_the_language_dict(qapp, monkeypatch):
    from Imervue.puppet import workspace_menus
    monkeypatch.setattr(workspace_menus.language_wrapper, "language_word_dict",
                        {"puppet_open": "OPEN", "puppet_recent": "RECENT"})
    widget = _Host()
    try:
        widget._build_actions()  # noqa: SLF001
        assert widget._open_action.text() == "OPEN"  # noqa: SLF001
        assert widget._recent_menu.title() == "RECENT"  # noqa: SLF001
        assert widget._save_action.text() == "Save As…"  # noqa: SLF001
    finally:
        widget.deleteLater()
