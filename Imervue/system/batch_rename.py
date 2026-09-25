"""Rename many files at once, where one file's new name may be another's old name.

Renumbering a folder (``002.jpg`` → ``003.jpg`` while ``003.jpg`` → ``004.jpg``)
only works when ``003.jpg`` moves out of the way first, and swapping two names
(or any cycle) only through a temporary name. :func:`rename_files` orders the
renames so each target is free when its turn comes, parks one file of each
cycle under a temporary name beside it, and never overwrites a file that is
not part of the batch.
"""
from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from Imervue.system.file_transfer import carry_sidecars, follow_saved_data, is_same_file

logger = logging.getLogger("Imervue.batch_rename")


@dataclass
class _Rename:
    source: str
    target: str
    at: str           # where the file is now: source, or its parking name inside a cycle
    settled: bool = False


def _key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def rename_files(pairs: Sequence[tuple[str, str]]) -> tuple[list[tuple[str, str]], int]:
    """Rename each ``(source, target)``; returns the pairs renamed and how many were not.

    A target may be the current name of another source in *pairs*: that one
    goes first, and a cycle (``a`` ↔ ``b``) passes through a temporary name,
    so the batch lands as a whole. Not renamed (counted in the second value):
    an unchanged name, a source listed twice, a target another pair already
    claimed, a target held by a file outside the batch, and a rename the OS
    refuses (which also stops any rename waiting for that name). A parked
    file whose rename fails goes back to its old name. Each file's sidecars
    follow it as it is renamed, and what Imervue saved for the files
    (rating, tags, notes …) follows the whole batch at the end.
    """
    renames, refused = _plan(pairs)
    occupants = {_key(rename.at): rename for rename in renames}
    renamed: list[tuple[str, str]] = []
    for start in renames:
        if start.settled:
            continue
        chain, cycle_start = _walk(start, occupants)
        if cycle_start is not None:
            _park(cycle_start)
        for rename in reversed(chain):
            if _finish(rename):
                renamed.append((rename.source, rename.target))
    if renamed:
        follow_saved_data(dict(renamed))
    return renamed, refused + len(renames) - len(renamed)


def _plan(pairs: Sequence[tuple[str, str]]) -> tuple[list[_Rename], int]:
    """The renames worth trying, in order, and how many were refused up front."""
    sources = {_key(source) for source, _target in pairs}
    seen_sources: set[str] = set()
    claimed: set[str] = set()
    renames: list[_Rename] = []
    refused = 0
    for source, target in pairs:
        source_key, target_key = _key(source), _key(target)
        outsider = (target_key not in sources and os.path.lexists(target)
                    and not is_same_file(source, target))
        if (os.path.abspath(source) == os.path.abspath(target) or outsider
                or source_key in seen_sources or target_key in claimed):
            refused += 1
            continue
        seen_sources.add(source_key)
        claimed.add(target_key)
        renames.append(_Rename(source, target, source))
    return renames, refused


def _walk(start: _Rename, occupants: dict[str, _Rename]) -> tuple[list[_Rename], _Rename | None]:
    """Follow *start* to whoever holds its target, and on; returns the chain and a cycle's start.

    Every target is claimed once, so the renames form separate chains and
    cycles: renaming the chain back to front frees each target in turn. A
    cycle comes back to a rename already walked, which is returned so it can
    be parked.
    """
    chain: list[_Rename] = []
    walked: set[int] = set()
    rename: _Rename | None = start
    while rename is not None and id(rename) not in walked:
        chain.append(rename)
        walked.add(id(rename))
        holder = occupants.get(_key(rename.target))
        # A case-only rename holds its own target; a settled one is out of the way or stuck.
        waiting = holder is not None and holder is not rename and not holder.settled
        rename = holder if waiting else None
    return chain, rename


def _parking_name(path: str) -> str:
    """A free name beside *path* that keeps its extension, so its sidecars keep their shape."""
    image = Path(path)
    while True:
        candidate = image.with_name(f"{image.stem}-renaming-{secrets.token_hex(4)}{image.suffix}")
        if not os.path.lexists(candidate):
            return str(candidate)


def _move(rename: _Rename, destination: str) -> None:
    """Rename the file at ``rename.at`` to *destination*, sidecars included; raises OSError."""
    os.rename(rename.at, destination)
    carry_sidecars([(rename.at, destination)], move=True)
    rename.at = destination


def _park(rename: _Rename) -> None:
    """Move a cycle's first file aside so the rename waiting for its name can go."""
    try:
        _move(rename, _parking_name(rename.at))
    except OSError:
        logger.warning("Could not move %s aside to rename it", rename.at, exc_info=True)


def _finish(rename: _Rename) -> bool:
    """Rename one file to its target if that is free now; True if it got there."""
    rename.settled = True
    if os.path.lexists(rename.target) and not is_same_file(rename.at, rename.target):
        logger.warning("Not renaming %s: %s is still taken", rename.source, rename.target)
    else:
        try:
            _move(rename, rename.target)
            return True
        except OSError:
            logger.warning("Could not rename %s to %s", rename.at, rename.target, exc_info=True)
    _unpark(rename)
    return False


def _unpark(rename: _Rename) -> None:
    """Put a parked file whose rename failed back under its old name."""
    if rename.at == rename.source:
        return
    if not os.path.lexists(rename.source):
        try:
            _move(rename, rename.source)
            return
        except OSError:
            logger.warning("Could not rename %s back", rename.at, exc_info=True)
    logger.error("%s was left as %s: its old name is taken", rename.source, rename.at)
