"""The vendor VRAM probe reads "unsupported" as 0 and lets anything else through.

``glGetIntegerv`` raises ``GLError`` without a context or for an enum the
driver rejects, and ``KeyError`` ("Unknown specifier") for an enum PyOpenGL has
no size entry for — measured on a real context. Driven with a patched
``glGetIntegerv``, so no GL context is needed.
"""
from __future__ import annotations

import pytest
from OpenGL.error import GLError

from Imervue.gpu_image_view import vram_detect


def _gl_returning(value):
    return lambda _enum: value


def _gl_raising(exc):
    def _fail(_enum):
        raise exc
    return _fail


@pytest.mark.parametrize(("value", "expected"), [
    (4096, 4096), ([2048, 1, 2, 3], 2048), ((512,), 512), ([], 0), (None, 0),
])
def test_probe_reads_scalars_and_vectors(monkeypatch, value, expected):
    monkeypatch.setattr(vram_detect, "glGetIntegerv", _gl_returning(value))
    assert vram_detect._probe_gl_integer(0x9048) == expected


@pytest.mark.parametrize("exc", [GLError(1282, None), KeyError("Unknown specifier 74565")])
def test_unsupported_enum_reads_as_zero(monkeypatch, exc):
    monkeypatch.setattr(vram_detect, "glGetIntegerv", _gl_raising(exc))
    assert vram_detect._probe_gl_integer(0x12345) == 0


def test_unexpected_error_propagates(monkeypatch):
    monkeypatch.setattr(vram_detect, "glGetIntegerv", _gl_raising(TypeError("bad enum")))
    with pytest.raises(TypeError):
        vram_detect._probe_gl_integer(0x9048)


def test_vendor_probe_falls_back_from_nvidia_to_amd(monkeypatch):
    def gl(enum):
        if enum == vram_detect._NVX_TOTAL_AVAILABLE:
            raise GLError(1280, None)   # GL_INVALID_ENUM on a non-NVIDIA driver
        return [8192, 0, 0, 0]

    monkeypatch.setattr(vram_detect, "glGetIntegerv", gl)
    assert vram_detect._probe_vendor_vram_kb() == 8192
