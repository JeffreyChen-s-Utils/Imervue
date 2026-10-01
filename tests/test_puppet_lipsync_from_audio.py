"""Puppet's Live > Lip-sync from Audio File… adds a mouth motion that plays the file.

``puppet/audio_lipsync.py`` computed a mouth-open curve from a WAV but nothing
called it. ``lipsync_motion`` turns the curve into a motion on the mouth
parameter with the file as its sound, keeping only the keys that matter.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from types import SimpleNamespace

import pytest

from Imervue.puppet.audio_lipsync import LIPSYNC_FPS, lipsync_motion
from Imervue.puppet.document import Motion, Parameter, PuppetDocument
from Imervue.puppet.motion_sampler import sample_motion
from Imervue.puppet.workspace import PuppetWorkspace

_RATE = 8000


def _wav(path: Path, frames: list[int], *, width: int = 2) -> Path:
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(width)
        writer.setframerate(_RATE)
        if width == 2:
            writer.writeframes(struct.pack(f"<{len(frames)}h", *frames))
        else:
            writer.writeframes(bytes(width * len(frames)))
    return path


def _quiet_then_loud(path: Path) -> Path:
    half = _RATE // 2
    tone = [int(20000 * math.sin(2 * math.pi * 220 * i / _RATE)) for i in range(half)]
    return _wav(path, [0] * half + tone)


def test_the_mouth_follows_the_loudness_and_closes_at_the_end(tmp_path):
    motion = lipsync_motion(_quiet_then_loud(tmp_path / "line.wav"), name="line",
                            param_id="ParamMouthOpenY", mouth_range=(0.0, 1.0))
    assert motion is not None and motion.name == "line" and motion.loop is False
    assert motion.duration == pytest.approx(1.0, abs=1.0 / LIPSYNC_FPS)
    (track,) = motion.tracks
    assert track.param_id == "ParamMouthOpenY"
    assert sample_motion(motion, 0.2)["ParamMouthOpenY"] == pytest.approx(0.0, abs=0.05)
    assert sample_motion(motion, 0.75)["ParamMouthOpenY"] > 0.8
    assert track.segments[-1].p1 == (pytest.approx(motion.duration), 0.0)


def test_the_take_keeps_only_the_keys_that_matter(tmp_path):
    motion = lipsync_motion(_quiet_then_loud(tmp_path / "line.wav"), name="l", param_id="P")
    frames = round(motion.duration * LIPSYNC_FPS)
    assert len(motion.tracks[0].segments) < frames / 3


def test_the_file_plays_as_the_motion_sound(tmp_path):
    path = _quiet_then_loud(tmp_path / "line.wav")
    motion = lipsync_motion(path, name="l", param_id="P")
    assert Path(motion.sound_path) == path.resolve()


def test_the_mouth_range_maps_closed_and_open(tmp_path):
    motion = lipsync_motion(_quiet_then_loud(tmp_path / "line.wav"), name="l", param_id="P",
                            mouth_range=(-1.0, 3.0))
    assert sample_motion(motion, 0.2)["P"] == pytest.approx(-1.0, abs=0.2)
    assert sample_motion(motion, 0.75)["P"] > 2.5


def test_a_silent_file_gives_no_motion(tmp_path):
    assert lipsync_motion(_wav(tmp_path / "quiet.wav", [0] * 4000), name="q", param_id="P") is None


def test_an_unsupported_wav_is_refused(tmp_path):
    with pytest.raises(ValueError, match="sample width"):
        lipsync_motion(_wav(tmp_path / "deep.wav", [0] * 30, width=3), name="d", param_id="P")


def _host(document):
    said, loaded, picked = [], [], []
    canvas = SimpleNamespace(document=lambda: document, load_document=loaded.append)
    host = SimpleNamespace(
        _canvas=canvas, _motion_dock=SimpleNamespace(select_motion=picked.append),
        _announce=lambda key, fallback, **fmt: said.append((key, fmt)),
    )
    return host, said, loaded, picked


def _mouth(**kw) -> Parameter:
    return Parameter(id="ParamMouthOpenY", **{"min": 0.0, "max": 1.0, "default": 0.0, **kw})


def test_the_handler_adds_the_motion_and_picks_it(tmp_path):
    doc = PuppetDocument(motions=[Motion(name="lipsync_line", duration=9.0)])
    host, said, loaded, picked = _host(doc)
    PuppetWorkspace._add_lipsync_motion(host, _quiet_then_loud(tmp_path / "line.wav"), _mouth())
    assert [m.name for m in doc.motions] == ["lipsync_line"]          # same name is replaced
    assert doc.motions[0].duration == pytest.approx(1.0, abs=0.05)
    assert loaded == [doc] and picked == ["lipsync_line"]
    assert said[0][0] == "puppet_lipsync_audio_done"


def test_a_mouth_whose_default_is_its_maximum_opens_toward_the_minimum(tmp_path):
    doc = PuppetDocument()
    host, *_ = _host(doc)
    PuppetWorkspace._add_lipsync_motion(host, _quiet_then_loud(tmp_path / "l.wav"),
                                        _mouth(min=-1.0, max=1.0, default=1.0))
    assert sample_motion(doc.motions[0], 0.75)["ParamMouthOpenY"] < -0.5


@pytest.mark.parametrize(("make", "key"), [
    (lambda d: _wav(d / "quiet.wav", [0] * 4000), "puppet_lipsync_audio_silent"),
    (lambda d: _wav(d / "deep.wav", [0] * 30, width=3), "puppet_lipsync_audio_failed"),
    (lambda d: d / "missing.wav", "puppet_lipsync_audio_failed"),
    (lambda d: (d / "text.wav").write_text("not audio") and d / "text.wav", "puppet_lipsync_audio_failed"),
])
def test_the_handler_reports_what_it_could_not_use(tmp_path, make, key):
    doc = PuppetDocument()
    host, said, loaded, _ = _host(doc)
    PuppetWorkspace._add_lipsync_motion(host, make(tmp_path), _mouth())
    assert [k for k, _ in said] == [key] and loaded == [] and doc.motions == []
