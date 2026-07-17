"""Per-document undo / redo stack for the paint workspace.

Captures snapshots of every layer's pixels plus the active selection
so any tool's mutation can be rolled back. The stack is bounded —
old snapshots are discarded when ``MAX_UNDO_LEVELS`` is reached so
a long editing session doesn't grow memory without bound.

Trade-offs:

* Snapshots copy each layer's full ``image`` buffer. For a 1024×1024
  canvas with three layers that's ~12 MB per snapshot — 50 levels
  bounded ≈ 600 MB. The level cap is exposed so a future preference
  dialog can lower it.
* No per-stroke delta encoding. Building a delta-based undo would
  cut memory dramatically but requires every tool to report its
  damage rect; the snapshot approach is correct unconditionally and
  good enough for the brush-eraser-shape-fill set.

The dispatcher is expected to call :meth:`UndoStack.commit` after
any event that returns ``True`` (i.e. mutated the canvas). The
workspace's Edit menu wires ``undo`` / ``redo`` to Ctrl+Z and
Ctrl+Y / Ctrl+Shift+Z respectively.
"""
from __future__ import annotations

import weakref
from dataclasses import dataclass

import numpy as np

from Imervue.paint.document import PaintDocument

MAX_UNDO_LEVELS = 50


@dataclass(frozen=True)
class _Snapshot:
    """One captured document state — layers + selection.

    Layer pixels are keyed by object identity (weak references), not by
    stack position: layers can be added, removed, or reordered between
    a capture and its restore, and an index-based mapping would write a
    captured image into whichever layer happens to occupy the old slot.
    Weak references keep deleted layers from being pinned in memory by
    old snapshots.
    """

    layer_refs: tuple[weakref.ReferenceType, ...]
    layer_images: tuple[np.ndarray, ...]
    selection: np.ndarray | None


class UndoStack:
    """Bounded undo / redo stack tied to a single :class:`PaintDocument`."""

    def __init__(
        self, document: PaintDocument, *,
        max_levels: int = MAX_UNDO_LEVELS,
    ):
        if int(max_levels) < 1:
            raise ValueError(
                f"max_levels must be >= 1, got {max_levels}",
            )
        self._document = document
        self._max_levels = int(max_levels)
        self._undo: list[_Snapshot] = []
        self._redo: list[_Snapshot] = []
        # Seed with the initial state so the first undo restores
        # the pre-edit canvas instead of leaving the user stuck on
        # whatever they just painted.
        self._baseline = self._capture()

    # ---- public API -----------------------------------------------------

    @property
    def document(self) -> PaintDocument:
        """The document this stack captures — used to detect a wholesale swap."""
        return self._document

    def commit(self) -> None:
        """Push the *current* state onto the undo stack.

        Discards the redo stack — once the user keeps editing past an
        undo point, the future is gone. Caps at ``max_levels``.
        """
        # The pre-mutation snapshot is whatever was pushed last (or
        # the baseline). What we want to push is THAT snapshot so an
        # undo restores it. The current state becomes the new
        # baseline.
        self._undo.append(self._baseline)
        if len(self._undo) > self._max_levels:
            self._undo = self._undo[-self._max_levels :]
        self._redo.clear()
        self._baseline = self._capture()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> bool:
        """Restore the most recently pushed snapshot. Returns ``True``
        when a snapshot was actually restored."""
        if not self._undo:
            return False
        snapshot = self._undo.pop()
        self._redo.append(self._capture())
        if len(self._redo) > self._max_levels:
            self._redo = self._redo[-self._max_levels :]
        self._restore(snapshot)
        self._baseline = snapshot
        return True

    def redo(self) -> bool:
        """Re-apply the most recently undone snapshot."""
        if not self._redo:
            return False
        snapshot = self._redo.pop()
        self._undo.append(self._capture())
        if len(self._undo) > self._max_levels:
            self._undo = self._undo[-self._max_levels :]
        self._restore(snapshot)
        self._baseline = snapshot
        return True

    def clear(self) -> None:
        """Forget every undo / redo snapshot.

        Called by the workspace when the document changes wholesale
        (open file / new document) so a stale undo doesn't roll back
        into a previous document's pixels.
        """
        self._undo.clear()
        self._redo.clear()
        self._baseline = self._capture()

    # ---- internals ------------------------------------------------------

    def _capture(self) -> _Snapshot:
        """Snapshot every layer image + the active selection."""
        layers = self._document.layers()
        layer_refs = tuple(weakref.ref(layer) for layer in layers)
        layer_images = tuple(
            np.ascontiguousarray(layer.image.copy()) for layer in layers
        )
        selection = self._document.selection()
        selection_copy = (
            np.ascontiguousarray(selection.copy())
            if selection is not None else None
        )
        return _Snapshot(
            layer_refs=layer_refs,
            layer_images=layer_images,
            selection=selection_copy,
        )

    def _restore(self, snapshot: _Snapshot) -> None:
        """Write a snapshot back to the document.

        Each captured image goes back into the layer object it was
        captured from, wherever that layer now sits in the stack.
        Layers added since the snapshot keep their pixels (the snapshot
        has nothing for them); layers removed since are not re-added
        (the snapshot only contains pixels, not stack structure).
        """
        current = self._document.layers()
        for ref, image in zip(
            snapshot.layer_refs, snapshot.layer_images, strict=True,
        ):
            layer = ref()
            if layer is None:
                continue  # captured layer was deleted and collected
            # Identity scan, not ``in`` — Layer is a dataclass whose
            # ``==`` would compare numpy fields elementwise.
            if not any(layer is live for live in current):
                continue  # deleted but still referenced elsewhere
            if layer.image.shape != image.shape:
                # A whole-canvas transform (rotate 90° / resize) changed this
                # layer's dimensions after the snapshot was captured; an in-place
                # ``np.copyto`` would raise a broadcast ValueError. Skip the stale
                # layer instead of crashing — transforms clear the stack, so this
                # is only a backstop for any snapshot that outlives a resize.
                continue
            np.copyto(layer.image, image)
        selection = snapshot.selection
        if selection is not None and selection.shape[:2] != self._document.shape:
            # A selection captured at the old size no longer maps onto the
            # resized canvas — drop it rather than restore a mismatched mask.
            selection = None
        self._document.set_selection(selection)
        self._document.invalidate_composite()
