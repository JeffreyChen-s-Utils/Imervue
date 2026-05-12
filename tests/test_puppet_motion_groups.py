"""Tests for the motion-group feature: Motion.group field, Cubism
import preserving real motion names + group tag, and
``MotionPlayer.play_group`` picking from the matching set.
"""
from __future__ import annotations

import json

from puppet.canvas import PuppetCanvas
from puppet.cubism_import import load_model3
from puppet.document import (
    Drawable,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    PuppetDocument,
)
from puppet.document_io import from_zip_bytes, to_zip_bytes
from puppet.motion_player import MotionPlayer


def _motion(name: str, group: str | None) -> Motion:
    return Motion(
        name=name, duration=1.0, loop=False, group=group,
        tracks=[MotionTrack(
            param_id="ParamX",
            segments=[MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.0, 1.0))],
        )],
    )


def _doc_with_motions(*motions: Motion) -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
    )]
    doc.parameters = [Parameter(id="ParamX", min=-1.0, max=1.0, default=0.0)]
    doc.motions = list(motions)
    return doc


# ---------------------------------------------------------------------------
# Schema round-trip
# ---------------------------------------------------------------------------


def test_motion_group_field_round_trips_through_zip():
    doc = _doc_with_motions(_motion("idle_01", "Idle"))
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert restored.motions[0].group == "Idle"


def test_motion_without_group_serialises_clean():
    doc = _doc_with_motions(_motion("loose", None))
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert restored.motions[0].group is None


# ---------------------------------------------------------------------------
# Cubism model3 import preserves real names + group tag
# ---------------------------------------------------------------------------


def _write_motion3(path):
    path.write_text(json.dumps({
        "Version": 3,
        "Meta": {"Duration": 1.0, "Fps": 30, "Loop": False},
        "Curves": [
            {"Target": "Parameter", "Id": "ParamAngleX",
             "Segments": [0.0, 0.0,   0, 1.0, 1.0]},
        ],
    }), encoding="utf-8")


def test_model3_import_keeps_real_motion_names_and_group(tmp_path):
    idle_01 = tmp_path / "idle_01.motion3.json"
    idle_02 = tmp_path / "idle_02.motion3.json"
    tap = tmp_path / "tap_head.motion3.json"
    for p in (idle_01, idle_02, tap):
        _write_motion3(p)
    model = tmp_path / "model.model3.json"
    model.write_text(json.dumps({
        "Version": 3,
        "FileReferences": {
            "Motions": {
                "Idle": [{"File": "idle_01.motion3.json"},
                         {"File": "idle_02.motion3.json"}],
                "TapHead": [{"File": "tap_head.motion3.json"}],
            },
        },
    }), encoding="utf-8")
    bundle = load_model3(model)
    by_name = {m.name: m for m in bundle.motions}
    assert {"Idle/idle_01", "Idle/idle_02", "TapHead/tap_head"} <= set(by_name)
    assert by_name["Idle/idle_01"].group == "Idle"
    assert by_name["Idle/idle_02"].group == "Idle"
    assert by_name["TapHead/tap_head"].group == "TapHead"


# ---------------------------------------------------------------------------
# MotionPlayer.play_group
# ---------------------------------------------------------------------------


def test_play_group_picks_from_matching_motions(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motions(
        _motion("idle_a", "Idle"),
        _motion("idle_b", "Idle"),
        _motion("tap_a", "TapHead"),
    ))
    player = MotionPlayer(canvas)
    try:
        picked = player.play_group("Idle", canvas.document().motions)
        assert picked is not None
        assert picked.group == "Idle"
        assert player.is_playing() is True
    finally:
        player.stop()
        player.deleteLater()
        canvas.deleteLater()


def test_play_group_returns_none_for_unknown_group(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motions(_motion("only", "Idle")))
    player = MotionPlayer(canvas)
    try:
        picked = player.play_group("DoesNotExist", canvas.document().motions)
        assert picked is None
        assert player.is_playing() is False
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_play_group_with_single_member_picks_deterministic(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motions(_motion("only", "Idle")))
    player = MotionPlayer(canvas)
    try:
        picked = player.play_group("Idle", canvas.document().motions)
        assert picked is not None
        assert picked.name == "only"
    finally:
        player.stop()
        player.deleteLater()
        canvas.deleteLater()
