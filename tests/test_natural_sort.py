"""Tests for the Explorer-style file name order."""
from __future__ import annotations

import pytest

from Imervue.system.natural_sort import natural_key


def _order(names):
    return sorted(names, key=natural_key)


def test_numbers_compare_by_value():
    assert _order(["img10.jpg", "img2.jpg", "img1.jpg"]) == ["img1.jpg", "img2.jpg", "img10.jpg"]


def test_case_is_ignored():
    assert _order(["b.png", "A.png", "c.png"]) == ["A.png", "b.png", "c.png"]


def test_several_number_runs():
    names = ["v2_p10.png", "v2_p9.png", "v10_p1.png", "v1_p20.png"]
    assert _order(names) == ["v1_p20.png", "v2_p9.png", "v2_p10.png", "v10_p1.png"]


def test_a_prefix_sorts_before_its_longer_names():
    assert _order(["page1", "page", "page0"]) == ["page", "page0", "page1"]


@pytest.mark.parametrize("names", [["a01", "a1"], ["a1", "a01"]])
def test_equal_values_keep_one_order_whatever_came_first(names):
    assert _order(names) == _order(list(reversed(names)))


def test_names_differing_only_in_case_have_a_fixed_order():
    assert _order(["a.png", "A.png"]) == _order(["A.png", "a.png"])


def test_full_width_digits_count_as_numbers():
    assert _order(["第１０話.png", "第２話.png"]) == ["第２話.png", "第１０話.png"]


def test_numbers_and_letters_mix_without_type_errors():
    assert _order(["2", "a", "10", "b1", ""]) == ["", "2", "10", "a", "b1"]


def test_a_very_long_digit_run_is_fine():
    long_name = "x" + "9" * 250
    assert _order([long_name, "x1"]) == ["x1", long_name]
