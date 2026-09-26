"""The Puppet workspace's Pose dock: pick which member of each pose group shows.

Pose groups could not be switched at all: ``set_pose_active`` was only called
by Reset to rest. The dock runs against a small stand-in canvas (the real
``PuppetCanvas`` is a ``QOpenGLWidget``, skipped on headless CI).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from Imervue.puppet.document import PoseGroup, PuppetDocument
from Imervue.puppet.pose_dock import PoseDock


class _Canvas(QObject):
    """The canvas surface the dock uses, with ``set_pose_active``'s checks."""

    document_loaded = Signal()
    pose_changed = Signal(str, str)

    def __init__(self, document=None):
        super().__init__()
        self._document = document
        self._active: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []

    def document(self):
        return self._document

    def active_pose(self):
        return dict(self._active)

    def set_pose_active(self, group_id, member):
        self.calls.append((group_id, member))
        group = next(g for g in self._document.pose_groups if g.id == group_id)
        if member not in group.drawables:
            return False
        self._active[group_id] = member
        self.pose_changed.emit(group_id, member)
        return True

    def load(self, document):
        self._document = document
        self._active = {}
        self.document_loaded.emit()


def _doc():
    doc = PuppetDocument(size=(64, 64))
    doc.pose_groups = [
        PoseGroup("hand", ["hand_open", "hand_fist", "hand_peace"]),
        PoseGroup("hat", ["hat_on", "hat_off"]),
        PoseGroup("unused", []),
    ]
    doc.display_names = {"hand": "Right hand"}
    return doc


def _dock(qapp, document=None):
    canvas = _Canvas(document)
    return PoseDock(canvas), canvas


def test_no_document_shows_the_empty_state(qapp):
    dock, _canvas = _dock(qapp)
    try:
        assert dock.combos() == {}
    finally:
        dock.deleteLater()


def test_each_group_with_members_gets_a_picker_on_its_first_member(qapp):
    dock, canvas = _dock(qapp)
    try:
        canvas.load(_doc())
        combos = dock.combos()
        assert list(combos) == ["hand", "hat"]      # an empty group has nothing to pick
        hand = combos["hand"]
        assert [hand.itemText(i) for i in range(hand.count())] == [
            "hand_open", "hand_fist", "hand_peace"]
        assert hand.currentText() == "hand_open"
        assert canvas.calls == []                    # building the list picks nothing
    finally:
        dock.deleteLater()


def test_a_group_is_labelled_with_its_display_name(qapp):
    from PySide6.QtWidgets import QLabel
    dock, canvas = _dock(qapp)
    try:
        canvas.load(_doc())
        labels = {label.text() for label in dock.findChildren(QLabel)}
        assert {"Right hand", "hat"} <= labels
    finally:
        dock.deleteLater()


def test_picking_a_member_shows_it(qapp):
    dock, canvas = _dock(qapp)
    try:
        canvas.load(_doc())
        dock.combos()["hand"].setCurrentText("hand_peace")
        assert canvas.calls == [("hand", "hand_peace")]
        assert canvas.active_pose() == {"hand": "hand_peace"}
    finally:
        dock.deleteLater()


def test_the_picker_follows_a_pose_set_elsewhere(qapp):
    """Reset to rest puts each group back on its first member through the canvas."""
    dock, canvas = _dock(qapp)
    try:
        canvas.load(_doc())
        dock.combos()["hat"].setCurrentText("hat_off")
        canvas.calls.clear()
        canvas.set_pose_active("hat", "hat_on")
        assert dock.combos()["hat"].currentText() == "hat_on"
        assert canvas.calls == [("hat", "hat_on")]   # not applied a second time
        canvas.pose_changed.emit("gone", "x")        # a group the dock does not list
    finally:
        dock.deleteLater()


def test_a_rig_opened_with_a_pose_already_set_shows_it(qapp):
    doc = _doc()
    canvas = _Canvas(doc)
    canvas._active = {"hand": "hand_fist"}  # noqa: SLF001
    dock = PoseDock(canvas)
    try:
        assert dock.combos()["hand"].currentText() == "hand_fist"
        assert dock.combos()["hat"].currentText() == "hat_on"
    finally:
        dock.deleteLater()


def test_loading_another_rig_rebuilds_the_list(qapp):
    dock, canvas = _dock(qapp)
    try:
        canvas.load(_doc())
        canvas.load(PuppetDocument(size=(8, 8)))
        assert dock.combos() == {}
        canvas.load(_doc())
        assert list(dock.combos()) == ["hand", "hat"]
    finally:
        dock.deleteLater()
