"""The Puppet motion timeline reshapes a track to an easing and simplifies keys.

``puppet/easing.py`` (named easing curves) and ``puppet/motion_compress.py``
(drop keys that sit on the line through their neighbours) were tested but
unreachable. The motion timeline dialog now has an **Ease** box with **Apply to
Track** and a **Simplify Keys** button with a tolerance in percent of each
parameter's range.
"""
from __future__ import annotations

import pytest

from Imervue.puppet.document import Motion, MotionSegment, MotionTrack
from Imervue.puppet.easing import (
    EASING_BEZIER,
    EASING_SAMPLES,
    ease_track,
    ease_value,
    eased_segments,
)
from Imervue.puppet.motion_timeline import MotionTimelineDialog


def _ramp(param: str = "ParamX", keys: int = 3, top: float = 1.0) -> MotionTrack:
    times = [i / (keys - 1) for i in range(keys)]
    points = [(t, top * t) for t in times]
    return MotionTrack(param, [MotionSegment("linear", a, b)
                               for a, b in zip(points, points[1:], strict=False)])


def test_a_bezier_easing_is_one_curve_between_the_same_keys():
    (segment,) = eased_segments("ease-in-out-cubic", (0.0, 0.0), (2.0, 10.0))
    assert segment.type == "cubic-bezier"
    assert (segment.p0, segment.p1) == ((0.0, 0.0), (2.0, 10.0))
    x1, y1, x2, y2 = EASING_BEZIER["ease-in-out-cubic"]
    assert segment.c0 == pytest.approx((2.0 * x1, 10.0 * y1))
    assert segment.c1 == pytest.approx((2.0 * x2, 10.0 * y2))


def test_linear_stays_one_straight_segment():
    (segment,) = eased_segments("linear", (0.0, 1.0), (1.0, 0.0))
    assert segment.type == "linear" and segment.c0 is None


def test_bounce_is_sampled_into_linear_pieces_through_the_curve():
    pieces = eased_segments("ease-out-bounce", (0.0, 0.0), (1.0, 4.0))
    assert len(pieces) == EASING_SAMPLES
    assert all(p.type == "linear" for p in pieces)
    assert pieces[0].p0 == (0.0, 0.0) and pieces[-1].p1 == (1.0, 4.0)
    t, v = pieces[3].p1
    assert v == pytest.approx(4.0 * ease_value("ease-out-bounce", t))


def test_an_unknown_easing_is_refused():
    with pytest.raises(ValueError, match="unknown easing"):
        eased_segments("ease-sideways", (0.0, 0.0), (1.0, 1.0))


def test_ease_track_keeps_the_keys_and_leaves_the_original_alone():
    track = _ramp(keys=4)
    eased = ease_track(track, "ease-in-quad")
    assert [s.p0 for s in eased.segments] == [s.p0 for s in track.segments]
    assert all(s.type == "cubic-bezier" for s in eased.segments)
    assert all(s.type == "linear" for s in track.segments)


@pytest.fixture
def dialog(qapp):
    motion = Motion("rec", 1.0, tracks=[_ramp("ParamX", keys=31), _ramp("ParamY", keys=11, top=30.0)])
    widget = MotionTimelineDialog(motion, None, ranges={"ParamX": (0.0, 1.0), "ParamY": (-30.0, 30.0)})
    yield widget
    widget.deleteLater()


def test_apply_easing_reshapes_the_shown_track_and_reports_it(dialog):
    edits = []
    dialog.widget().track_modified.connect(lambda: edits.append(1))
    assert dialog.apply_easing("ease-out-back") is True
    track = dialog.widget().track()
    assert track.param_id == "ParamX"
    assert len(track.segments) == 30 and all(s.type == "cubic-bezier" for s in track.segments)
    assert edits == [1]


def test_apply_easing_without_a_track_does_nothing(qapp):
    widget = MotionTimelineDialog(Motion("empty", 1.0), None)
    try:
        assert widget.apply_easing("ease-in-sine") is False
    finally:
        widget.deleteLater()


def test_simplify_drops_the_keys_on_a_straight_line(dialog):
    edits = []
    dialog.widget().track_modified.connect(lambda: edits.append(1))
    assert dialog.key_count() == 31 + 11
    assert dialog.simplify_keys(1.0) == (42, 4)
    assert [len(t.segments) for t in dialog._motion.tracks] == [1, 1]
    assert dialog._motion.tracks[1].segments[0].p1 == (1.0, 30.0)
    assert dialog._keys_label.text() == "42 → 4 keys"
    assert edits == [1]
    assert dialog.simplify_keys(1.0) == (4, 4)               # nothing left to drop
    assert edits == [1]


def test_the_tolerance_is_a_share_of_each_parameter_range(qapp):
    bumpy = [(0.0, 0.0), (0.5, 0.5), (1.0, 0.0)]
    track = MotionTrack("ParamY", [MotionSegment("linear", a, b)
                                   for a, b in zip(bumpy, bumpy[1:], strict=False)])
    widget = MotionTimelineDialog(Motion("m", 1.0, tracks=[track]), None,
                                  ranges={"ParamY": (-30.0, 30.0)})
    try:
        assert widget.simplify_keys(0.5) == (3, 3)           # 0.5 % of 60 = 0.3 < the 0.5 bump
        assert widget.simplify_keys(1.0) == (3, 2)           # 1 % of 60 = 0.6 covers it
    finally:
        widget.deleteLater()
