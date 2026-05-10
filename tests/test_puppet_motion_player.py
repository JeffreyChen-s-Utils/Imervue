"""Qt-smoke for MotionPlayer + MotionDock — start / stop / loop /
seek behaviour without a wall-clock dependency.
"""
from __future__ import annotations

import pytest

from puppet.canvas import PuppetCanvas
from puppet.document import (
    Deformer,
    Drawable,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    PuppetDocument,
)
from puppet.motion_dock import MotionDock
from puppet.motion_player import MotionPlayer


def _doc_with_motion() -> PuppetDocument:
    doc = PuppetDocument(size=(64, 64))
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
            draw_order=0,
        ),
    ]
    doc.deformers = [
        Deformer(
            id="rot", type="rotation", parent=None, drawables=["x"],
            form={"anchor": [32.0, 32.0], "angle": 0.0},
        ),
    ]
    doc.parameters = [
        Parameter(id="ParamX", min=-1.0, max=1.0, default=0.0, keys=[]),
    ]
    doc.motions = [
        Motion(
            name="idle", duration=1.0, loop=True,
            tracks=[
                MotionTrack(
                    param_id="ParamX",
                    segments=[
                        MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.0, 1.0)),
                    ],
                ),
            ],
        ),
    ]
    return doc


# ---------------------------------------------------------------------------
# MotionPlayer
# ---------------------------------------------------------------------------


def test_player_seek_pushes_parameter_into_canvas(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion())
    player = MotionPlayer(canvas)
    player.set_motion(canvas.document().motions[0])
    try:
        player.seek(0.5)
        # ParamX at t=0.5 along linear 0..1 → 0.5
        assert canvas.parameter_values()["ParamX"] == pytest.approx(0.5, abs=1e-3)
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_player_step_advances_time(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion())
    player = MotionPlayer(canvas)
    player.set_motion(canvas.document().motions[0])
    try:
        player.step(0.25)
        assert player.elapsed() == pytest.approx(0.25)
        player.step(0.25)
        assert player.elapsed() == pytest.approx(0.5)
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_player_loop_wraps_time(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion())
    player = MotionPlayer(canvas)
    motion = canvas.document().motions[0]
    motion.loop = True
    player.set_motion(motion)
    player.set_loop(True)
    try:
        player.seek(1.5)   # > duration (1.0), should wrap to 0.5
        # Loop wraps in the sampler, not the player's elapsed counter,
        # so canvas value reflects the wrapped sample.
        assert canvas.parameter_values()["ParamX"] == pytest.approx(0.5, abs=1e-3)
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_player_no_loop_clamps_at_duration(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion())
    player = MotionPlayer(canvas)
    motion = canvas.document().motions[0]
    motion.loop = False
    player.set_motion(motion)
    player.set_loop(False)
    try:
        player.seek(5.0)
        assert player.elapsed() == pytest.approx(motion.duration)
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_player_state_changed_signal_fires(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion())
    player = MotionPlayer(canvas)
    captured = []
    player.state_changed.connect(lambda: captured.append(True))
    try:
        player.set_motion(canvas.document().motions[0])
        player.set_loop(False)
        player.seek(0.5)
        assert len(captured) >= 3
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_player_set_motion_none_stops_playback(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion())
    player = MotionPlayer(canvas)
    try:
        player.set_motion(canvas.document().motions[0])
        player.play()
        player.set_motion(None)
        assert not player.is_playing()
    finally:
        player.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# MotionDock
# ---------------------------------------------------------------------------


def test_dock_lists_motions_from_document(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion())
    dock = MotionDock(canvas)
    try:
        items = [dock._list.item(i).text() for i in range(dock._list.count())]   # noqa: SLF001
        assert items == ["idle"]
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_shows_empty_state_for_motionless_doc(qapp):
    from PySide6.QtCore import Qt as _Qt

    canvas = PuppetCanvas()
    doc = _doc_with_motion()
    doc.motions = []
    canvas.load_document(doc)
    dock = MotionDock(canvas)
    try:
        item = dock._list.item(0)   # noqa: SLF001
        assert "(" in item.text()   # placeholder text starts with parenthesis
        # Placeholder is disabled so the user can't activate it
        assert not bool(item.flags() & _Qt.ItemFlag.ItemIsEnabled)
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_select_motion_drives_player(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion())
    dock = MotionDock(canvas)
    try:
        assert dock.select_motion("idle") is True
        assert dock.player().motion() is not None
        assert dock.player().motion().name == "idle"
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_single_click_binds_and_plays(qapp):
    """Clicking a motion in the list (not double-clicking) must bind
    the motion to the player and start playback — that's the UX
    users instinctively reach for."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion())
    dock = MotionDock(canvas)
    try:
        item = dock._list.item(0)   # noqa: SLF001
        # Drive the slot directly — itemClicked emits with the QListWidgetItem.
        dock._on_item_clicked(item)   # noqa: SLF001
        assert dock.player().motion() is not None
        assert dock.player().is_playing() is True
        dock.player().stop()
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_single_click_ignores_disabled_placeholder(qapp):
    """The empty-state placeholder is disabled — clicking it must not
    bind anything to the player."""
    canvas = PuppetCanvas()
    doc = _doc_with_motion()
    doc.motions = []
    canvas.load_document(doc)
    dock = MotionDock(canvas)
    try:
        placeholder = dock._list.item(0)   # noqa: SLF001
        dock._on_item_clicked(placeholder)   # noqa: SLF001
        assert dock.player().motion() is None
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_select_unknown_motion_returns_false(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion())
    dock = MotionDock(canvas)
    try:
        assert dock.select_motion("ghost") is False
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_rebuilds_when_document_swaps(qapp):
    canvas = PuppetCanvas()
    dock = MotionDock(canvas)
    try:
        canvas.load_document(_doc_with_motion())
        # Triggers document_loaded → _rebuild_motions
        items = [dock._list.item(i).text() for i in range(dock._list.count())]   # noqa: SLF001
        assert items == ["idle"]
    finally:
        dock.deleteLater()
        canvas.deleteLater()
