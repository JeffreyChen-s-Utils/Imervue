"""open_raw_via_mmap's close() must release the mmap region + fd, not leak them.

RawPy.close() only tears down the libraw context; the mmap + fd were stashed but
never closed. The release wiring is extracted so it is testable without rawpy.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Imervue.image.raw_loader import _wrap_close_to_release


def test_close_releases_all_three_handles():
    order: list = []
    raw = SimpleNamespace(close=lambda: order.append("raw"))
    region = SimpleNamespace(close=lambda: order.append("region"))
    fd = SimpleNamespace(close=lambda: order.append("fd"))
    wrapped = _wrap_close_to_release(raw, region, fd)
    assert wrapped is raw
    wrapped.close()
    assert order == ["raw", "region", "fd"]


def test_region_and_fd_close_even_if_rawpy_close_raises():
    closed: list = []

    def boom():
        raise RuntimeError("libraw error")

    raw = SimpleNamespace(close=boom)
    region = SimpleNamespace(close=lambda: closed.append("region"))
    fd = SimpleNamespace(close=lambda: closed.append("fd"))
    wrapped = _wrap_close_to_release(raw, region, fd)
    with pytest.raises(RuntimeError):
        wrapped.close()
    assert closed == ["region", "fd"]   # still released via finally
