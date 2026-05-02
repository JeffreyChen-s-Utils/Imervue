"""Tests for the cubic Bezier path data + sampler."""
from __future__ import annotations

import pytest

from Imervue.paint.bezier_path import (
    DEFAULT_SAMPLES_PER_SEGMENT,
    BezierPath,
    PathNode,
    nearest_node,
    sample_path,
)


def _square_path() -> BezierPath:
    """Square corners — straight segments with no handles."""
    return BezierPath(
        nodes=[
            PathNode(anchor=(0.0, 0.0)),
            PathNode(anchor=(10.0, 0.0)),
            PathNode(anchor=(10.0, 10.0)),
            PathNode(anchor=(0.0, 10.0)),
        ],
        closed=True,
    )


# ---------------------------------------------------------------------------
# PathNode round-trip
# ---------------------------------------------------------------------------


def test_node_round_trip_with_handles():
    original = PathNode(
        anchor=(1.0, 2.0),
        handle_in=(0.0, 1.5),
        handle_out=(2.0, 2.5),
    )
    rebuilt = PathNode.from_dict(original.to_dict())
    assert rebuilt == original


def test_node_round_trip_no_handles():
    original = PathNode(anchor=(3.0, 4.0))
    rebuilt = PathNode.from_dict(original.to_dict())
    assert rebuilt == original
    assert rebuilt.handle_in is None
    assert rebuilt.handle_out is None


def test_node_from_dict_recovers_corrupt_anchor():
    rebuilt = PathNode.from_dict({"anchor": "garbage"})
    assert rebuilt.anchor == (0.0, 0.0)


def test_node_from_dict_drops_malformed_handle():
    rebuilt = PathNode.from_dict({"anchor": [1, 2], "handle_in": [1, 2, 3]})
    assert rebuilt.handle_in is None


def test_node_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        PathNode.from_dict("not a dict")  # NOSONAR — intentional negative-path test


# ---------------------------------------------------------------------------
# BezierPath operations
# ---------------------------------------------------------------------------


def test_path_starts_empty():
    path = BezierPath()
    assert path.nodes == []
    assert path.closed is False


def test_append_grows_node_list():
    path = BezierPath()
    path.append(PathNode(anchor=(1.0, 1.0)))
    assert len(path.nodes) == 1


def test_insert_at_position():
    path = BezierPath(nodes=[
        PathNode(anchor=(0.0, 0.0)), PathNode(anchor=(2.0, 2.0)),
    ])
    path.insert(1, PathNode(anchor=(1.0, 1.0)))
    assert path.nodes[1].anchor == (1.0, 1.0)


def test_insert_out_of_range_raises():
    path = BezierPath()
    with pytest.raises(IndexError):
        path.insert(99, PathNode(anchor=(0.0, 0.0)))


def test_remove_drops_node():
    path = _square_path()
    assert path.remove(2) is True
    assert len(path.nodes) == 3


def test_remove_returns_false_for_out_of_range():
    path = BezierPath()
    assert path.remove(5) is False


def test_replace_swaps_node():
    path = _square_path()
    new_node = PathNode(anchor=(99.0, 99.0))
    assert path.replace(0, new_node) is True
    assert path.nodes[0].anchor == (99.0, 99.0)


def test_replace_returns_false_for_out_of_range():
    path = BezierPath()
    assert path.replace(0, PathNode(anchor=(0.0, 0.0))) is False


# ---------------------------------------------------------------------------
# Path round-trip
# ---------------------------------------------------------------------------


def test_path_to_dict_preserves_closed_flag():
    path = _square_path()
    raw = path.to_dict()
    assert raw["closed"] is True
    assert len(raw["nodes"]) == 4


def test_path_round_trip_via_dict():
    original = _square_path()
    rebuilt = BezierPath.from_dict(original.to_dict())
    assert rebuilt.closed == original.closed
    assert [n.anchor for n in rebuilt.nodes] == [
        n.anchor for n in original.nodes
    ]


def test_path_from_dict_drops_malformed_nodes():
    raw = {
        "closed": True,
        "nodes": [
            {"anchor": [1, 2]},
            "garbage",
            {"anchor": [3, 4]},
        ],
    }
    rebuilt = BezierPath.from_dict(raw)
    assert len(rebuilt.nodes) == 2


def test_path_from_dict_handles_non_dict_input():
    rebuilt = BezierPath.from_dict("not a dict")  # NOSONAR — intentional negative-path test
    assert rebuilt.nodes == []


# ---------------------------------------------------------------------------
# sample_path — line segments (no handles)
# ---------------------------------------------------------------------------


def test_sample_empty_path_returns_empty():
    assert sample_path(BezierPath()) == []


