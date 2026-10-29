"""Motion / expression playback and file drops for :class:`PetWindow`.

``PetPlaybackMixin`` plays motions (by object, by name, or at random from a
group), toggles expressions, and dispatches files dropped onto the pet: a
``.puppet`` archive becomes the new rig, anything else plays the Drop group.
It relies on the host window's ``_motion_player``, ``_canvas``,
``_speech_enabled`` and ``_script_engine`` plus its ``document``,
``load_puppet_file``, ``_show_speech`` and ``hit_triggered`` signal.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QDragEnterEvent, QDropEvent

from Imervue.puppet.motion_picker import pick_random_motion_in_group

DROP_MOTION_GROUP: str = "Drop"
"""Played when the user drops *external content* (a file from
Explorer / Finder) onto the pet. Distinct from ``LAND_MOTION_GROUP``
so rigs can react differently to "moved the pet" vs "fed the pet
something"."""

PUPPET_FILE_SUFFIX: str = ".puppet"
"""Extension treated as "drop this and the pet loads it as its new
rig". Anything else triggers the generic Drop reaction instead."""


def classify_drop_paths(paths: list[Path]) -> tuple[str, Path | None]:
    """Decide what the pet should do with a file-drop payload.

    Returns ``("puppet", path)`` when the drop contains at least one
    ``.puppet`` archive (the first one wins — multiple-file drops
    aren't a use case worth solving), ``("other", path_or_None)``
    when the drop has files but none are a rig (the first path is
    handed back so callers can log / display it), or ``("none", None)``
    for an empty payload.

    Pure helper so the dispatcher logic is tested without spinning
    up a QMimeData — Qt's drop machinery is hard to fake."""
    if not paths:
        return ("none", None)
    for path in paths:
        if path.suffix.lower() == PUPPET_FILE_SUFFIX:
            return ("puppet", path)
    return ("other", paths[0])


class PetPlaybackMixin:
    """Motion, expression and file-drop behaviour mixed into ``PetWindow``."""

    # =====================================================================
    # Motion / expression playback (context menu + hit-area)
    # =====================================================================

    def _play_motion(self, motion) -> None:
        """Bind ``motion`` on the player and start playback. Used
        from the context-menu motions submenu."""
        self._motion_player.set_motion(motion)
        self._motion_player.play()

    def play_motion(self, motion) -> None:
        """Public alias used by the context-menu motions submenu."""
        self._play_motion(motion)

    def apply_expression(self, name: str) -> None:
        """Toggle ``name`` on or off (the context-menu expressions submenu)."""
        self._apply_expression(name)

    def play_group(self, group: str) -> bool:
        return self.play_random_motion_in_group(group)

    # ---- file drag-drop -------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:   # noqa: N802 - Qt override
        """Accept drops that carry file URLs. Anything else (text,
        in-app drags) is ignored so we don't intercept random
        events from elsewhere in the app."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:   # noqa: N802 - Qt override
        """Thin glue over :meth:`handle_dropped_paths` — Qt's drop
        event class is awkward to construct in tests, so all the
        real dispatch logic sits in the path-based helper that
        tests can drive directly."""
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile() and url.toLocalFile()
        ]
        self.handle_dropped_paths(paths)
        event.acceptProposedAction()

    def handle_dropped_paths(self, paths: list[Path]) -> str:
        """Dispatch a list of dropped paths. Returns the same kind
        string :func:`classify_drop_paths` produces so callers (and
        tests) can verify which branch ran. Side effects:

        * ``"puppet"`` → loads the rig and emits ``hit_triggered("")``.
        * ``"other"``  → plays the Drop motion group + a greeting.
        * ``"none"``   → no-op.
        """
        kind, target = classify_drop_paths(paths)
        if kind == "puppet" and target is not None:
            self.load_puppet_file(target)
            self.hit_triggered.emit("")
        elif kind == "other":
            self.play_random_motion_in_group(DROP_MOTION_GROUP)
            if self._speech_enabled:
                line = (
                    self._script_engine.pick_time_of_day_greeting()
                    or self._script_engine.pick_greeting()
                )
                if line:
                    self._show_speech(line)
        return kind

    def play_random_motion_in_group(self, group: str) -> bool:
        """Pick + play a random motion from ``group``. Returns ``True``
        when the rig had at least one motion in the group and playback
        was started; ``False`` is a silent no-op (rigs without authored
        Drag / Land groups still work)."""
        last_name = (
            self._motion_player.motion().name
            if self._motion_player.motion() is not None
            else None
        )
        motion = pick_random_motion_in_group(
            self.document(), group, exclude_name=last_name,
        )
        if motion is None:
            return False
        self._play_motion(motion)
        return True

    def _play_motion_by_name(self, name: str) -> None:
        document = self.document()
        if document is None:
            return
        for motion in document.motions:
            if motion.name == name:
                self._play_motion(motion)
                return

    def _apply_expression(self, name: str) -> None:
        """Toggle an expression: add it, or take it off when it is already on.

        The context menu shows each expression checked while it is active;
        before, an applied expression stayed until the rig was reloaded.
        """
        canvas = self._canvas
        if name in canvas.active_expressions():
            canvas.remove_expression(name)
        else:
            canvas.add_expression(name)
