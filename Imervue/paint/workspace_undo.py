"""Per-canvas undo / redo and history feedback for the Paint workspace.

Split out of :mod:`paint_workspace` to keep the coordinator small.
:class:`UndoHistoryMixin` is composed into
:class:`Imervue.paint.paint_workspace.PaintWorkspace`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.paint.undo_stack import UndoStack


def _pointer_button_held(buttons) -> bool:
    """True while the left mouse button is down.

    Used to defer undo/redo that arrives mid-brush-stroke (Ctrl+Z with the
    button still held): the undo would restore a committed state that the
    in-flight stroke then overwrites when it syncs its FBO to the layer on
    release, silently discarding the undo.
    """
    return bool(buttons & Qt.MouseButton.LeftButton)


class UndoHistoryMixin:
    """One undo stack per canvas, undo / redo commands and their toasts.

    Expects the host to provide ``_canvas``, ``_undo_stacks``,
    ``_set_tab_dirty`` and (optionally) ``_dispatcher``, ``toast`` and
    ``_status``.
    """

    @property
    def _undo_stack(self) -> UndoStack:
        """The active canvas's undo stack (created on demand).

        Per-canvas so a tab switch can't apply one document's history to
        another. Recreated when the canvas's *document object* is replaced
        wholesale (open file / new document) — matching the old ``clear()``
        intent — while a mere in-place mutation (a brush dab) keeps the same
        object and so the same history.
        """
        from Imervue.paint.undo_stack import UndoStack
        canvas = self._canvas
        document = canvas.document()
        stack = self._undo_stacks.get(canvas)
        if stack is None or stack.document is not document:
            stack = UndoStack(document)
            self._undo_stacks[canvas] = stack
        return stack

    def _on_dispatcher_commit(self) -> None:
        """Push an undo snapshot after the dispatcher commits a stroke.

        Called by the dispatcher only at gesture boundaries so a long
        brush stroke counts as one undoable action rather than every
        dab. Also flips the active tab to "modified".
        """
        regions = getattr(getattr(self, "_dispatcher", None), "history_regions", None)
        if regions is None:
            self._undo_stack.commit()
        else:
            self._undo_stack.commit(regions=regions)
        self._set_tab_dirty(self._canvas, True)

    def undo(self) -> None:
        """Undo the most recent committed stroke if there is one."""
        if self._pointer_stroke_active():
            return
        if self._undo_stack.undo():
            self._set_tab_dirty(self._canvas, True)
            self._canvas.invalidate_texture()
            self._canvas.update()
            self._notify_history_action("undo")
        else:
            self._notify_history_empty("undo")

    def redo(self) -> None:
        """Re-apply the most recently undone stroke."""
        if self._pointer_stroke_active():
            return
        if self._undo_stack.redo():
            self._set_tab_dirty(self._canvas, True)
            self._canvas.invalidate_texture()
            self._canvas.update()
            self._notify_history_action("redo")
        else:
            self._notify_history_empty("redo")

    @staticmethod
    def _pointer_stroke_active() -> bool:
        """Whether a mouse button is currently held (a brush stroke may be in
        progress), so undo/redo should defer until it's released."""
        from PySide6.QtWidgets import QApplication
        return _pointer_button_held(QApplication.mouseButtons())

    def _notify_history_action(self, kind: str) -> None:
        """Toast a confirmation after a successful undo / redo.

        Surfaces the action *and* the remaining depth so the user can
        pace their Ctrl+Z taps without overshooting.
        """
        lang = language_wrapper.language_word_dict
        verb = lang.get(f"paint_history_{kind}", kind.title())
        depth = self._history_depth_for(kind)
        msg = lang.get(
            "paint_history_done", "{verb} ({depth} left)",
        ).format(verb=verb, depth=depth)
        self._broadcast_history_msg(msg, level="info")

    def _notify_history_empty(self, kind: str) -> None:
        lang = language_wrapper.language_word_dict
        msg = lang.get(
            f"paint_history_{kind}_empty",
            "Nothing to {kind}",
        ).format(kind=kind)
        self._broadcast_history_msg(msg, level="warning")

    def _history_depth_for(self, kind: str) -> int:
        """Return how many steps remain in the requested direction.

        Falls back to ``0`` rather than crashing if the underlying
        :class:`UndoStack` doesn't expose the queried side.
        """
        if kind == "undo":
            stack = getattr(self._undo_stack, "_undo", ())
        else:
            stack = getattr(self._undo_stack, "_redo", ())
        return len(stack) if stack is not None else 0

    def _broadcast_history_msg(self, msg: str, *, level: str) -> None:
        toast = getattr(self, "toast", None)
        if toast is not None:
            target = getattr(toast, level, None)
            if callable(target):
                target(msg)
                return
        status = getattr(self, "_status", None)
        if status is not None:
            status.showMessage(msg, 2000)

    def _ensure_undo_stack(self) -> None:
        """Force the active canvas's undo stack into existence at bind time.

        Its baseline snapshots the current (blank / just-loaded) state. Left to
        lazy creation, the first access is the first commit -- after the stroke
        already mutated the layer -- so the baseline captured the post-stroke
        state and the first undo restored it (a no-op), losing the pre-stroke
        canvas."""
        _ = self._undo_stack
