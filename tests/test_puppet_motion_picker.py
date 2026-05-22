"""Tests for :func:`pick_random_motion_in_group`.

The picker is the shared policy used by every "play a random motion
from a named group" caller (idle cycler, drag / land hooks, future
event triggers). It's a pure function over the document → easy to
test without any Qt.
"""
from __future__ import annotations

from Imervue.puppet.document import (
    Motion,
    MotionSegment,
    MotionTrack,
    PuppetDocument,
)
from Imervue.puppet.motion_picker import pick_random_motion_in_group


def _motion(name: str, group: str | None) -> Motion:
    return Motion(
        name=name, duration=1.0, loop=False, group=group,
        tracks=[MotionTrack(
            param_id="ParamX",
            segments=[MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.0, 1.0))],
        )],
    )


def _doc_with(*motions: Motion) -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.motions = list(motions)
    return doc


def test_returns_none_when_document_is_none():
    """Caller may not have a rig loaded yet — must not crash."""
    assert pick_random_motion_in_group(None, "Drag") is None


def test_returns_none_when_no_motions_in_group():
    """The whole point of returning ``None`` is so the caller can
    use it as the "did anything happen" signal — a rig that lacks
    Drag motions just won't react, no error."""
    doc = _doc_with(_motion("idle_a", "Idle"))
    assert pick_random_motion_in_group(doc, "Drag") is None


def test_returns_none_when_document_has_no_motions():
    """Brand-new rig with zero authored motions — boundary case."""
    doc = PuppetDocument(size=(32, 32))
    assert pick_random_motion_in_group(doc, "Idle") is None


def test_picks_the_only_candidate_deterministically():
    """One motion in the group → always that motion, even when an
    exclusion would otherwise filter it out. Otherwise a single-
    motion group would be silently dead after the first play."""
    only = _motion("drag_a", "Drag")
    doc = _doc_with(only, _motion("idle_a", "Idle"))
    assert pick_random_motion_in_group(doc, "Drag") is only
    assert (
        pick_random_motion_in_group(doc, "Drag", exclude_name="drag_a") is only
    )


def test_exclude_name_avoids_back_to_back():
    """Two candidates and the previous pick is excluded — the picker
    must return the other one to avoid the rig replaying the same
    motion twice in a row."""
    a = _motion("drag_a", "Drag")
    b = _motion("drag_b", "Drag")
    doc = _doc_with(a, b)
    result = pick_random_motion_in_group(doc, "Drag", exclude_name="drag_a")
    assert result is b


def test_exclude_name_ignored_when_no_match():
    """Excluding a name that isn't in the group is a no-op — caller
    might pass in the name of a non-Drag motion that just played."""
    a = _motion("drag_a", "Drag")
    b = _motion("drag_b", "Drag")
    doc = _doc_with(a, b)
    result = pick_random_motion_in_group(doc, "Drag", exclude_name="random_other")
    assert result in (a, b)


def test_pick_returns_one_of_the_candidates():
    """When randomness drives the choice, the contract is "one of
    the group's motions" — anything else would mean we leaked a
    motion from another group or invented one."""
    a = _motion("drag_a", "Drag")
    b = _motion("drag_b", "Drag")
    c = _motion("drag_c", "Drag")
    doc = _doc_with(a, b, c, _motion("idle_a", "Idle"))
    for _ in range(20):
        picked = pick_random_motion_in_group(doc, "Drag")
        assert picked in (a, b, c)


def test_group_is_case_sensitive():
    """Cubism groups are case-sensitive ("Drag" != "drag"). The
    picker must mirror that or rigs with mixed conventions will
    silently misbehave."""
    doc = _doc_with(_motion("drag_a", "drag"))
    assert pick_random_motion_in_group(doc, "Drag") is None
    assert pick_random_motion_in_group(doc, "drag") is not None
