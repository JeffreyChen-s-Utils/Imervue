"""Per-document history of complete editable content, excluding runtime wiring.

Each gesture or explicit edit commits one snapshot. Snapshots include stack
structure, all layer properties and masks, vectors, groups, selections and
reference indices. Restoring keeps the live document and surviving layer
identities so canvases, docks and tool providers remain bound correctly.
"""
from __future__ import annotations

import copy
import weakref
from dataclasses import dataclass

from Imervue.paint.document import PaintDocument

MAX_UNDO_LEVELS = 50


@dataclass(frozen=True)
class _Snapshot:
    """Independent content plus weak identities for surviving layer objects."""

    document: PaintDocument
    layer_refs: tuple[weakref.ReferenceType, ...]


class UndoStack:
    """Bounded undo / redo stack tied to a single document."""

    def __init__(self, document: PaintDocument, *, max_levels: int = MAX_UNDO_LEVELS):
        if int(max_levels) < 1:
            raise ValueError(f"max_levels must be >= 1, got {max_levels}")
        self._document = document
        self._max_levels = int(max_levels)
        self._undo: list[_Snapshot] = []
        self._redo: list[_Snapshot] = []
        self._baseline = self._capture()

    @property
    def document(self) -> PaintDocument:
        """The live document, used to detect a wholesale document replacement."""
        return self._document

    def commit(self) -> None:
        """Remember the pre-edit state and discard the abandoned redo branch."""
        current = self._capture()
        self._undo.append(self._baseline)
        self._undo = self._undo[-self._max_levels:]
        self._redo.clear()
        self._baseline = current

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
        return True

    def _capture(self) -> _Snapshot:
        return _Snapshot(
            document=copy.deepcopy(self._document),
            layer_refs=tuple(weakref.ref(layer) for layer in self._document.layers()),
        )

    def _restore(self, snapshot: _Snapshot) -> None:
        state = copy.deepcopy(snapshot.document)
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
