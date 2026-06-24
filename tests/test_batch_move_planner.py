"""Tests for batch move planning."""
from __future__ import annotations

from pathlib import Path

import pytest

from Imervue.image.batch_move_planner import (
    ACTION_MOVE,
    ACTION_RENAME,
    ACTION_REPLACE,
    ACTION_SKIP,
    MovePlan,
    plan_batch_move,
    resolve_name_collision,
)


# ---------------------------------------------------------------------------
# resolve_name_collision
# ---------------------------------------------------------------------------


def test_free_name_unchanged():
    assert resolve_name_collision("photo.jpg", set()) == "photo.jpg"


def test_collision_numbers_and_keeps_extension():
    assert resolve_name_collision("photo.jpg", {"photo.jpg"}) == "photo_1.jpg"


def test_collision_skips_taken_numbers():
    existing = {"photo.jpg", "photo_1.jpg", "photo_2.jpg"}
    assert resolve_name_collision("photo.jpg", existing) == "photo_3.jpg"


def test_collision_no_extension():
    assert resolve_name_collision("README", {"README"}) == "README_1"


def test_collision_dotfile_keeps_leading_dot():
    # os.path.splitext treats a leading-dot name as having no extension.
    assert resolve_name_collision(".gitignore", {".gitignore"}) == ".gitignore_1"


# ---------------------------------------------------------------------------
# plan_batch_move
# ---------------------------------------------------------------------------


def _names(plans):
    return [None if p.destination is None else Path(p.destination).name for p in plans]


def test_no_collisions_all_move():
    plans = plan_batch_move(["/a/x.png", "/b/y.png"], "/out", set())
    assert [p.action for p in plans] == [ACTION_MOVE, ACTION_MOVE]
    assert _names(plans) == ["x.png", "y.png"]


def test_collision_with_existing_number_strategy():
    plans = plan_batch_move(["/a/x.png"], "/out", {"x.png"})
    assert plans[0].action == ACTION_RENAME
    assert _names(plans) == ["x_1.png"]


def test_collision_among_sources_is_handled():
    # Two different sources share a basename -> second gets renamed.
    plans = plan_batch_move(["/a/x.png", "/b/x.png"], "/out", set())
    assert [p.action for p in plans] == [ACTION_MOVE, ACTION_RENAME]
    assert _names(plans) == ["x.png", "x_1.png"]


def test_skip_strategy():
    plans = plan_batch_move(["/a/x.png"], "/out", {"x.png"}, strategy="skip")
    assert plans[0].action == ACTION_SKIP
    assert plans[0].destination is None


def test_replace_strategy():
    plans = plan_batch_move(["/a/x.png"], "/out", {"x.png"}, strategy="replace")
    assert plans[0].action == ACTION_REPLACE
    assert _names(plans) == ["x.png"]


def test_unknown_strategy_raises():
    with pytest.raises(ValueError, match="strategy must be"):
        plan_batch_move(["/a/x.png"], "/out", set(), strategy="clobber")


def test_destination_is_under_dest_dir():
    plans = plan_batch_move(["/a/x.png"], "/out/sub", set())
    assert Path(plans[0].destination).parent == Path("/out/sub")


def test_move_plan_is_frozen():
    plan = MovePlan("/a/x.png", "/out/x.png", ACTION_MOVE, "no collision")
    with pytest.raises((AttributeError, TypeError)):
        plan.action = ACTION_SKIP  # type: ignore[misc]
