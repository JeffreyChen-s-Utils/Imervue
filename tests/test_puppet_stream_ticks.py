"""The puppet's per-frame outputs skip a frame only for the GL failures they expect.

NDI, the virtual camera and the recorder all render or grab a frame on a timer.
No current context or a deleted canvas (``GLError`` / ``RuntimeError``, which
includes the recorder's ``CaptureError``) skips that frame; any other error is
a bug and propagates. Driven unbound on fakes, so no GL widget, NDI runtime or
virtual-camera driver is needed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from OpenGL.error import GLError

from Imervue.puppet import recorder as recorder_mod
from Imervue.puppet.ndi_output import NDIOutput
from Imervue.puppet.recorder import CaptureError, RecordingSession
from Imervue.puppet.virtual_camera import VirtualCameraOutput


def _raise(exc):
    def _fail(*_args, **_kwargs):
        raise exc
    return _fail


def _ndi(render):
    sent: list = []
    canvas = SimpleNamespace(document=lambda: SimpleNamespace(size=(64, 48)),
                             render_offscreen_puppet=render)
    return SimpleNamespace(_sender=object(), _ndi=SimpleNamespace(send=sent.append),
                           _canvas=canvas), sent


def _camera(render):
    frames: list = []
    camera = SimpleNamespace(width=32, height=24, send=frames.append)
    return SimpleNamespace(_camera=camera,
                           _canvas=SimpleNamespace(render_offscreen_puppet=render)), frames


EXPECTED = [GLError(1282, None), RuntimeError("Internal C++ object already deleted")]


@pytest.mark.parametrize("exc", EXPECTED)
def test_ndi_skips_a_frame_it_cannot_render(exc):
    fake, sent = _ndi(_raise(exc))
    NDIOutput._on_tick(fake)
    assert sent == []


def test_ndi_propagates_an_unexpected_render_error():
    fake, _sent = _ndi(_raise(TypeError("bad size")))
    with pytest.raises(TypeError):
        NDIOutput._on_tick(fake)


@pytest.mark.parametrize("exc", EXPECTED)
def test_virtual_camera_skips_a_frame_it_cannot_render(exc):
    fake, frames = _camera(_raise(exc))
    VirtualCameraOutput._on_tick(fake)
    assert frames == []


def test_virtual_camera_propagates_an_unexpected_render_error():
    fake, _frames = _camera(_raise(TypeError("bad size")))
    with pytest.raises(TypeError):
        VirtualCameraOutput._on_tick(fake)


def _session():
    appended: list = []
    return SimpleNamespace(is_recording=lambda: True, _canvas=object(),
                           _writer=SimpleNamespace(append_data=appended.append)), appended


@pytest.mark.parametrize("exc", [*EXPECTED, CaptureError("no framebuffer yet")])
def test_recorder_skips_a_frame_it_cannot_grab(monkeypatch, exc):
    monkeypatch.setattr(recorder_mod, "capture_canvas_image", _raise(exc))
    fake, appended = _session()
    RecordingSession._on_tick(fake)
    assert appended == []


def test_recorder_propagates_an_unexpected_grab_error(monkeypatch):
    monkeypatch.setattr(recorder_mod, "capture_canvas_image", _raise(TypeError("bad canvas")))
    fake, _appended = _session()
    with pytest.raises(TypeError):
        RecordingSession._on_tick(fake)
