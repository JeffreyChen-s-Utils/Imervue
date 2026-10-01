"""The puppet canvas's off-screen framebuffer carries a stencil buffer, which clip masks need.

The format is a plain value, so this runs without a GL context, but Qt needs its
application object first.
"""
from __future__ import annotations

from PySide6.QtOpenGL import QOpenGLFramebufferObject

from Imervue.puppet.canvas import offscreen_framebuffer_format


def test_offscreen_framebuffer_has_a_depth_stencil_attachment(qapp):
    fmt = offscreen_framebuffer_format()
    assert fmt.attachment() == QOpenGLFramebufferObject.Attachment.CombinedDepthStencil


def test_each_call_returns_a_fresh_format(qapp):
    assert offscreen_framebuffer_format() is not offscreen_framebuffer_format()
