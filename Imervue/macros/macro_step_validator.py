"""Validate and tidy recorded macro steps.

``macro_manager`` records ``MacroStep(action, kwargs)`` entries and silently
skips any whose action isn't in ``ACTION_REGISTRY`` at replay — so a macro can
carry dead or redundant steps with no feedback. These pure helpers check a step
list against a known-action set, flag the steps that would be skipped, collapse
consecutive duplicates, and spot add/remove-tag pairs that cancel out. The
known-action set is injected, so this stays Qt-free and independent of the
manager singleton.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from Imervue.macros.macro_manager import MacroStep

_ADD_TAG = "add_tag"
_REMOVE_TAG = "remove_tag"
_TAG_KEY = "tag"

CODE_UNKNOWN_ACTION = "unknown_action"
CODE_BAD_KWARGS = "bad_kwargs"


@dataclass(frozen=True)
class StepIssue:
    """A problem with one step: its index, a stable code and a detail string."""

    index: int
    code: str
    detail: str


def validate_steps(
    steps: Sequence[MacroStep], known_actions: Iterable[str],
) -> list[StepIssue]:
    """Return issues for steps that would misbehave on replay.

    Flags actions absent from *known_actions* (skipped at replay) and steps
    whose ``kwargs`` is not a dict.
    """
    known = set(known_actions)
    issues: list[StepIssue] = []
    for index, step in enumerate(steps):
        if step.action not in known:
            issues.append(StepIssue(
                index, CODE_UNKNOWN_ACTION,
                f"{step.action!r} is not a known action (skipped on replay)"))
        elif not isinstance(step.kwargs, dict):
            issues.append(StepIssue(
                index, CODE_BAD_KWARGS,
                f"kwargs must be a dict, got {type(step.kwargs).__name__}"))
    return issues


def find_unknown_actions(
    steps: Sequence[MacroStep], known_actions: Iterable[str],
) -> list[str]:
    """Return the distinct action names in *steps* not in *known_actions*
    (first-seen order)."""
    known = set(known_actions)
    seen: list[str] = []
    for step in steps:
        if step.action not in known and step.action not in seen:
            seen.append(step.action)
    return seen


def deduplicate_consecutive(steps: Sequence[MacroStep]) -> list[MacroStep]:
    """Collapse runs of identical consecutive steps (same action and kwargs)."""
    out: list[MacroStep] = []
    for step in steps:
        if not out or (out[-1].action, out[-1].kwargs) != (step.action, step.kwargs):
            out.append(step)
    return out


def find_redundant_tag_pairs(steps: Sequence[MacroStep]) -> list[tuple[int, int]]:
    """Return ``(add_index, remove_index)`` pairs that cancel out.

    Within each tag's own sequence of add/remove ops, an ``add_tag`` immediately
    followed by a ``remove_tag`` of the same tag is a net no-op. Returned sorted
    by add index.
    """
    by_tag: dict[str, list[tuple[int, str]]] = {}
    for index, step in enumerate(steps):
        if step.action in (_ADD_TAG, _REMOVE_TAG):
            tag = step.kwargs.get(_TAG_KEY) if isinstance(step.kwargs, dict) else None
            if isinstance(tag, str):
                by_tag.setdefault(tag, []).append((index, step.action))
    pairs: list[tuple[int, int]] = []
    for ops in by_tag.values():
        for (first_index, first_op), (second_index, second_op) in zip(
            ops, ops[1:], strict=False,
        ):
            if first_op == _ADD_TAG and second_op == _REMOVE_TAG:
                pairs.append((first_index, second_index))
    return sorted(pairs)
