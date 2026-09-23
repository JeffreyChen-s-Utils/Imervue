"""The GL call sequence ``GPUDabSession.stamp`` issues, recorded without a GL context.

Every ``OpenGL.GL`` function ``stamp`` uses is replaced by a recorder, and
``stamp`` runs on a stand-in session. That pins the exact calls and arguments
(kernel upload, uniforms, the dab quad's vertices, attribute setup, draw and
unbind), so restructuring the method cannot change what reaches the driver.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from OpenGL import GL as gl  # noqa: N811 - short alias for many GL names
import pytest

from Imervue.paint.gpu_brush import GPUDabSession

_USED = (
    "glActiveTexture", "glBindBuffer", "glBindTexture", "glBufferData",
    "glDisableVertexAttribArray", "glDrawArrays", "glEnableVertexAttribArray",
    "glTexImage2D", "glUniform1f", "glUniform1i", "glUniform3f", "glUniformMatrix4fv",
    "glUseProgram", "glVertexAttribPointer",
)


def _plain(value):
    if isinstance(value, np.ndarray):
        return ("array", value.dtype.str, value.shape, value.tobytes())
    if isinstance(value, (bytes, int, float, str, type(None))):
        return value
    return ("obj", getattr(value, "value", repr(type(value))))


@pytest.fixture
def calls(monkeypatch):
    log: list[tuple] = []
    for name in _USED:
        monkeypatch.setattr(gl, name, lambda *args, n=name: log.append((n, *map(_plain, args))))
    return log


def _session(log):
    program = SimpleNamespace(program=11, u_mvp=1, u_kernel=2, u_color=3, u_opacity=4,
                              a_position=5, a_texcoord=6)
    session = GPUDabSession.__new__(GPUDabSession)   # skip __init__: it needs a GL context
    session._bind_session = lambda: log.append(("bind_session",))  # noqa: SLF001
    session._kernel_tex, session._program, session._vbo = 21, program, 31  # noqa: SLF001
    session._mvp = np.eye(4, dtype=np.float32)  # noqa: SLF001
    return session


def _stamp(log, kernel, *, color=(255, 128, 0), opacity=0.5, cx=10.0, cy=20.0):
    _session(log).stamp(kernel, color, opacity, cx, cy)


def test_full_call_sequence(calls):
    kernel = np.arange(6, dtype=np.float64).reshape(2, 3) / 10.0
    _stamp(calls, kernel)
    names = [c[0] for c in calls]
    assert names == [
        "bind_session", "glActiveTexture", "glBindTexture", "glTexImage2D", "glUseProgram",
        "glUniformMatrix4fv", "glUniform1i", "glUniform3f", "glUniform1f", "glBindBuffer",
        "glBufferData", "glEnableVertexAttribArray", "glVertexAttribPointer",
        "glEnableVertexAttribArray", "glVertexAttribPointer", "glDrawArrays",
        "glDisableVertexAttribArray", "glDisableVertexAttribArray", "glBindBuffer",
        "glUseProgram",
    ]
    tex = calls[3]
    assert tex[1:8] == (gl.GL_TEXTURE_2D, 0, gl.GL_LUMINANCE, 3, 2, 0, gl.GL_RED)
    assert tex[8] == gl.GL_FLOAT
    assert tex[9] == np.ascontiguousarray(kernel, dtype=np.float32).tobytes()
    assert calls[7] == ("glUniform3f", 3, pytest.approx(1.0), pytest.approx(128 / 255),
                        pytest.approx(0.0))
    assert calls[8] == ("glUniform1f", 4, pytest.approx(0.5))
    vertices = np.frombuffer(calls[10][3][3], dtype=np.float32).reshape(4, 4)
    # 3x2 kernel centred on (10, 20): x from 8.5 to 11.5, y from 19 to 21.
    assert vertices.tolist() == [[8.5, 19.0, 0.0, 0.0], [11.5, 19.0, 1.0, 0.0],
                                 [11.5, 21.0, 1.0, 1.0], [8.5, 21.0, 0.0, 1.0]]
    assert calls[10][1:3] == (gl.GL_ARRAY_BUFFER, 64)
    assert calls[12][1:6] == (5, 2, gl.GL_FLOAT, gl.GL_FALSE, 16)
    assert calls[14][1:6] == (6, 2, gl.GL_FLOAT, gl.GL_FALSE, 16)
    assert calls[15] == ("glDrawArrays", gl.GL_TRIANGLE_FAN, 0, 4)
    assert calls[-2] == ("glBindBuffer", gl.GL_ARRAY_BUFFER, 0)
    assert calls[-1] == ("glUseProgram", 0)


@pytest.mark.parametrize("opacity", [0.0, -0.3])
def test_zero_opacity_touches_no_gl(calls, opacity):
    _stamp(calls, np.ones((3, 3)), opacity=opacity)
    assert calls == []


def test_opacity_is_clamped_to_one(calls):
    _stamp(calls, np.ones((3, 3)), opacity=4.0)
    assert ("glUniform1f", 4, pytest.approx(1.0)) in calls


def test_kernel_must_be_2d(calls):
    with pytest.raises(ValueError, match="2-D"):
        _stamp(calls, np.ones((3, 3, 1)))
    assert calls == []
