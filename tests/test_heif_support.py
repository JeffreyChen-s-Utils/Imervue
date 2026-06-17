"""Tests for HEIF/AVIF decode support (Imervue.image.heif_support)."""
from __future__ import annotations

import sys

import pytest

from Imervue.image import heif_support
from Imervue.image.heif_support import (
    HEIF_EXTENSIONS,
    ensure_heif_opener,
    is_heif_path,
    needs_heif_hint,
)


# ---------------------------------------------------------------------------
# extensions + path test
# ---------------------------------------------------------------------------


def test_known_extensions_present():
    assert ".heic" in HEIF_EXTENSIONS
    assert ".heif" in HEIF_EXTENSIONS
    assert ".avif" in HEIF_EXTENSIONS


def test_is_heif_path():
    assert is_heif_path("IMG_1234.HEIC") is True
    assert is_heif_path("shot.avif") is True
    assert is_heif_path("photo.png") is False


# ---------------------------------------------------------------------------
# needs_heif_hint
# ---------------------------------------------------------------------------


def test_hint_not_needed_when_opener_available():
    assert needs_heif_hint(["a.heic"], opener_available=True) is False


def test_hint_needed_when_missing_and_heif_present():
    assert needs_heif_hint(["a.png", "b.heic"], opener_available=False) is True


def test_hint_not_needed_without_heif():
    assert needs_heif_hint(["a.png", "b.jpg"], opener_available=False) is False


def test_hint_not_needed_for_empty_folder():
    assert needs_heif_hint([], opener_available=False) is False


# ---------------------------------------------------------------------------
# ensure_heif_opener
# ---------------------------------------------------------------------------


def test_ensure_returns_bool_and_is_idempotent():
    first = ensure_heif_opener()
    assert isinstance(first, bool)
    assert ensure_heif_opener() == first


def test_ensure_false_when_backend_missing(monkeypatch):
    heif_support.ensure_heif_opener.cache_clear()
    monkeypatch.setitem(sys.modules, "pillow_heif", None)
    try:
        assert heif_support.ensure_heif_opener() is False
    finally:
        # Drop the cached failure so later tests re-evaluate against the real backend.
        heif_support.ensure_heif_opener.cache_clear()


# ---------------------------------------------------------------------------
# integration — real decode (needs pillow-heif)
# ---------------------------------------------------------------------------


def _write_heif(path, ext):
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    import numpy as np
    from PIL import Image
    arr = np.full((24, 24, 3), 90, dtype=np.uint8)
    Image.fromarray(arr).save(str(path.with_suffix(ext)))


@pytest.mark.parametrize("ext", [".heic", ".avif"])
def test_load_heif_via_image_loader(tmp_path, ext):
    heif_support.ensure_heif_opener.cache_clear()
    _write_heif(tmp_path / "shot", ext)
    from Imervue.gpu_image_view.images.image_loader import load_image_file
    result = load_image_file(str((tmp_path / "shot").with_suffix(ext)))
    assert result.ndim == 3
    assert result.shape[2] == 4
    assert result.dtype.kind == "u"
