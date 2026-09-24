"""Move or copy files into a folder without ever overwriting what is already there.

``shutil.move`` and ``shutil.copy2`` replace an existing destination silently
(on Windows ``move`` falls back to a copy when the rename fails), and camera
files share names all the time: two cards both hold ``IMG_0001.JPG``. Every
"move / copy into a folder" action goes through :func:`transfer_into`, which
plans a unique name for each file with ``batch_move_planner`` and checks the
target again right before writing it.
"""
from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from Imervue.image.batch_move_planner import plan_batch_move

logger = logging.getLogger("Imervue.file_transfer")


@dataclass
class TransferResult:
    """What :func:`transfer_into` did: ``(source, destination)`` pairs and failed sources."""

    done: list[tuple[str, str]] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def _same_folder(source: str, dest_dir: Path) -> bool:
    try:
        return Path(source).parent.resolve() == dest_dir.resolve()
    except OSError:
        return False


def _transfer_one(source: str, target: Path, *, move: bool) -> None:
    if move:
        shutil.move(source, str(target))
    elif Path(source).is_dir():
        shutil.copytree(source, str(target))
    else:
        shutil.copy2(source, str(target))


def transfer_into(sources: Sequence[str], dest_dir: str | Path, *, move: bool) -> TransferResult:
    """Move (or copy) *sources* into *dest_dir*, renaming instead of overwriting.

    A name already in the folder, or taken by an earlier source in this batch,
    becomes ``name_1.ext`` (then ``_2`` …); the comparison follows the file
    system's case rules. Moving a file into the folder it already sits in is a
    no-op. A target that appears between planning and writing, or a transfer
    that fails, counts the source as failed; the rest carry on.
    """
    dest = Path(dest_dir)
    try:
        existing = set(os.listdir(dest))
    except OSError:
        existing = set()
    result = TransferResult()
    for plan in plan_batch_move(list(sources), str(dest), existing):
        if move and _same_folder(plan.source, dest):
            result.done.append((plan.source, plan.source))
            continue
        target = Path(plan.destination)
        if os.path.lexists(target):
            logger.warning("Not overwriting %s, which appeared during the transfer", target)
            result.failed.append(plan.source)
            continue
        try:
            _transfer_one(plan.source, target, move=move)
        except OSError:
            logger.warning("Could not %s %s to %s", "move" if move else "copy",
                           plan.source, target, exc_info=True)
            result.failed.append(plan.source)
            continue
        result.done.append((plan.source, str(target)))
    return result
