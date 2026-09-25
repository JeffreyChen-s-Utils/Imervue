"""Tests for picking file names that are not taken yet."""
from __future__ import annotations

import os

import pytest

from Imervue.system.free_names import free_names


def _names(paths):
    return [p.name for p in paths]


def test_an_empty_folder_gets_the_plain_names(tmp_path):
    assert free_names(tmp_path, ["a", "b"], ".png") == [tmp_path / "a.png", tmp_path / "b.png"]


def test_a_taken_name_moves_to_the_next_number(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "a_1.png").write_bytes(b"x")
    assert _names(free_names(tmp_path, ["a"], ".png")) == ["a_2.png"]


def test_the_extension_is_part_of_the_name(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    assert _names(free_names(tmp_path, ["a"], ".png")) == ["a.png"]


def test_a_group_shares_one_number(tmp_path):
    """One taken member moves the whole group, so the set stays recognisable."""
    (tmp_path / "doc_page001.png").write_bytes(b"x")
    assert _names(free_names(tmp_path, ["doc_page000", "doc_page001"], ".png")) == [
        "doc_page000_1.png", "doc_page001_1.png"]


def test_no_stems_returns_nothing(tmp_path):
    assert free_names(tmp_path, [], ".png") == []


def test_a_missing_folder_counts_as_empty(tmp_path):
    folder = tmp_path / "gone"
    assert free_names(folder, ["a"], ".png") == [folder / "a.png"]


@pytest.mark.skipif(os.path.normcase("A") != os.path.normcase("a"),
                    reason="case-insensitive file system only")
def test_names_compare_as_the_file_system_does(tmp_path):
    (tmp_path / "A.PNG").write_bytes(b"x")
    assert _names(free_names(tmp_path, ["a"], ".png")) == ["a_1.png"]


def test_a_str_folder_is_accepted(tmp_path):
    assert free_names(str(tmp_path), ["a"], ".png") == [tmp_path / "a.png"]
