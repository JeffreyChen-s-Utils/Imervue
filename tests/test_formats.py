"""The one definition of which file extensions Imervue opens."""
from __future__ import annotations

import pytest

from Imervue.image import formats
from Imervue.image.formats import (
    RAW_EXTENSIONS,
    STILL_IMAGE_EXTENSIONS,
    VIEWER_EXTENSIONS,
    ensure_pillow_opener,
)
from Imervue.image.avif_support import AVIF_EXTENSIONS
from Imervue.image.heif_support import HEIF_EXTENSIONS
from Imervue.image.jxl_support import JXL_EXTENSIONS
from Imervue.image.video_frames import VIDEO_EXTENSIONS


def test_sets_nest():
    assert RAW_EXTENSIONS | HEIF_EXTENSIONS | AVIF_EXTENSIONS | JXL_EXTENSIONS <= STILL_IMAGE_EXTENSIONS
    assert VIEWER_EXTENSIONS == STILL_IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    assert not STILL_IMAGE_EXTENSIONS & VIDEO_EXTENSIONS


def test_extensions_are_lowercase_with_a_dot():
    assert all(e.startswith(".") and e == e.lower() for e in VIEWER_EXTENSIONS)


@pytest.mark.parametrize(("ext", "expected"), [
    (".heic", ["heif"]), (".HEIF", ["heif"]), (".AVIF", []), (".jxl", ["jxl"]),
    (".png", []), (".mp4", []), ("", []),
])
def test_ensure_pillow_opener_registers_only_the_codec_needed(monkeypatch, ext, expected):
    calls = []
    monkeypatch.setattr(formats, "ensure_heif_opener", lambda: calls.append("heif"))
    monkeypatch.setattr(formats, "ensure_jxl_opener", lambda: calls.append("jxl"))
    ensure_pillow_opener(ext)
    assert calls == expected
