"""Tests for JPEG-XL decode/encode support (Imervue.image.jxl_support)."""
from __future__ import annotations

import sys

import pytest

from Imervue.image import jxl_support
from Imervue.image.jxl_support import (
    JXL_EXTENSIONS,
    ensure_jxl_opener,
    is_jxl_path,
)


def test_extension_present():
    assert ".jxl" in JXL_EXTENSIONS


def test_is_jxl_path():
    assert is_jxl_path("photo.JXL") is True
    assert is_jxl_path("shot.jxl") is True
    assert is_jxl_path("image.png") is False


def test_ensure_returns_bool_and_idempotent():
    first = ensure_jxl_opener()
    assert isinstance(first, bool)
    assert ensure_jxl_opener() == first


def test_ensure_false_when_backend_missing(monkeypatch):
    jxl_support.ensure_jxl_opener.cache_clear()
    monkeypatch.setitem(sys.modules, "pillow_jxl", None)
    try:
        assert jxl_support.ensure_jxl_opener() is False
    finally:
        jxl_support.ensure_jxl_opener.cache_clear()


def test_load_jxl_via_image_loader(tmp_path):
    pytest.importorskip("pillow_jxl")
    jxl_support.ensure_jxl_opener.cache_clear()
    import numpy as np
    from PIL import Image

    import pillow_jxl  # noqa: F401  (registers the codec for the save below)
    out = tmp_path / "shot.jxl"
    Image.fromarray(np.full((24, 24, 3), 90, dtype=np.uint8)).save(str(out), "JXL")

    from Imervue.gpu_image_view.images.image_loader import load_image_file
    result = load_image_file(str(out))
    assert result.ndim == 3
    assert result.shape[2] == 4
    assert result.dtype.kind == "u"
