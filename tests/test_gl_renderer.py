"""Tests for ``GLRenderer.init``'s fallbacks, with the GL entry points faked (no context)."""
from __future__ import annotations

import pytest
from OpenGL.error import GLError

from Imervue.gpu_image_view import gl_renderer as mod


@pytest.fixture
def fake_gl(monkeypatch):
    """Make every GL call ``init`` makes succeed; return a setter for glGetFloatv."""
    monkeypatch.setattr(mod.gl_shaders, "compileShader", lambda *_a: 1)
    monkeypatch.setattr(mod.gl_shaders, "compileProgram", lambda *_a: 2)
    for name in ("glGenBuffers", "glBindBuffer", "glBufferData",
                 "glGetUniformLocation", "glGetAttribLocation"):
        monkeypatch.setattr(mod, name, lambda *_a: 3)

    def set_aniso(result):
        def get_floatv(_enum):
            if isinstance(result, Exception):
                raise result
            return result
        monkeypatch.setattr(mod, "glGetFloatv", get_floatv)

    return set_aniso


def test_shaders_with_anisotropy(fake_gl):
    fake_gl(16.0)
    renderer = mod.GLRenderer()
    renderer.init()
    assert renderer.use_shaders is True
    assert renderer._max_anisotropy == pytest.approx(8.0)  # noqa: SLF001


def test_missing_anisotropy_extension_keeps_shaders(fake_gl):
    fake_gl(GLError(err=1280, baseOperation="glGetFloatv"))
    renderer = mod.GLRenderer()
    renderer.init()
    assert renderer.use_shaders is True
    assert renderer._max_anisotropy == 0  # noqa: SLF001


def test_unexpected_anisotropy_error_falls_back_to_immediate_mode(fake_gl, caplog):
    fake_gl(RuntimeError("driver bug"))
    renderer = mod.GLRenderer()
    with caplog.at_level("WARNING", logger="Imervue"):
        renderer.init()
    assert renderer.use_shaders is False


@pytest.mark.parametrize("exc", [RuntimeError("compile failed"), GLError(err=1282),
                                 TypeError("ctypes argument")])
def test_shader_failure_falls_back_with_traceback(fake_gl, monkeypatch, caplog, exc):
    def fail(*_a):
        raise exc

    monkeypatch.setattr(mod.gl_shaders, "compileShader", fail)
    renderer = mod.GLRenderer()
    with caplog.at_level("WARNING", logger="Imervue"):
        renderer.init()
    assert renderer.use_shaders is False
    (record,) = [r for r in caplog.records if r.exc_info]
    assert record.exc_info[0] is type(exc)


# ---------------------------------------------------------------------------
# draw_colored_rect(rect, rgba, filled): both paths, GL entry points recorded.
# ---------------------------------------------------------------------------

@pytest.fixture
def gl_log(monkeypatch):
    log: list[tuple] = []
    for name in ("glUseProgram", "glUniformMatrix4fv", "glUniform4f", "glBindBuffer",
                 "glBufferSubData", "glEnableVertexAttribArray", "glVertexAttribPointer",
                 "glDrawArrays", "glDisableVertexAttribArray", "glColor4f", "glBegin",
                 "glVertex2f", "glEnd"):
        monkeypatch.setattr(mod, name, lambda *args, n=name: log.append((n, *args)))
    return log


def test_colored_rect_shader_path(gl_log):
    import numpy as np
    renderer = mod.GLRenderer()
    renderer.use_shaders = True
    renderer._col_prog, renderer._vbo = 7, 9  # noqa: SLF001
    renderer._col_loc = {"u_mvp": 1, "u_color": 2, "a_position": 3}  # noqa: SLF001
    renderer.draw_colored_rect((1.0, 2.0, 11.0, 22.0), (0.1, 0.2, 0.3, 0.4), filled=False)
    names = [c[0] for c in gl_log]
    assert names[0] == "glUseProgram" and ("glUniform4f", 2, 0.1, 0.2, 0.3, 0.4) in gl_log
    assert ("glDrawArrays", mod.GL_LINE_LOOP, 0, 4) in gl_log
    assert np.array_equal(renderer._rect_scratch,  # noqa: SLF001
                          np.array([1, 2, 11, 2, 11, 22, 1, 22], dtype=np.float32))


def test_colored_rect_legacy_path(gl_log):
    renderer = mod.GLRenderer()
    renderer.use_shaders = False
    renderer.draw_colored_rect((1.0, 2.0, 11.0, 22.0), (0.1, 0.2, 0.3, 0.4))
    assert gl_log[0] == ("glColor4f", 0.1, 0.2, 0.3, 0.4)
    assert gl_log[1] == ("glBegin", mod.GL_QUADS)
    assert [c[1:] for c in gl_log if c[0] == "glVertex2f"] == [
        (1.0, 2.0), (11.0, 2.0), (11.0, 22.0), (1.0, 22.0)]
