"""Best-of-group culling — keep the strongest frame per group, reject the rest.

Burst / near-duplicate grouping (``library.events``, ``library.phash``) and
per-frame quality scoring (``image.sharpness`` / quality metrics) already
exist; this is the missing join: given groups of paths and a score per path,
pick the single best frame in each group and mark the others for rejection,
emitting a ``(picks, rejects)`` plan the caller can feed to the cull state.
Pure ranking — no I/O, no Qt; the caller supplies the score map.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

_MISSING_SCORE = float("-inf")


@dataclass(frozen=True)
class CullDecision:
    """The keeper and the rejects for one group."""

    keep: str
    reject: tuple[str, ...]


def best_in_group(group: Sequence[str], scores: Mapping[str, float]) -> str:
    """Return the highest-scoring path in *group* (first on ties, stable).

    Paths absent from *scores* are treated as the lowest possible score, so a
    scored frame always beats an unscored one. Raises ``ValueError`` on an
    empty group.
    """
    if not group:
        raise ValueError("cannot pick a best frame from an empty group")
    return max(group, key=lambda path: scores.get(path, _MISSING_SCORE))


def select_best_per_group(
    groups: Sequence[Sequence[str]], scores: Mapping[str, float],
) -> list[CullDecision]:
    """Return one :class:`CullDecision` per non-empty group."""
    decisions: list[CullDecision] = []
    for group in groups:
        members = list(group)
        if not members:
            continue
        keep = best_in_group(members, scores)
        reject = tuple(path for path in members if path != keep)
        decisions.append(CullDecision(keep=keep, reject=reject))
    return decisions


def plan_group_cull(
    groups: Sequence[Sequence[str]], scores: Mapping[str, float],
) -> tuple[list[str], list[str]]:
    """Return ``(picks, rejects)`` flattened across every group's decision."""
    decisions = select_best_per_group(groups, scores)
    picks = [decision.keep for decision in decisions]
    rejects = [path for decision in decisions for path in decision.reject]
    return picks, rejects
