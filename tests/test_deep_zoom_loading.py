"""``DeepZoomLoadingMixin`` decisions that need no GL context."""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.deep_zoom_loading import DeepZoomLoadingMixin


@pytest.mark.parametrize("name", ["a.nef", "b.CR2", "c.dng"])
def test_raw_files_decode_progressively(tmp_path, name):
    """This path imported a removed ``image_loader._RAW_EXTS`` and raised ImportError."""
    path = tmp_path / name
    path.write_bytes(b"\x00")
    assert DeepZoomLoadingMixin._should_progressive_decode(None, str(path)) is True


def test_small_ordinary_file_loads_in_one_pass(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"\x00" * 16)
    assert DeepZoomLoadingMixin._should_progressive_decode(None, str(path)) is False


def test_large_file_decodes_progressively(tmp_path):
    path = tmp_path / "big.png"
    with path.open("wb") as fh:
        fh.truncate(60 * 1024 * 1024)
    assert DeepZoomLoadingMixin._should_progressive_decode(None, str(path)) is True


def test_missing_file_loads_in_one_pass(tmp_path):
    assert DeepZoomLoadingMixin._should_progressive_decode(None, str(tmp_path / "gone.png")) is False
