"""Move or copy files into a folder without ever overwriting what is already there.

``shutil.move`` and ``shutil.copy2`` replace an existing destination silently
(on Windows ``move`` falls back to a copy when the rename fails), and camera
files share names all the time: two cards both hold ``IMG_0001.JPG``. Every
"move / copy into a folder" action goes through :func:`transfer_into`, which
plans a unique name for each file with ``batch_move_planner`` and checks the
target again right before writing it.

A file's sidecars go with it (:func:`carry_along`): the XMP sidecar other
editors keep their edits in, and Imervue's annotations.
"""
from __future__ import annotations

import filecmp
import logging
import os
import shutil
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from Imervue.image.batch_move_planner import plan_batch_move

logger = logging.getLogger("Imervue.file_transfer")

# Sidecars named by appending to the image's whole name: darktable / digiKam's
# ``IMG.JPG.xmp`` and Imervue's ``IMG.JPG.annotations.json``. Adobe's
# ``IMG.xmp`` replaces the extension instead, so a RAW + JPEG pair shares it.
_APPENDED_SIDECARS = (".xmp", ".annotations.json")
_ADOBE_SIDECAR = ".xmp"


@dataclass
class TransferResult:
    """What :func:`transfer_into` did: ``(source, destination)`` pairs and failed sources."""

    done: list[tuple[str, str]] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def _path_key(path: str | Path) -> str:
    """*path* as the file system compares it: absolute, case-folded where names ignore case."""
    return os.path.normcase(os.path.abspath(path))


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
    that fails, counts the source as failed; the rest carry on. Each file
    brings its sidecars (and, when moved, its saved metadata) along; a
    sidecar that was also selected counts as done where it went.
    """
    dest = Path(dest_dir)
    try:
        existing = set(os.listdir(dest))
    except OSError:
        existing = set()
    result = TransferResult()
    carried: dict[str, str] = {}
    for plan in plan_batch_move(list(sources), str(dest), existing):
        if move and _same_folder(plan.source, dest):
            result.done.append((plan.source, plan.source))
            continue
        if _path_key(plan.source) in carried:   # already went along with its image
            result.done.append((plan.source, carried[_path_key(plan.source)]))
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
        carried.update(carry_along([(plan.source, str(target))], move=move))
    return result


def _sidecar_pairs(source: Path, target: Path) -> list[tuple[Path, Path, bool]]:
    """``(sidecar, its name beside target, is Adobe's IMG.xmp)`` per sidecar name of *source*."""
    pairs = [(source.with_name(source.name + suffix), target.with_name(target.name + suffix), False)
             for suffix in _APPENDED_SIDECARS]
    if source.suffix and source.suffix.lower() != _ADOBE_SIDECAR:
        pairs.append((source.with_suffix(_ADOBE_SIDECAR), target.with_suffix(_ADOBE_SIDECAR), True))
    return pairs


def _is_sidecar(name: str) -> bool:
    lowered = name.lower()
    return any(lowered.endswith(suffix) for suffix in _APPENDED_SIDECARS)


def _shares_adobe_sidecar(source: Path) -> bool:
    """Whether another ``IMG.*`` beside *source* (a RAW of the pair) still uses ``IMG.xmp``."""
    stem = os.path.normcase(source.stem)
    try:
        names = os.listdir(source.parent)
    except OSError:
        return False
    return any(os.path.normcase(os.path.splitext(name)[0]) == stem and not _is_sidecar(name)
               and os.path.normcase(name) != os.path.normcase(source.name) for name in names)


def _carry_sidecar(side: Path, new_side: Path, *, move: bool) -> bool:
    """Move (or copy) *side* to *new_side* unless another file is there; True if it got there."""
    if os.path.lexists(new_side) and not is_same_file(side, new_side):
        if not filecmp.cmp(side, new_side, shallow=False):
            logger.warning("Not overwriting %s; %s stays where it is", new_side, side)
            return False
        if move:                               # the same sidecar already went ahead
            side.unlink()
        return True
    if move:
        shutil.move(str(side), str(new_side))
    else:
        shutil.copy2(side, new_side)
    return True


def carry_along(pairs: Iterable[tuple[str, str]], *, move: bool) -> dict[str, str]:
    """Bring each file's sidecars from its old path to its new one.

    Returns the sidecars that arrived as ``{old path key: new path}``, keyed
    like :func:`_path_key`. For every ``(source, target)`` of a file already
    moved, renamed or copied:
    ``IMG.JPG.xmp`` (darktable, digiKam), ``IMG.JPG.annotations.json`` and
    ``IMG.xmp`` (Adobe) follow it, moved with a move and copied with a copy.
    ``IMG.xmp`` is copied instead while another ``IMG.*`` in the old folder
    still uses it (the RAW of a RAW + JPEG pair). A different file already at
    a sidecar's new name is never overwritten; that sidecar stays and a
    warning is logged. After a move, what Imervue saved for the files follows
    them too (:func:`follow_saved_data`; for a folder, for every file in it).
    """
    pairs = list(pairs)
    carried = carry_sidecars(pairs, move=move)
    if move:
        files = {source: target for source, target in pairs if not Path(target).is_dir()}
        folders = {source: target for source, target in pairs if Path(target).is_dir()}
        follow_saved_data(files, folders)
    return carried


def carry_sidecars(pairs: Iterable[tuple[str, str]], *, move: bool) -> dict[str, str]:
    """The file half of :func:`carry_along`: move or copy the sidecars, touch no saved data.

    Safe on a worker thread; the caller hands the moves to
    :func:`follow_saved_data` on the GUI thread. A folder's sidecars are
    inside it, so folders are skipped.
    """
    carried: dict[str, str] = {}
    for source, target in pairs:
        src, dst = Path(source), Path(target)
        if src.is_dir() or dst.is_dir():
            continue
        for side, new_side, adobe in _sidecar_pairs(src, dst):
            if not side.is_file():
                continue
            shared = adobe and _shares_adobe_sidecar(src)
            try:
                if _carry_sidecar(side, new_side, move=move and not shared):
                    carried[_path_key(side)] = str(new_side)
            except OSError:
                logger.warning("Could not carry %s to %s", side, new_side, exc_info=True)
    return carried


def sidecars_of(path: str) -> list[str]:
    """The sidecars beside *path* that belong to it alone, whether or not *path* still exists.

    ``IMG.JPG.xmp`` and ``IMG.JPG.annotations.json`` always; ``IMG.xmp`` only
    while no other ``IMG.*`` (the RAW of a RAW + JPEG pair) uses it.
    """
    image = Path(path)
    if image.is_dir():
        return []
    return [str(side) for side, _unused, adobe in _sidecar_pairs(image, image)
            if side.is_file() and not (adobe and _shares_adobe_sidecar(image))]


def follow_saved_data(files: Mapping[str, str], folders: Mapping[str, str] | None = None, *,
                      keep_existing: bool = False) -> None:
    """Re-key what Imervue saved per image path for files and folders now elsewhere.

    *files* and *folders* map old paths to new ones; a folder brings the data
    of every file inside it. Covers the settings (ratings, tags, labels,
    titles, bookmarks … — :func:`~Imervue.user_settings.path_metadata.move_path_metadata`)
    and the library (notes, cull state, hierarchical tags —
    :func:`~Imervue.library.image_index.move_paths`); *keep_existing* is
    passed to both. A library that can't be written is logged, not raised:
    the files have moved either way.
    """
    from Imervue.library import image_index
    from Imervue.user_settings.path_metadata import (
        folder_moves, move_path_metadata, stored_paths,
    )
    settings_moves, library_moves = dict(files), dict(files)
    for old, new in (folders or {}).items():
        settings_moves.update(folder_moves(old, new, stored_paths()))
    move_path_metadata(settings_moves, keep_existing=keep_existing)
    try:
        for old, new in (folders or {}).items():
            library_moves.update(folder_moves(old, new, image_index.stored_paths()))
        image_index.move_paths(library_moves, keep_existing=keep_existing)
    except sqlite3.Error:
        logger.warning("Could not re-point the library at moved files", exc_info=True)


def is_same_file(a: str | Path, b: str | Path) -> bool:
    """Whether *a* and *b* name one existing file — ``img.jpg`` and ``IMG.JPG`` on Windows.

    A rename to *b* then only changes the name's case (or nothing at all), so
    *b* "already existing" is no conflict.
    """
    try:
        return os.path.samefile(a, b)
    except OSError:   # either side missing or unreadable
        return False
