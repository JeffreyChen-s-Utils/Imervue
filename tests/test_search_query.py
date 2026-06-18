"""Tests for the search-query DSL → smart_album rules parser."""
from __future__ import annotations

from Imervue.library.search_query import parse_query


def test_keywords_and_tags_collect_into_tags_all():
    assert parse_query("kw:beach tag:trip keyword:summer")["tags_all"] == [
        "beach", "trip", "summer"]


def test_rating_supports_operator_and_bare_number():
    assert parse_query("rating:>=4")["min_rating"] == 4
    assert parse_query("rating:3")["min_rating"] == 3


def test_color_and_ext():
    rules = parse_query("color:red ext:png")
    assert rules["color_labels"] == ["red"]
    assert rules["exts"] == ["png"]


def test_type_video_expands_to_video_exts():
    assert "mp4" in parse_query("type:video")["exts"]


def test_place_cull_and_favorites():
    rules = parse_query("place:Paris cull:pick fav:true")
    assert rules["place"] == "Paris"
    assert rules["cull"] == "pick"
    assert rules["favorites_only"] is True


def test_favorites_false():
    assert parse_query("fav:no")["favorites_only"] is False


def test_free_words_become_name_contains():
    assert parse_query("name:sunset over lake")["name_contains"] == "sunset over lake"


def test_empty_query_is_empty_rules():
    assert parse_query("   ") == {}


def test_bare_words_only():
    assert parse_query("cat dog")["name_contains"] == "cat dog"
