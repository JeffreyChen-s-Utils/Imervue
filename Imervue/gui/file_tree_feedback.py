"""Report file-tree operation progress and deletion results."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from Imervue.multi_language.language_wrapper import language_wrapper


def toast(view, kind: str, message: Callable[[], str]) -> None:
    """Build and show a message only when the owning window supplies toasts."""
    if hasattr(view._main_window, "toast"):
        getattr(view._main_window.toast, kind)(message())


def _on_trash_progress(self, done: int, total: int) -> None:
    if hasattr(self._main_window, "show_progress"):
        self._main_window.show_progress(done, total)


def _notify_batch_result(self, already_removed: int, done: list[str]) -> None:
    """Summary toast for a multi-file delete once its trash calls land."""
    self._notify_deleted_batch(len(done) + already_removed)


def _notify_single_result(self, path: str, done: list[str]) -> None:
    """Per-file toast, only if the trash call actually took the file."""
    if done:
        self._notify_deleted(path)


def _notify_deleted(self, path: str) -> None:
    if not hasattr(self._main_window, "toast"):
        return
    lang = language_wrapper.language_word_dict
    self._main_window.toast.info(
        lang.get("tree_deleted", "Moved to trash: {name}").format(name=Path(path).name)
    )


def _notify_deleted_batch(self, count: int) -> None:
    """One summary toast after a multi-file delete."""
    if not hasattr(self._main_window, "toast"):
        return
    lang = language_wrapper.language_word_dict
    self._main_window.toast.info(
        lang.get("tree_deleted_batch", "Moved {count} items to trash").format(
            count=count,
        )
    )
