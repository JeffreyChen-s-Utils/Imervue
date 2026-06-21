"""Tests for the search-query DSL → smart_album rules parser."""
from __future__ import annotations

import time

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


def test_aspect_operators_set_bounds():
    assert parse_query("aspect:>1.5")["min_aspect"] == 1.5
    assert parse_query("aspect:<0.8")["max_aspect"] == 0.8


def test_rating_ceiling_with_less_than():
    rules = parse_query("rating:<=3")
    assert rules["max_rating"] == 3
    assert "min_rating" not in rules


def test_rating_floor_unchanged():
    assert parse_query("rating:>=4")["min_rating"] == 4
    assert parse_query("rating:2")["min_rating"] == 2


def test_age_younger_sets_date_from():
    rules = parse_query("age:<30d")
    assert "date_to" not in rules
    assert abs(rules["date_from"] - (time.time() - 30 * 86400)) < 5


def test_age_older_sets_date_to():
    rules = parse_query("age:>7d")
    assert "date_from" not in rules
    assert abs(rules["date_to"] - (time.time() - 7 * 86400)) < 5


def test_camera_and_lens_tokens():
    assert parse_query("camera:Canon")["camera"] == "Canon"
    assert parse_query("lens:50mm")["lens"] == "50mm"


def test_width_and_height_bounds():
    assert parse_query("width:>1920")["min_width"] == 1920
    assert parse_query("width:<800")["max_width"] == 800
    assert parse_query("height:1080")["min_height"] == 1080
    assert parse_query("height:<600")["max_height"] == 600


def test_size_with_units():
    assert parse_query("size:>1mb")["min_size"] == 1024 ** 2
    assert parse_query("size:<500kb")["max_size"] == 500 * 1024
    assert parse_query("size:>=2gb")["min_size"] == 2 * 1024 ** 3


def test_size_bare_number_is_bytes_floor():
    assert parse_query("size:2048")["min_size"] == 2048


def test_size_unknown_unit_ignored():
    rules = parse_query("size:>5tb")
    assert "min_size" not in rules
    assert "max_size" not in rules


def test_regex_and_glob_filename_patterns():
    assert parse_query(r"re:IMG_\d+")["name_regex"] == r"IMG_\d+"
    assert parse_query("regex:^DSC")["name_regex"] == "^DSC"
    assert parse_query("glob:*.png")["name_glob"] == "*.png"


def test_empty_query_is_empty_rules():
    assert parse_query("   ") == {}


def test_bare_words_only():
    assert parse_query("cat dog")["name_contains"] == "cat dog"
