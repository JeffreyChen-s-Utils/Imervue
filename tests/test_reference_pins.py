"""Tests for the reference-pins persistence layer.

The Qt panel is exercised separately via the qapp fixture; this file
covers the user-setting-backed list operations directly.
"""
from __future__ import annotations

import pytest

from Imervue.library import reference_pins
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_pins():
    """Each test starts with an empty pin list."""
    user_setting_dict.pop("reference_pins", None)
    yield
    user_setting_dict.pop("reference_pins", None)


# ---------------------------------------------------------------------------
# Empty / default state
# ---------------------------------------------------------------------------


def test_empty_state_returns_empty_list():
    assert reference_pins.get_all() == []
    assert reference_pins.count() == 0
    assert reference_pins.contains("/whatever") is False


def test_get_all_returns_a_copy():
    reference_pins.add("/a")
    snapshot = reference_pins.get_all()
    snapshot.append("/sneaky")
    assert reference_pins.get_all() == ["/a"]


# ---------------------------------------------------------------------------
# add / add_many
# ---------------------------------------------------------------------------


def test_add_returns_true_on_new_path():
    assert reference_pins.add("/foo.png") is True
    assert reference_pins.contains("/foo.png")
    assert reference_pins.count() == 1


def test_add_returns_false_on_duplicate():
    reference_pins.add("/foo.png")
    assert reference_pins.add("/foo.png") is False
    assert reference_pins.count() == 1


def test_add_rejects_empty_string():
    assert reference_pins.add("") is False
    assert reference_pins.count() == 0


def test_add_many_only_counts_new_entries():
    reference_pins.add("/a")
    added = reference_pins.add_many(["/a", "/b", "/c", "", "/b"])
    assert added == 2  # /b and /c are new; /a was already there; "" rejected
    assert reference_pins.get_all() == ["/a", "/b", "/c"]


# ---------------------------------------------------------------------------
# remove / clear
# ---------------------------------------------------------------------------


def test_remove_deletes_existing_entry():
    reference_pins.add("/a")
    reference_pins.add("/b")
    assert reference_pins.remove("/a") is True
    assert reference_pins.get_all() == ["/b"]


def test_remove_nonexistent_is_false():
    assert reference_pins.remove("/never-added") is False


def test_clear_empties_the_list():
    reference_pins.add_many(["/a", "/b", "/c"])
    reference_pins.clear()
    assert reference_pins.count() == 0


def test_clear_on_empty_is_safe():
    reference_pins.clear()  # no exception
    assert reference_pins.count() == 0


# ---------------------------------------------------------------------------
# move / reorder
# ---------------------------------------------------------------------------


def test_move_up_swaps_with_predecessor():
    reference_pins.add_many(["/a", "/b", "/c"])
    assert reference_pins.move("/b", up=True) is True
    assert reference_pins.get_all() == ["/b", "/a", "/c"]


def test_move_down_swaps_with_successor():
    reference_pins.add_many(["/a", "/b", "/c"])
    assert reference_pins.move("/b", up=False) is True
    assert reference_pins.get_all() == ["/a", "/c", "/b"]


def test_move_up_at_top_is_noop():
    reference_pins.add_many(["/a", "/b"])
    assert reference_pins.move("/a", up=True) is False
    assert reference_pins.get_all() == ["/a", "/b"]


def test_move_down_at_bottom_is_noop():
    reference_pins.add_many(["/a", "/b"])
    assert reference_pins.move("/b", up=False) is False
    assert reference_pins.get_all() == ["/a", "/b"]


def test_move_unknown_path_is_false():
    reference_pins.add("/a")
    assert reference_pins.move("/nope", up=True) is False


# ---------------------------------------------------------------------------
# Stored format under user_setting_dict
# ---------------------------------------------------------------------------


def test_pins_stored_under_reference_pins_key():
    reference_pins.add("/a")
    assert user_setting_dict.get("reference_pins") == ["/a"]


def test_corrupt_value_is_replaced_by_fresh_list():
    user_setting_dict["reference_pins"] = "not-a-list"
    reference_pins.add("/recovered")
    assert user_setting_dict["reference_pins"] == ["/recovered"]


# ---------------------------------------------------------------------------
# Order preservation
# ---------------------------------------------------------------------------


def test_insertion_order_preserved():
    paths = [f"/{i}.png" for i in range(8)]
    reference_pins.add_many(paths)
    assert reference_pins.get_all() == paths
