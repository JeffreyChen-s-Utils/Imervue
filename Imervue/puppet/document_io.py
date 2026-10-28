"""Load / save the ``.puppet`` zip container.

Pure-Python — no Qt, no GL. Round-trips through the dataclasses in
``document.py``. Strict schema validation on load with clear error
messages so corrupt files don't silently produce broken puppets.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from Imervue.puppet.archive_container import _load_from_zip, _write_entries
from Imervue.puppet.document import (
    SCHEMA_VERSION,
    PuppetDocument,
)
from Imervue.puppet.format_values import PuppetFormatError
from Imervue.system.atomic_write import replace_atomically

__all__ = [
    "PuppetFormatError", "SCHEMA_VERSION", "load_puppet", "save_puppet",
    "new_blank", "to_zip_bytes", "from_zip_bytes",
]

# Ceiling on the total declared uncompressed size. A rig's textures are PNGs
# that barely compress (the bundled example is ~21 MB), so this only stops a
# zip bomb: zipfile never reads past an entry's declared size, so checking the
# declared total before reading is enough.
_MAX_UNCOMPRESSED_BYTES = 2 * 1024 ** 3


def load_puppet(path: str | Path) -> PuppetDocument:
    """Open ``path`` (a ``.puppet`` zip), parse it, return a document.

    Raises :class:`PuppetFormatError` for any schema violation.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if not zipfile.is_zipfile(p):
        raise PuppetFormatError(f"{p} is not a zip archive")
    try:
        with zipfile.ZipFile(p, "r") as zf:
            return _load_from_zip(zf, max_uncompressed=_MAX_UNCOMPRESSED_BYTES)
    except PuppetFormatError:
        raise
    except (KeyError, TypeError, AttributeError, ValueError, IndexError,
            zipfile.BadZipFile) as exc:
        # The format parsers are strict but not exhaustive: a manifest
        # that is a JSON list (AttributeError on .get), a non-numeric size
        # (ValueError from int()), or a truncated vertex pair (unpack
        # ValueError) would otherwise escape as a raw exception past the
        # workspace's (FileNotFoundError, PuppetFormatError) handler. Normalise
        # every structural fault to PuppetFormatError so the caller reports it
        # cleanly instead of crashing.
        raise PuppetFormatError(f"malformed puppet archive {p}: {exc}") from exc


def save_puppet(doc: PuppetDocument, path: str | Path) -> None:
    """Write ``doc`` to ``path`` as a ``.puppet`` zip archive.

    Overwrites if the file already exists — in one step, so a failure
    mid-write leaves the previous file whole. Creates parent directories
    on demand.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    replace_atomically(p, lambda tmp: _write_puppet(doc, tmp))


def _write_puppet(doc: PuppetDocument, p: Path) -> None:
    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_entries(zf, doc)


def new_blank(size: tuple[int, int] = (1024, 1024)) -> PuppetDocument:
    """Return an empty puppet of ``size`` — no drawables yet. Used as
    the seed for editor sessions starting from scratch."""
    return PuppetDocument(size=size)


def to_zip_bytes(doc: PuppetDocument) -> bytes:
    """Serialise ``doc`` to an in-memory zip and return the bytes. Mirrors
    ``save_puppet`` but without touching disk — handy for tests and for
    embedding a puppet inside another container later."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_entries(zf, doc)
    return buf.getvalue()


def from_zip_bytes(data: bytes) -> PuppetDocument:
    """Inverse of :func:`to_zip_bytes`."""
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        return _load_from_zip(zf, max_uncompressed=_MAX_UNCOMPRESSED_BYTES)
