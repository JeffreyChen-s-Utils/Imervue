"""Diff and selectively merge develop :class:`Recipe` objects.

The develop pipeline can copy a whole recipe between images, but not a *subset*
of it — there's no way to paste just the exposure and white balance from one
shot onto a batch. These pure helpers diff two recipes field-by-field and merge
only chosen fields, so the UI can offer "copy these adjustments". Iterates the
dataclass fields generically, so new recipe fields are picked up automatically.
Pure dataclass work — no Qt, no I/O.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import fields, replace
from typing import Any, cast

from Imervue.image.recipe import Recipe


def _field_names() -> set[str]:
    return {f.name for f in fields(Recipe)}


def recipe_diff(base: Recipe, other: Recipe) -> dict[str, tuple[Any, Any]]:
    """Return ``{field: (base_value, other_value)}`` for every differing field."""
    diff: dict[str, tuple[Any, Any]] = {}
    for name in _field_names():
        base_value = getattr(base, name)
        other_value = getattr(other, name)
        if base_value != other_value:
            diff[name] = (base_value, other_value)
    return diff


def changed_fields(base: Recipe, other: Recipe) -> list[str]:
    """Return the sorted names of fields that differ between two recipes."""
    return sorted(recipe_diff(base, other))


def selective_merge(
    target: Recipe, source: Recipe, field_names: Iterable[str],
) -> Recipe:
    """Return a copy of *target* with only *field_names* taken from *source*.

    Raises :class:`ValueError` for an unknown field name. Neither input is
    mutated.
    """
    names = set(field_names)
    unknown = names - _field_names()
    if unknown:
        raise ValueError(f"unknown recipe field(s): {sorted(unknown)}")
    # ``replace`` returns the dataclass type; make it explicit for analysers.
    return cast(Recipe, replace(target, **{name: getattr(source, name) for name in names}))


def copy_active_adjustments(target: Recipe, source: Recipe) -> Recipe:
    """Return *target* with every field *source* sets away from its default.

    Equivalent to ``selective_merge`` over the fields where *source* differs
    from a default (identity) recipe — a "paste the adjustments that are
    actually on" operation. Neither input is mutated.
    """
    active = changed_fields(Recipe(), source)
    return selective_merge(target, source, active)
