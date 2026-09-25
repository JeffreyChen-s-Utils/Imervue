"""Tests for the memory-efficient RAW loader helpers.

We can't ship a real CR3 / NEF in the test suite (huge binaries,
licensing). The tests stub ``rawpy.RawPy`` to verify the wrappers
call the right methods in the right order: open_file → unpack
(efficient path) and open_buffer → unpack (mmap path).
"""
from __future__ import annotations

import sys
import types

import pytest

from Imervue.image.raw_loader import (
    file_size_supports_mmap,
    open_raw_efficient,
    open_raw_via_mmap,
    raw_dimensions,
)


# ---------------------------------------------------------------
# Stub RawPy module
# ---------------------------------------------------------------


class _StubRaw:
    """Records every method call so tests can assert on the order
    and arguments — proves the wrapper takes the efficient path."""

    instances: list = []

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.closed = False
        _StubRaw.instances.append(self)

    def open_file(self, path: str) -> None:
        self.calls.append(("open_file", path))

    def open_buffer(self, fileobj) -> None:
        self.calls.append(("open_buffer", type(fileobj).__name__))

    def unpack(self) -> None:
        self.calls.append(("unpack",))

    def close(self) -> None:
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


@pytest.fixture
def stub_rawpy(monkeypatch):
    """Replace ``rawpy.RawPy`` with the stub class so the wrappers
    can be exercised without a real libraw install / RAW file."""
    _StubRaw.instances.clear()
    fake = types.ModuleType("rawpy")
    fake.RawPy = _StubRaw   # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "rawpy", fake)
    return _StubRaw


# ---------------------------------------------------------------
# open_raw_efficient
# ---------------------------------------------------------------


def test_efficient_path_uses_open_file(stub_rawpy, tmp_path):
    """The whole point — no convenience ``imread``. The wrapper
    must hit ``open_file`` so libraw streams via the OS page cache
    instead of through a Python bytes copy."""
    raw = open_raw_efficient(tmp_path / "fake.cr3")
    method_names = [c[0] for c in raw.calls]
    assert "open_file" in method_names
    assert "unpack" in method_names


def test_efficient_path_order_is_open_then_unpack(stub_rawpy, tmp_path):
    """libraw requires open_file before unpack — any reversal
    would raise. Catches a future refactor that splits them up."""
    raw = open_raw_efficient(tmp_path / "fake.cr3")
    names = [c[0] for c in raw.calls]
    assert names.index("open_file") < names.index("unpack")


def test_efficient_returns_unpacked_instance(stub_rawpy, tmp_path):
    """Caller expects to call ``postprocess`` / ``extract_thumb``
    on the return — the wrapper must hand back the raw instance,
    not a wrapper or a tuple."""
    raw = open_raw_efficient(tmp_path / "fake.cr3")
    assert isinstance(raw, stub_rawpy)


def test_efficient_closes_on_unpack_failure(stub_rawpy, monkeypatch, tmp_path):
    """If ``unpack`` raises, the libraw context must be released —
    otherwise repeated failures would leak file handles."""
    instances: list = []

    class _FailingRaw(_StubRaw):
        def unpack(self):
            instances.append(self)
            raise RuntimeError("corrupt RAW")

    fake = types.ModuleType("rawpy")
    fake.RawPy = _FailingRaw   # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "rawpy", fake)

    with pytest.raises(RuntimeError):
        open_raw_efficient(tmp_path / "broken.cr3")
    assert instances and instances[0].closed is True


# ---------------------------------------------------------------
# open_raw_via_mmap
# ---------------------------------------------------------------


def test_mmap_path_uses_open_buffer(stub_rawpy, tmp_path):
    """mmap fallback must NOT call open_file — that would read the
    file twice. open_buffer takes the mmap region directly."""
    rawfile = tmp_path / "fake.cr3"
    rawfile.write_bytes(b"FAKE-RAW-CONTENT" * 1024)
    raw = open_raw_via_mmap(rawfile)
    try:
        method_names = [c[0] for c in raw.calls]
        assert "open_buffer" in method_names
        assert "open_file" not in method_names
        assert "unpack" in method_names
    finally:
        raw.close()   # wrapped close releases the mmap region + fd too


def test_mmap_path_close_releases_the_file(stub_rawpy, tmp_path):
    """close() must release the mmap + fd on top of the libraw context. A
    leaked mapping keeps the file locked on Windows, so deleting it after close
    proves everything was released."""
    rawfile = tmp_path / "fake.cr3"
    rawfile.write_bytes(b"X" * 4096)
    raw = open_raw_via_mmap(rawfile)
    raw.close()
    rawfile.unlink()   # PermissionError here would mean the mmap/fd leaked
    assert not rawfile.exists()


# ---------------------------------------------------------------
# file_size_supports_mmap
# ---------------------------------------------------------------


def test_mmap_threshold_yes_for_large_files():
    """50 MB CR3 → mmap pays off."""
    assert file_size_supports_mmap(50 * 1024 * 1024) is True


