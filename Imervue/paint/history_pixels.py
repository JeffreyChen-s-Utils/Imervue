"""Immutable, shared pixel tiles for bounded document history.

Only a caller that knows every changed array may supply regional hints.
Uninstrumented edits always compare all pixels with the previous snapshot.
"""
from __future__ import annotations

import sys
import weakref
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

import numpy as np

from Imervue.paint.damage import DamageRect
from Imervue.paint.document import PaintDocument, _CONTENT_FIELDS

TILE_SIZE = 256


@dataclass(frozen=True, eq=False)
class _Chunk:
    data: bytes


@dataclass(frozen=True, eq=False)
class FrozenPixels:
    """Owned immutable tiles; deepcopy reconstructs a mutable, independent array."""

    shape: tuple[int, ...]
    dtype: np.dtype
    chunks: tuple[_Chunk, ...]

    def tiles(self) -> Iterator[tuple[tuple[slice, ...], _Chunk]]:
        """Yield each tile's array slice and owned bytes."""
        height = self.shape[0] if self.shape else 1
        width = self.shape[1] if len(self.shape) > 1 else 1
        for index, (y, x) in enumerate(
            (y, x) for y in range(0, height, TILE_SIZE) for x in range(0, width, TILE_SIZE)
        ):
            slices = (slice(y, y + TILE_SIZE), slice(x, x + TILE_SIZE))[:len(self.shape)]
            yield slices, self.chunks[index]

    def restore_into(self, array: np.ndarray) -> None:
        """Patch differing tiles into a compatible writable live array."""
        for slices, chunk in self.tiles():
            target = array[slices]
            pixels = np.frombuffer(chunk.data, dtype=self.dtype).reshape(target.shape)
            if not np.array_equal(target, pixels):
                target[...] = pixels

    def __deepcopy__(self, memo: dict) -> np.ndarray:
        array = np.empty(self.shape, dtype=self.dtype)
        # Every tile is assigned; an empty array has no tile payload.
        for slices, chunk in self.tiles():
            array[slices] = np.frombuffer(chunk.data, dtype=self.dtype).reshape(array[slices].shape)
        memo[id(self)] = array
        return array


def arrays_in(value: object, seen: set[int] | None = None) -> Iterator[np.ndarray]:
    """Find content arrays without following callbacks or weak identities."""
    seen = set() if seen is None else seen
    if id(value) in seen:
        return
    seen.add(id(value))
    if isinstance(value, np.ndarray):
        yield value
    else:
        owned = (tuple(getattr(value, name) for name in _CONTENT_FIELDS)
                 if isinstance(value, PaintDocument) else children(value))
        for child in owned:
            yield from arrays_in(child, seen)


def children(value: object) -> tuple | list:
    """Return owned Python fields for copying/accounting, never weakref targets."""
    if isinstance(value, dict):
        return [part for pair in value.items() for part in pair]
    if isinstance(value, (tuple, list, set, frozenset)):
        return value
    if isinstance(value, (type, weakref.ReferenceType, np.ndarray, np.dtype)):
        return ()
    return (vars(value),) if hasattr(value, "__dict__") else ()


def owned_bytes(values: object) -> int:
    """Count unique owned payloads and Python containers, excluding live targets."""
    seen: set[int] = set()
    pending = [values]
    size = 0
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        size += sys.getsizeof(value)
        pending.extend(children(value))
    return size



def _tile_outside(region: DamageRect | None, x: int, y: int) -> bool:
    """Whether the tile at ``(x, y)`` lies wholly outside the damaged *region*."""
    return region is not None and (
        x >= region.x2 or x + TILE_SIZE <= region.x
        or y >= region.y2 or y + TILE_SIZE <= region.y
    )


def _same_pixels(tile: np.ndarray, chunk: _Chunk) -> bool:
    """Whether *tile* still holds the pixels frozen in *chunk*."""
    return np.array_equal(tile, np.frombuffer(chunk.data, dtype=tile.dtype).reshape(tile.shape))


class PixelStore:
    """Intern identical tiles weakly so discarded history releases its payloads."""

    def __init__(self) -> None:
        self._chunks: weakref.WeakValueDictionary[bytes, _Chunk] = weakref.WeakValueDictionary()

    def compact(self, retained: Iterable[FrozenPixels]) -> None:
        """Rebuild the weak index from retained history, releasing its spare capacity."""
        self._chunks = weakref.WeakValueDictionary(
            (chunk.data, chunk) for pixels in retained for chunk in pixels.chunks
        )

    def freeze(self, array: np.ndarray, previous: FrozenPixels | None = None,
               *, region: DamageRect | None = None) -> FrozenPixels:
        """Capture array pixels, sharing unchanged tiles with earlier content."""
        if array.dtype.hasobject:
            raise ValueError("history arrays must not contain Python objects")
        if previous is not None and (
            previous.shape != array.shape or previous.dtype != array.dtype
        ):
            previous = None
        layout = FrozenPixels(array.shape, array.dtype, ())
        chunks = []
        # Slice objects are not hashable on every supported Python; positional
        # indices also avoid making chunk dictionaries for large canvases.
        old_chunks = previous.chunks if previous is not None else ()
        height = array.shape[0] if array.ndim else 1
        width = array.shape[1] if array.ndim > 1 else 1
        for index, (y, x) in enumerate(
            (y, x) for y in range(0, height, TILE_SIZE) for x in range(0, width, TILE_SIZE)
        ):
            slices = (slice(y, y + TILE_SIZE), slice(x, x + TILE_SIZE))[:array.ndim]
            tile = array[slices]
            prior = old_chunks[index] if old_chunks else None
            if prior is not None and (_tile_outside(region, x, y) or _same_pixels(tile, prior)):
                chunks.append(prior)
            else:
                chunks.append(self._intern(tile))
        return FrozenPixels(layout.shape, layout.dtype, tuple(chunks))

    def _intern(self, tile: np.ndarray) -> _Chunk:
        """The shared chunk holding *tile*'s bytes, made on first sight."""
        data = tile.tobytes()
        chunk = self._chunks.get(data)
        if chunk is None:
            chunk = _Chunk(data)
            self._chunks[data] = chunk
        return chunk
