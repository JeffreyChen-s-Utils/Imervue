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


def test_missing_field_accumulates():
    assert parse_query("missing:location missing:keywords")["missing"] == [
        "location", "keywords"]


def test_tag_negation_collects_into_tags_exclude():
    assert parse_query("-tag:reject")["tags_exclude"] == ["reject"]
    assert parse_query("-kw:private -keyword:wip")["tags_exclude"] == [
        "private", "wip"]


def test_include_and_exclude_tags_coexist():
    rules = parse_query("tag:trip -tag:reject")
    assert rules["tags_all"] == ["trip"]
    assert rules["tags_exclude"] == ["reject"]


def test_negation_only_applies_to_tag_fields():
    # A leading dash on a non-tag field is not a tag exclusion.
    assert "tags_exclude" not in parse_query("-rating:4")


def test_bare_dash_word_is_free_text_not_exclusion():
    rules = parse_query("-sunset")
    assert "tags_exclude" not in rules
    assert rules["name_contains"] == "-sunset"


def test_empty_query_is_empty_rules():
    assert parse_query("   ") == {}


def test_bare_words_only():
    assert parse_query("cat dog")["name_contains"] == "cat dog"
