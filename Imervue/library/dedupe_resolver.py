"""Pick the best image to keep from a group of duplicates.

The duplicate finder produces groups of near-identical images; this decides,
per group, which one to keep and which to discard. The ranking is pure
(resolution first, then file size as a proxy for compression quality) so the
"keep best, trash the rest" wizard and its tests share one rule. Loading pixel
dimensions stays in the caller — this module only ranks the supplied metadata.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """One member of a duplicate group with the metadata used to rank it."""

    path: str
    width: int
    height: int
    size_bytes: int


def resolve_group(
    candidates: Iterable[Candidate],
) -> tuple[Candidate | None, list[Candidate]]:
    """Return ``(keep, discard)`` for one duplicate group.

    The keeper has the most pixels, then the largest file; ties are broken by
    the lexicographically smallest path so the result is stable. An empty group
    yields ``(None, [])`` and a single image is kept with nothing discarded.
    """
    members = list(candidates)
    if not members:
        return None, []
    # Best pixels/size first; among equals, smallest path first (stable keep).
    keeper = min(
        members,
        key=lambda c: (-c.width * c.height, -c.size_bytes, c.path),
    )
    discard = [c for c in members if c.path != keeper.path]
    return keeper, discard


def resolve_groups(
    groups: Iterable[Iterable[Candidate]],
) -> list[tuple[Candidate, list[Candidate]]]:
    """Resolve every group, skipping those with nothing to keep."""
    resolved: list[tuple[Candidate, list[Candidate]]] = []
    for group in groups:
        keeper, discard = resolve_group(group)
        if keeper is not None:
            resolved.append((keeper, discard))
    return resolved


def plan_discards(groups: Iterable[Iterable[Candidate]]) -> list[str]:
    """Flat list of paths to discard across all groups (keepers excluded)."""
    return [c.path for _keep, discard in resolve_groups(groups) for c in discard]
