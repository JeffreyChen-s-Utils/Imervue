"""A motion's own ``loop`` flag decides whether it loops.

Every motion looped, whatever its flag: the player started with looping on
and nothing read the flag, so a tap reaction (``tap_head``, loop off) on the
bundled March 7th rig repeated forever in the Puppet tab and on the Desktop
Pet. These use a stand-in canvas (the real one is a ``QOpenGLWidget``).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from Imervue.puppet.document import Motion, PuppetDocument
from Imervue.puppet.motion_dock import MotionDock
from Imervue.puppet.motion_player import MotionPlayer


class _Canvas(QObject):
    """What the player and the Motions dock read from the canvas."""

    document_loaded = Signal()

    def __init__(self, document=None):
        super().__init__()
        self._document = document
        self.values: dict[str, float] = {}

    def document(self):
        return self._document

    def parameter_values(self):
        return dict(self.values)

    def set_parameter_values(self, values):
        self.values.update(values)

    def set_parameter(self, param_id, value):
        self.values[param_id] = value


def _doc():
    doc = PuppetDocument(size=(8, 8))
    doc.motions = [Motion(name="idle", duration=1.0, loop=True),
                   Motion(name="tap", duration=1.0, loop=False)]
    return doc


def test_binding_a_motion_takes_its_loop_flag(qapp):
    player = MotionPlayer(_Canvas())
    try:
        idle, tap = _doc().motions
        player.set_motion(tap)
        assert player.loop() is False
        player.set_motion(idle)
        assert player.loop() is True
        player.set_motion(None)
        assert player.loop() is True          # nothing bound: left as it was
    finally:
        player.deleteLater()


def test_toggling_loop_changes_the_bound_motions_flag(qapp):
    player = MotionPlayer(_Canvas())
    try:
        tap = _doc().motions[1]
        player.set_motion(tap)
        player.set_loop(True)
        assert tap.loop is True               # kept when the rig is saved
        player.set_motion(None)
        player.set_loop(False)                # nothing bound: nothing to change
        assert tap.loop is True
    finally:
        player.deleteLater()


def test_the_loop_box_shows_the_picked_motions_flag(qapp):
    canvas = _Canvas(_doc())
    dock = MotionDock(canvas)
    try:
        box = dock._loop_box  # noqa: SLF001
        assert dock.select_motion("tap")
        assert box.isChecked() is False
        assert canvas.document().motions[1].loop is False   # showing it did not set it
        assert dock.select_motion("idle")
        assert box.isChecked() is True
        box.setChecked(False)
        assert canvas.document().motions[0].loop is False
        assert dock.player().loop() is False
    finally:
        dock.player().stop()
        dock.deleteLater()