def test_mmap_threshold_no_for_tiny_files():
    """An 800 KB JPEG would be slower with mmap than a one-shot
    read — the setup overhead dominates."""
    assert file_size_supports_mmap(800 * 1024) is False


def test_mmap_threshold_at_boundary():
    """Exactly the threshold counts as 'yes' — boundary check
    matters for files that sit right at the 1 MB cutoff."""
    assert file_size_supports_mmap(1_048_576) is True


def test_mmap_threshold_zero_size_is_false():
    """An empty file (somehow) is not mmappable. The decoder
    would also fail; bail early with False."""
    assert file_size_supports_mmap(0) is False
    assert file_size_supports_mmap(-1) is False


def test_mmap_threshold_custom_minimum():
    """Tunable for callers that want a different policy — e.g.
    streaming over network drive might want a higher cutoff."""
    assert file_size_supports_mmap(2_000_000, minimum_bytes=5_000_000) is False
    assert file_size_supports_mmap(10_000_000, minimum_bytes=5_000_000) is True


def test_efficient_close_failure_is_logged_and_keeps_the_unpack_error(
        stub_rawpy, monkeypatch, tmp_path, caplog):
    class _BrokenRaw(_StubRaw):
        def unpack(self):
            raise RuntimeError("corrupt RAW")

        def close(self):
            raise OSError("libraw close failed")

    fake = types.ModuleType("rawpy")
    fake.RawPy = _BrokenRaw   # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "rawpy", fake)

    with caplog.at_level("DEBUG", logger="Imervue"), pytest.raises(RuntimeError, match="corrupt RAW"):
        open_raw_efficient(tmp_path / "broken.cr3")
    (record,) = caplog.records
    assert "close the RAW file after a failed unpack" in record.getMessage()
    assert record.exc_info[0] is OSError


# ---------------------------------------------------------------
# raw_dimensions
# ---------------------------------------------------------------


class _LibRawError(Exception):
    pass


def _sizes_rawpy(monkeypatch, *, width=6000, height=4000, flip=0, error=None):
    """A rawpy stand-in whose open_file either fails or exposes ``sizes``; records the calls."""
    calls = []

    class _Raw:
        def open_file(self, path):
            calls.append(("open_file", path))
            if error is not None:
                raise error
            self.sizes = types.SimpleNamespace(width=width, height=height, flip=flip)

        def unpack(self):
            calls.append(("unpack",))

        def close(self):
            calls.append(("close",))

    fake = types.ModuleType("rawpy")
    fake.RawPy = _Raw   # type: ignore[attr-defined]
    fake.LibRawError = _LibRawError   # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "rawpy", fake)
    return calls


@pytest.mark.parametrize(("flip", "expected"), [
    (0, (6000, 4000)), (3, (6000, 4000)), (5, (4000, 6000)), (6, (4000, 6000)),
])
def test_raw_dimensions_reads_the_header_only_and_follows_the_orientation(
    monkeypatch, tmp_path, flip, expected,
):
    calls = _sizes_rawpy(monkeypatch, flip=flip)
    assert raw_dimensions(tmp_path / "a.cr2") == expected
    assert [c[0] for c in calls] == ["open_file", "close"]   # no unpack: header only


def test_raw_dimensions_of_an_unreadable_file_is_none_and_still_closes(monkeypatch, tmp_path):
    calls = _sizes_rawpy(monkeypatch, error=_LibRawError("unsupported"))
    assert raw_dimensions(tmp_path / "a.cr2") is None
    assert calls[-1] == ("close",)


def test_raw_dimensions_lets_an_unexpected_error_through(monkeypatch, tmp_path):
    _sizes_rawpy(monkeypatch, error=RuntimeError("bug"))
    with pytest.raises(RuntimeError, match="bug"):
        raw_dimensions(tmp_path / "a.cr2")



# ---------------------------------------------------------------
# develop_raw (real libraw)
# ---------------------------------------------------------------


@pytest.mark.parametrize("thumbnail", [False, True])
def test_develop_raw_turns_libraw_errors_into_oserror(tmp_path, thumbnail):
    """Qt-free, so the MCP server can develop RAW; its failures stay IMAGE_READ_ERRORS."""
    rawpy = pytest.importorskip("rawpy")
    from Imervue.image.raw_loader import develop_raw
    from Imervue.image.read_errors import IMAGE_READ_ERRORS
    path = tmp_path / "broken.nef"
    path.write_bytes(b"not a raw file" * 20)
    with pytest.raises(OSError, match="libraw can't decode") as caught:
        develop_raw(path, thumbnail=thumbnail)
    assert isinstance(caught.value, IMAGE_READ_ERRORS)
    assert isinstance(caught.value.__cause__, rawpy.LibRawError)


def test_develop_raw_pulls_in_no_qt():
    """The MCP server imports it and must stay Qt-free."""
    import subprocess
    from pathlib import Path
    code = ("import sys; import Imervue.image.raw_loader; "
            "print(any(m.startswith('PySide6') for m in sys.modules))")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,  # noqa: S603 - fixed argv
                            check=True, cwd=str(Path(__file__).parent.parent))
    assert result.stdout.strip() == "False"
