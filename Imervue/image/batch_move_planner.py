"""Plan collision-free batch moves across folders.

``library.token_rename`` renames within a folder; moving a set of files *into*
another folder needs the complementary step — deciding what happens when an
incoming name already exists there (or two sources share a name). This builds a
dry-run plan (rename / skip / replace per file) so the UI can preview it before
touching the disk. Pure path logic: the caller supplies the destination's
existing filenames, so there is no filesystem I/O here.
"""
from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ACTION_MOVE = "move"
ACTION_RENAME = "rename"
ACTION_REPLACE = "replace"
ACTION_SKIP = "skip"

STRATEGY_NUMBER = "number"
STRATEGY_SKIP = "skip"
STRATEGY_REPLACE = "replace"
_STRATEGIES = (STRATEGY_NUMBER, STRATEGY_SKIP, STRATEGY_REPLACE)


@dataclass(frozen=True)
class MovePlan:
    """One planned move: where it goes, what action, and why."""

    source: str
    destination: str | None  # None when the move is skipped
    action: str
    reason: str


def resolve_name_collision(name: str, existing: set[str]) -> str:
    """Return *name* if free, else a numbered variant unique within *existing*.

    ``photo.jpg`` becomes ``photo_1.jpg`` (then ``photo_2.jpg`` …); the
    extension is preserved and dot-files keep their leading dot.
    """
    if name not in existing:
        return name
    stem, ext = os.path.splitext(name)
    counter = 1
    while f"{stem}_{counter}{ext}" in existing:
        counter += 1
    return f"{stem}_{counter}{ext}"


def plan_batch_move(
    sources: Sequence[str],
    dest_dir: str,
    existing: set[str],
    *,
    strategy: str = STRATEGY_NUMBER,
) -> list[MovePlan]:
    """Plan moving *sources* into *dest_dir*, resolving name collisions.

    *existing* is the set of filenames already in *dest_dir*. Collisions (with
    existing files or with earlier sources in the batch) are handled by
    *strategy*: ``"number"`` renames to a unique variant, ``"skip"`` drops the
    move, ``"replace"`` overwrites. Raises :class:`ValueError` for an unknown
    strategy. No filesystem access — returns a dry-run plan.
    """
    if strategy not in _STRATEGIES:
        raise ValueError(f"strategy must be one of {_STRATEGIES}, got {strategy!r}")
    dest = Path(dest_dir)
    claimed = set(existing)
    plans: list[MovePlan] = []
    for source in sources:
        name = Path(source).name
        if name not in claimed:
            claimed.add(name)
            plans.append(MovePlan(source, str(dest / name), ACTION_MOVE, "no collision"))
        else:
            plans.append(_resolve_collision(source, name, dest, claimed, strategy))
    return plans


def _resolve_collision(
    source: str, name: str, dest: Path, claimed: set[str], strategy: str,
) -> MovePlan:
    if strategy == STRATEGY_SKIP:
        return MovePlan(source, None, ACTION_SKIP, f"{name} already exists")
    if strategy == STRATEGY_REPLACE:
        return MovePlan(source, str(dest / name), ACTION_REPLACE, f"overwrites {name}")
    unique = resolve_name_collision(name, claimed)
    claimed.add(unique)
    return MovePlan(source, str(dest / unique), ACTION_RENAME, f"renamed to {unique}")