def test_sample_single_node_returns_empty():
    path = BezierPath(nodes=[PathNode(anchor=(1.0, 1.0))])
    assert sample_path(path) == []


def test_sample_straight_segment_starts_at_first_anchor():
    path = BezierPath(nodes=[
        PathNode(anchor=(0.0, 0.0)),
        PathNode(anchor=(10.0, 0.0)),
    ])
    samples = sample_path(path, samples_per_segment=10)
    assert samples[0] == (0.0, 0.0)


def test_sample_straight_segment_ends_at_last_anchor():
    path = BezierPath(nodes=[
        PathNode(anchor=(0.0, 0.0)),
        PathNode(anchor=(10.0, 0.0)),
    ])
    samples = sample_path(path, samples_per_segment=10)
    assert samples[-1] == pytest.approx((10.0, 0.0))


def test_sample_straight_segment_is_linear():
    """No handles ⇒ the cubic collapses into a straight line; halfway
    samples land at the midpoint of the segment."""
    path = BezierPath(nodes=[
        PathNode(anchor=(0.0, 0.0)),
        PathNode(anchor=(10.0, 0.0)),
    ])
    samples = sample_path(path, samples_per_segment=10)
    middle = samples[len(samples) // 2]
    assert middle[0] == pytest.approx(5.0, abs=0.5)
    assert middle[1] == pytest.approx(0.0)


def test_sample_two_segments_share_join_sample():
    """Consecutive segments must share their boundary sample —
    otherwise the rasteriser's brush stamps a duplicate dab there."""
    path = BezierPath(nodes=[
        PathNode(anchor=(0.0, 0.0)),
        PathNode(anchor=(10.0, 0.0)),
        PathNode(anchor=(20.0, 0.0)),
    ])
    samples = sample_path(path, samples_per_segment=4)
    # 4 samples in segment one + 4 more in segment two = 9 total
    # (the join sample at x=10 isn't repeated).
    assert len(samples) == 9


def test_sample_closed_path_loops_back_to_first_node():
    """A closed path appends the wrap-around segment."""
    path = _square_path()
    samples = sample_path(path, samples_per_segment=4)
    # 4 nodes × 4 samples + extra join samples; the LAST sample
    # must coincide with the first node (the closing-segment end).
    assert samples[-1] == pytest.approx(samples[0])


# ---------------------------------------------------------------------------
# sample_path — curves with handles
# ---------------------------------------------------------------------------


def test_curve_handle_pulls_path_off_the_chord():
    """A non-collinear handle bends the curve away from the straight
    chord between the two anchors. Halfway sample should NOT be at
    the chord midpoint."""
    path = BezierPath(nodes=[
        PathNode(anchor=(0.0, 0.0), handle_out=(0.0, 10.0)),
        PathNode(anchor=(10.0, 0.0), handle_in=(10.0, 10.0)),
    ])
    samples = sample_path(path, samples_per_segment=20)
    middle = samples[len(samples) // 2]
    # Midpoint of straight chord is (5, 0); the curve's middle is
    # pulled upward by the handles.
    assert middle[1] > 1.0


# ---------------------------------------------------------------------------
# sample_path — argument validation
# ---------------------------------------------------------------------------


def test_sample_rejects_too_few_samples():
    path = _square_path()
    with pytest.raises(ValueError, match="samples_per_segment"):
        sample_path(path, samples_per_segment=1)


def test_sample_rejects_excessive_samples():
    path = _square_path()
    with pytest.raises(ValueError, match="samples_per_segment"):
        sample_path(path, samples_per_segment=10_000)


def test_default_samples_per_segment_is_reasonable():
    """A two-anchor path sampled at the documented default should
    give enough resolution for visible smoothness — at least the
    documented constant's worth of points."""
    path = BezierPath(nodes=[
        PathNode(anchor=(0.0, 0.0)),
        PathNode(anchor=(10.0, 0.0)),
    ])
    samples = sample_path(path)
    assert len(samples) >= DEFAULT_SAMPLES_PER_SEGMENT


# ---------------------------------------------------------------------------
# nearest_node
# ---------------------------------------------------------------------------


def test_nearest_node_picks_closest_anchor():
    path = _square_path()
    assert nearest_node(path, (10.5, 10.5)) == 2


def test_nearest_node_returns_none_outside_radius():
    path = _square_path()
    assert nearest_node(path, (1000.0, 1000.0)) is None


def test_nearest_node_respects_max_distance():
    path = _square_path()
    # Point near (10, 10) but max_distance is too small.
    assert nearest_node(path, (10.5, 10.5), max_distance=0.1) is None


def test_nearest_node_empty_path_returns_none():
    assert nearest_node(BezierPath(), (0.0, 0.0)) is None
