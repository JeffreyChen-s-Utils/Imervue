"""The Desktop Pet's right-click Pose submenu picks each pose group's shown member.

Stand-ins for the pet and its canvas, no PetWindow (a QOpenGLWidget), so this
runs on headless CI.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QMenu

from Imervue.desktop_pet.pet_context_menu import _build_pose_submenu
from Imervue.puppet.document import PoseGroup, PuppetDocument


def _tr(_key, fallback):
    return fallback


def _pet(groups, active=None, names=None):
    document = PuppetDocument(size=(8, 8))
    document.pose_groups = groups
    document.display_names = dict(names or {})
    picked = []
    canvas = SimpleNamespace(
        active_pose=lambda: dict(active or {}),
        set_pose_active=lambda group, member: picked.append((group, member)))
    return SimpleNamespace(document=lambda: document, canvas=lambda: canvas), picked


def _submenus(menu):
    return menu.actions()[0].menu().actions()


def test_each_group_lists_its_members_and_checks_the_shown_one(qapp):
    pet, picked = _pet(
        [PoseGroup("hand", ["open", "fist"]), PoseGroup("hat", ["on", "off"]),
         PoseGroup("empty", [])],
        active={"hat": "off"}, names={"hand": "Right hand"})
    menu = QMenu()
    try:
        _build_pose_submenu(pet, menu, _tr)
        groups = _submenus(menu)
        assert [a.text() for a in groups] == ["Right hand", "hat"]
        hand, hat = (g.menu().actions() for g in groups)
        assert [(a.text(), a.isChecked()) for a in hand] == [("open", True), ("fist", False)]
        assert [(a.text(), a.isChecked()) for a in hat] == [("on", False), ("off", True)]
        hand[1].trigger()
        assert picked == [("hand", "fist")]
    finally:
        menu.deleteLater()


def test_a_rig_without_pose_groups_disables_the_submenu(qapp):
    for document_groups in ([], [PoseGroup("empty", [])]):
        pet, _picked = _pet(document_groups)
        menu = QMenu()
        try:
            _build_pose_submenu(pet, menu, _tr)
            assert not menu.actions()[0].menu().isEnabled()
        finally:
            menu.deleteLater()


def test_no_rig_disables_the_submenu(qapp):
    pet = SimpleNamespace(document=lambda: None, canvas=lambda: None)
    menu = QMenu()
    try:
        _build_pose_submenu(pet, menu, _tr)
        assert not menu.actions()[0].menu().isEnabled()
    finally:
        menu.deleteLater()
