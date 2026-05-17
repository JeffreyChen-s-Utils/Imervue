"""Tests for the motion sound-playback hook on :class:`MotionPlayer`.

We don't exercise QtMultimedia's actual playback (no audio hardware in
CI). Instead we assert:

* ``Motion.sound_path`` round-trips through document IO.
* Cubism .model3 imports populate it from the entry's ``Sound`` field.
* Playing a motion without a sound_path doesn't try to create a
  QSoundEffect (lazy init).
* Playing a motion with a missing sound_path is silent / non-raising.
"""
from __future__ import annotations
import json

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.cubism_import import load_model3
from Imervue.puppet.document import (
    Drawable,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    PuppetDocument,
)
from Imervue.puppet.document_io import from_zip_bytes, to_zip_bytes
from Imervue.puppet.motion_player import MotionPlayer

from _qt_skip import pytestmark  # noqa: E402,F401


def _doc_with_motion(motion: Motion) -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
    )]
    doc.parameters = [Parameter(id="ParamX", min=-1.0, max=1.0, default=0.0)]
    doc.motions = [motion]
    return doc


def _simple_motion(sound_path: str | None = None) -> Motion:
    return Motion(
        name="m",
        duration=1.0,
        loop=False,
        sound_path=sound_path,
        tracks=[MotionTrack(
            param_id="ParamX",
            segments=[MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.0, 1.0))],
        )],
    )


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_sound_path_round_trips_through_zip():
    doc = _doc_with_motion(_simple_motion(sound_path="motions/voice.wav"))
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert restored.motions[0].sound_path == "motions/voice.wav"


def test_motion_without_sound_path_serialises_clean():
    doc = _doc_with_motion(_simple_motion())
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert restored.motions[0].sound_path is None


# ---------------------------------------------------------------------------
# Cubism model3 integration
# ---------------------------------------------------------------------------


def test_model3_populates_sound_path_from_motion_entry(tmp_path):
    motion_path = tmp_path / "voice.motion3.json"
    motion_path.write_text(json.dumps({
        "Version": 3,
        "Meta": {"Duration": 1.0, "Fps": 30, "Loop": False},
        "Curves": [
            {"Target": "Parameter", "Id": "ParamAngleX",
             "Segments": [0.0, 0.0,   0, 1.0, 1.0]},
        ],
    }), encoding="utf-8")
    sound_path = tmp_path / "voice.wav"
    sound_path.write_bytes(b"")
    model_path = tmp_path / "model.model3.json"
    model_path.write_text(json.dumps({
        "Version": 3,
        "FileReferences": {
            "Motions": {
                "Voice": [
                    {"File": "voice.motion3.json", "Sound": "voice.wav"},
                ],
            },
        },
    }), encoding="utf-8")
    bundle = load_model3(model_path)
    assert bundle.motions[0].sound_path is not None
    assert bundle.motions[0].sound_path.endswith("voice.wav")


# ---------------------------------------------------------------------------
# Player tolerates absent sound path
# ---------------------------------------------------------------------------


def test_play_motion_without_sound_path_does_not_init_audio(qapp):
    """Motions without a sound_path should never instantiate the
    QSoundEffect — lazy init keeps the player import-time cheap in
    headless environments. We can introspect the private attribute
    safely because the test owns this player exclusively."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_motion(_simple_motion()))
    player = MotionPlayer(canvas)
    try:
        player.set_motion(canvas.document().motions[0])
        player.play()
        assert player._sound_effect is None   # noqa: SLF001
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_play_motion_with_missing_sound_file_is_silent(qapp, tmp_path):
    """If the sound_path points at a non-existent file, the player
    must still play the motion normally — we log debug + skip audio."""
    canvas = PuppetCanvas()
    motion = _simple_motion(sound_path=str(tmp_path / "missing.wav"))
    canvas.load_document(_doc_with_motion(motion))
    player = MotionPlayer(canvas)
    try:
        player.set_motion(canvas.document().motions[0])
        player.play()
        assert player.is_playing() is True
    finally:
        player.deleteLater()
        canvas.deleteLater()
