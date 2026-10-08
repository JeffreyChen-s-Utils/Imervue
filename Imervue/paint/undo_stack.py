"""Per-document history of complete editable content, excluding runtime wiring.

Each gesture or explicit edit commits one snapshot. Snapshots include stack
structure, all layer properties and masks, vectors, groups, selections and
reference indices. Restoring keeps the live document and surviving layer
identities so canvases, docks and tool providers remain bound correctly.
"""
from __future__ import annotations

import copy
import logging
import weakref
from dataclasses import dataclass

import numpy as np

from Imervue.paint.document import PaintDocument
from Imervue.paint.damage import DamageRect
from Imervue.paint.history_pixels import FrozenPixels, PixelStore, arrays_in, owned_bytes

MAX_UNDO_LEVELS = 50
MAX_UNDO_BYTES = 512 * 1024 * 1024
logger = logging.getLogger("Imervue.paint.history")


@dataclass(frozen=True)
class _Snapshot:
    """Independent content plus weak identities for surviving layer objects."""

    document: PaintDocument
    layer_refs: tuple[weakref.ReferenceType, ...]
    arrays: tuple[tuple[weakref.ReferenceType, FrozenPixels], ...]

    def materialize(self) -> PaintDocument:
        """Return an independent editable document, safe to build on a worker."""
        return copy.deepcopy(self.document)


class UndoStack:
    """Bounded undo / redo stack tied to a single document."""

    def __init__(self, document: PaintDocument, *, max_levels: int = MAX_UNDO_LEVELS,
                 max_bytes: int = MAX_UNDO_BYTES):
        if int(max_levels) < 1:
            raise ValueError(f"max_levels must be >= 1, got {max_levels}")
        self._document = document
        self._max_levels = int(max_levels)
        if int(max_bytes) < 1:
            raise ValueError(f"max_bytes must be >= 1, got {max_bytes}")
        self._max_bytes = int(max_bytes)
        self._store = PixelStore()
        self._undo: list[_Snapshot] = []
        self._redo: list[_Snapshot] = []
        self._baseline: _Snapshot | None = None
        self._baseline = self._capture()
        self._trim()

    @property
    def document(self) -> PaintDocument:
        """The live document, used to detect a wholesale document replacement."""
        return self._document

    @property
    def history_bytes(self) -> int:
        """Unique retained tile bytes and Python state, including both branches."""
        if self._baseline is None and not self._undo and not self._redo:
            return 0
        return owned_bytes((self._baseline, self._undo, self._redo, self._store))

    def committed_snapshot(self) -> _Snapshot:
        """Share immutable committed content; its materializer owns all new arrays."""
        return self._baseline if self._baseline is not None else self._capture()

    @property
    def available_snapshot(self) -> _Snapshot | None:
        """Already immutable committed state, or None when the history byte cap disabled it."""
        return self._baseline

    def commit(self, *, regions: tuple[tuple[np.ndarray, DamageRect], ...] | None = None) -> None:
        """Commit content; optional hints must cover EVERY array changed by the edit."""
        current = self._capture(regions=regions)
        if self._baseline is not None:
            self._undo.append(self._baseline)
        discarded = bool(self._redo) or len(self._undo) > self._max_levels
        self._undo = self._undo[-self._max_levels:]
        self._redo.clear()
        self._baseline = current
        if discarded:
            self._compact()
        self._trim()

    def can_undo(self) -> bool:
        """Whether an older state is available."""
        return bool(self._undo)

    def can_redo(self) -> bool:
        """Whether an undone state is available."""
        return bool(self._redo)

    def undo(self) -> bool:
        """Restore the previous complete document; return False at the boundary."""
        return self._step(self._undo, self._redo)

    def redo(self) -> bool:
        """Restore the next complete document; return False at the boundary."""
        return self._step(self._redo, self._undo)

    def clear(self) -> None:
        """Reset history to the current content after opening a document."""
        self._undo.clear()
        self._redo.clear()
        self._baseline = self._capture()
        self._compact()
        self._trim()

    def _step(self, source: list[_Snapshot], destination: list[_Snapshot]) -> bool:
        if not source:
            return False
        current = self._capture()
        snapshot = source[-1]
        self._restore(snapshot)
        source.pop()
        destination.append(current)
        del destination[:-self._max_levels]
        self._baseline = snapshot
        self._trim()
        return True

    def _trim(self) -> None:
        while self.history_bytes > self._max_bytes:
            if self._undo:
                self._undo.pop(0)
            elif self._redo:
                self._redo.pop(0)
            elif self._baseline is not None:
                logger.warning("document snapshot exceeds history budget; undo history cleared")
                self._baseline = None
            else:
                break
            self._compact()

    def _compact(self) -> None:
        retained = [*self._undo, *self._redo]
        if self._baseline is not None:
            retained.append(self._baseline)
        self._store.compact(pixels for snapshot in retained for _, pixels in snapshot.arrays)

    def _capture(self, *, regions=None) -> _Snapshot:
        previous = {id(ref()): (ref, pixels) for ref, pixels in self._baseline.arrays
                    if ref() is not None} if self._baseline is not None else {}
        damage = ({id(array): (array, rect) for array, rect in regions}
                  if regions is not None else {})
        memo = {}
        arrays = []
        for array in arrays_in(self._document):
            prior = previous.get(id(array))
            frozen = prior[1] if prior is not None and prior[0]() is array else None
            if regions is not None and frozen is not None and id(array) not in damage:
                pixels = frozen
            else:
                rect = damage[id(array)][1] if id(array) in damage else None
                pixels = self._store.freeze(array, frozen, region=rect)
            memo[id(array)] = pixels
            arrays.append((weakref.ref(array), pixels))
        return _Snapshot(
            document=copy.deepcopy(self._document, memo),
            layer_refs=tuple(weakref.ref(layer) for layer in self._document.layers()),
            arrays=tuple(arrays),
        )

    def _restore(self, snapshot: _Snapshot) -> None:
        live_arrays = {id(array): array for array in arrays_in(self._document)}
        memo = {}
        for ref, pixels in snapshot.arrays:
            array = ref()
            if array is not None and live_arrays.get(id(array)) is array and array.flags.writeable:
                pixels.restore_into(array)
                memo[id(pixels)] = array
        state = copy.deepcopy(snapshot.document, memo)
        layers = []
        for ref, stored in zip(snapshot.layer_refs, state.layers(), strict=True):
            layer = ref()
            if layer is None:
                layer = stored
            else:
                vars(layer).update(vars(stored))
            layers.append(layer)
        state._layers = layers  # noqa: SLF001 - owned content, not runtime wiring
        self._document.adopt_content(state)
