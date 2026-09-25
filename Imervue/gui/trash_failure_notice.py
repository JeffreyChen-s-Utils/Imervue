"""Ask what to do with deleted files the Recycle Bin could not take.

A file on a drive without a Recycle Bin (a memory card, USB stick or network
share), or one another program holds, stays where it is when Imervue commits
its deletions (``trash_ops.recycle_bin_holds``). Saying nothing made the
delete look lost; deleting it for good unasked is what the Recycle Bin is
there to prevent. So the user sees the files and decides.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtWidgets import QMessageBox, QWidget

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.trash_ops import delete_outright

logger = logging.getLogger("Imervue.trash_failure_notice")

_LISTED = 10          # paths spelled out in the message; the rest become "…"


def _ask_to_delete_permanently(parent: QWidget | None, paths: Sequence[str]) -> bool:
    """Whether the user chose to delete *paths* for good; keeping them is the default."""
    lang = language_wrapper.language_word_dict
    listing = "\n".join(paths[:_LISTED]) + ("\n…" if len(paths) > _LISTED else "")
    text = lang.get(
        "trash_left_in_place",
        "{count} deleted file(s) could not go to the Recycle Bin and are still on disk: "
        "their drive has none (a memory card, USB stick or network share), or another "
        "program is using them.\n\n{paths}\n\nDelete them permanently? This cannot be undone.",
    ).format(count=len(paths), paths=listing)
    box = QMessageBox(
        QMessageBox.Icon.Warning,
        lang.get("trash_left_in_place_title", "Not moved to the Recycle Bin"), text,
        QMessageBox.StandardButton.NoButton, parent)
    delete = box.addButton(lang.get("recycle_bin_purge", "Delete Forever"),
                           QMessageBox.ButtonRole.DestructiveRole)
    keep = box.addButton(lang.get("trash_keep_files", "Keep Them"),
                         QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(keep)
    box.exec()
    return box.clickedButton() is delete


def offer_permanent_delete(parent: QWidget | None, paths: Sequence[str]) -> list[str]:
    """List the files left in place and delete them for good if the user says so.

    Returns the paths removed (a folder with its contents, a file with its
    sidecars); nothing is asked when *paths* is empty.
    """
    paths = list(paths)
    if not paths or not _ask_to_delete_permanently(parent, paths):
        return []
    removed, failed = delete_outright(paths)
    for path in failed:
        logger.warning("Couldn't delete %s permanently either; it is still on disk", path)
    return removed
