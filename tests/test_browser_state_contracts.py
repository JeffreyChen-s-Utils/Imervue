"""Contracts for the browser-state helpers that the older tests leave open.

They pin the filter grammar (rating operators, raw-query tokens, date
bounds), the missing-file repair helpers, rename inference, viewer-cache
migration and the metadata index's cache bookkeeping, all through the
public ``Imervue.image.browser_state`` import path.
"""
from __future__ import annotations

import os
from datetime import date

import pytest
from PIL import Image

from Imervue.image import browser_state
from Imervue.image.browser_state import (
    ImageFilterSpec,
    ImageMetadataIndex,
    auto_match_same_name,
    detect_renamed_paths,
    filter_paths,
    migrate_view_path_state,
    missing_paths,
    refilter_keeping_current,
    relocate_root,
    remove_missing,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict

PUBLIC_NAMES = (
    "ImageMeta", "ImageMetadataIndex", "ImageFilterSpec", "match_filter",
    "filter_paths", "refilter_keeping_current", "missing_paths", "remove_missing",
    "auto_match_same_name", "relocate_root", "detect_renamed_paths",
    "migrate_view_path_state", "is_missing_file_error", "is_transient_load_error",
)


def _file(path, payload=b"x"):
    path.write_bytes(payload)
    return str(path)


def _png(path, size=(4, 4)):
    Image.new("RGB", size, (10, 20, 30)).save(path)
    return str(path)


@pytest.mark.parametrize("name", PUBLIC_NAMES)
def test_every_public_name_stays_importable_from_browser_state(name):
    assert callable(getattr(browser_state, name))


# ---------------------------------------------------------------- filter grammar

@pytest.mark.parametrize(("expr", "expected"), [
    (">=3", ["b", "c"]), ("<=3", ["a", "b"]), (">3", ["c"]), ("<3", ["a"]),
    ("3", ["b"]), (">=x", ["a", "b", "c"]), ("abc", ["a", "b", "c"]),
])
def test_rating_expression_operators(tmp_path, expr, expected):
    paths = {n: _file(tmp_path / f"{n}.png") for n in "abc"}
    user_setting_dict["image_ratings"] = {paths["a"]: 1, paths["b"]: 3, paths["c"]: 5}
    got = filter_paths(list(paths.values()), ImageFilterSpec(rating=expr))
    assert got == [paths[n] for n in expected]
    raw = filter_paths(list(paths.values()), ImageFilterSpec(raw_query=f"rating:{expr}"))
    assert raw == got


def test_unparseable_stored_rating_counts_as_zero(tmp_path):
    p = _file(tmp_path / "a.png")
    user_setting_dict["image_ratings"] = {p: "bad"}
    assert filter_paths([p], ImageFilterSpec(rating="0")) == [p]
    assert filter_paths([p], ImageFilterSpec(rating=">0")) == []


def test_tag_filter_and_tag_token_use_case_insensitive_substrings(tmp_path, monkeypatch):
    import Imervue.user_settings.tags as tags_mod
    a, b = _file(tmp_path / "a.png"), _file(tmp_path / "b.png")
    tags = {a: ["Holiday", "Beach"], b: ["Work"]}
    monkeypatch.setattr(tags_mod, "get_tags_for_image", lambda path: tags.get(path, []))
    assert filter_paths([a, b], ImageFilterSpec(tag="  beach ")) == [a]
    assert filter_paths([a, b], ImageFilterSpec(raw_query="tag:wor")) == [b]


def test_raw_query_name_and_date_tokens(tmp_path):
    p = _file(tmp_path / "Sunset_Beach.png")
    year = date.fromtimestamp(os.stat(p).st_mtime).isoformat()[:4]
    assert filter_paths([p], ImageFilterSpec(raw_query="SUNSET beach")) == [p]
    assert filter_paths([p], ImageFilterSpec(raw_query="sunset night")) == []
    assert filter_paths([p], ImageFilterSpec(raw_query=f"date:{year}")) == [p]
    assert filter_paths([p], ImageFilterSpec(raw_query="date:1899")) == []


def test_date_range_is_inclusive_and_drops_unstattable_files(tmp_path):
    p = _file(tmp_path / "a.png")
    day = date.fromtimestamp(os.stat(p).st_mtime)
    gone = str(tmp_path / "gone.png")
    assert filter_paths([p], ImageFilterSpec(date_from=day, date_to=day)) == [p]
    assert filter_paths([p], ImageFilterSpec(date_from=day.replace(year=day.year + 1))) == []
    assert filter_paths([p], ImageFilterSpec(date_to=day.replace(year=day.year - 1))) == []
    assert filter_paths([p, gone], ImageFilterSpec(date_from=day)) == [p]


def test_empty_spec_returns_every_path_unchanged():
    spec = ImageFilterSpec(filename="  ", raw_query=" ")
    assert spec.is_empty()
    assert filter_paths(iter(["/nope/a", "/nope/b"]), spec) == ["/nope/a", "/nope/b"]


def test_filter_with_index_reads_through_the_stat_cache(tmp_path):
    p = _file(tmp_path / "keep.png")
    index = ImageMetadataIndex()
    assert filter_paths([p], ImageFilterSpec(filename="KEEP"), index) == [p]
    assert index.peek(p) is not None


@pytest.mark.parametrize(("filtered", "current", "expected"), [
    (["a", "d"], "c", ["a", "c", "d"]),
    (["b", "d"], "a", ["a", "b", "d"]),
    (["a", "b"], "d", ["a", "b", "d"]),
    (["a"], "a", ["a"]),
    (["a"], None, ["a"]),
    (["a"], "zz", ["a"]),
])
def test_refilter_keeping_current_inserts_in_folder_order(filtered, current, expected):
    assert refilter_keeping_current(["a", "b", "c", "d"], filtered, current) == expected


# ---------------------------------------------------------------- missing repair

def test_missing_and_remove_missing_partition_paths(tmp_path):
    here = _file(tmp_path / "here.png")
    gone = str(tmp_path / "gone.png")
    assert missing_paths([here, gone]) == [gone]
    assert remove_missing([here, gone]) == [here]


def test_auto_match_same_name_is_case_insensitive_and_needs_a_folder(tmp_path):
    found = _file(tmp_path / "Photo.PNG")
    (tmp_path / "sub").mkdir()
    assert auto_match_same_name(["/old/photo.png", "/old/other.png"], str(tmp_path)) == {
        "/old/photo.png": found,
    }
    assert auto_match_same_name(["/old/photo.png"], str(tmp_path / "nope")) == {}


def test_relocate_root_falls_back_to_the_basename(tmp_path):
    new_root = tmp_path / "new"
    (new_root / "sub").mkdir(parents=True)
    nested = _file(new_root / "sub" / "a.png")
    flat = _file(new_root / "b.png")
    old_root = str(tmp_path / "old")
    mapping = relocate_root(
        [os.path.join(old_root, "sub", "a.png"), str(tmp_path / "elsewhere" / "b.png"),
         os.path.join(old_root, "missing.png")],
        old_root, str(new_root),
    )
    assert mapping == {
        os.path.join(old_root, "sub", "a.png"): nested,
        str(tmp_path / "elsewhere" / "b.png"): flat,
    }


# ---------------------------------------------------------------- rename inference

def test_detect_renames_needs_both_sides_to_change(tmp_path):
    a = _file(tmp_path / "a.png")
    assert detect_renamed_paths([a], [a]) == {}
    assert detect_renamed_paths([a], [a, str(tmp_path / "b.png")]) == {}


def test_detect_renames_prefers_the_closest_stem(tmp_path):
    first = _file(tmp_path / "holiday_001.png", b"same")
    second = _file(tmp_path / "zzz.png", b"same")
    os.utime(second, ns=(os.stat(first).st_atime_ns, os.stat(first).st_mtime_ns))
    old_paths = [first, second]
    index = ImageMetadataIndex()
    index.prime(old_paths)
    renamed_first = str(tmp_path / "holiday_001_edit.png")
    os.replace(first, renamed_first)
    os.replace(second, str(tmp_path / "other.png"))
    mapping = detect_renamed_paths(old_paths, [renamed_first, str(tmp_path / "other.png")], index)
    assert mapping[first] == renamed_first
    assert mapping[second] == str(tmp_path / "other.png")


def test_detect_renames_skips_unstattable_new_paths(tmp_path):
    gone_old = str(tmp_path / "old.png")
    assert detect_renamed_paths([gone_old], [str(tmp_path / "new.png")]) == {}


def test_detect_renames_with_index_uses_cached_signature(tmp_path):
    index = ImageMetadataIndex()
    old = _file(tmp_path / "pic.png", b"payload")
    index.get_stat(old)
    new = str(tmp_path / "pic2.png")
    os.replace(old, new)
    assert detect_renamed_paths([old], [new], index) == {old: new}


# ---------------------------------------------------------------- viewer migration

class _View:
    def __init__(self):
        self.tile_cache = {"/a": 1, "/b": 2, "/n": 9}
        self.tile_errors = {"/a": "boom"}
        self.offline_paths = {"/a"}
        self.selected_tiles = {"/b"}
        self._view_memory = ["not", "a", "dict"]


def test_migrate_view_path_state_keeps_existing_targets():
    view = _View()
    migrate_view_path_state(view, {"/a": "/n", "/b": "/c"})
    assert view.tile_cache == {"/a": 1, "/n": 9, "/c": 2}
    assert view.tile_errors == {"/n": "boom"}
    assert view.offline_paths == {"/n"}
    assert view.selected_tiles == {"/c"}
    assert view._view_memory == ["not", "a", "dict"]


def test_migrate_view_path_state_empty_mapping_is_a_no_op():
    view = _View()
    migrate_view_path_state(view, {})
    assert view.tile_cache == {"/a": 1, "/b": 2, "/n": 9}


# ---------------------------------------------------------------- metadata index

def test_prime_respects_its_limit(tmp_path):
    paths = [_file(tmp_path / f"{i}.png") for i in range(3)]
    index = ImageMetadataIndex()
    index.prime(paths, limit=2)
    assert [index.peek(p) is not None for p in paths] == [True, True, False]
    index.prime(paths)
    assert index.peek(paths[2]) is not None


def test_get_promotes_a_stat_entry_and_drop_missing_forgets_both(tmp_path):
    p = _png(tmp_path / "a.png", size=(5, 3))
    q = _file(tmp_path / "b.png")
    index = ImageMetadataIndex()
    assert index.get_stat(p).width is None
    full = index.get(p)
    assert (full.width, full.height) == (5, 3)
    assert index.get_stat(p) is full
    assert index.peek(p) is full
    index.get_stat(q)
    os.remove(p)
    os.remove(q)
    index.drop_missing()
    assert index.peek(p) is None
    assert index.peek(q) is None


def test_get_stat_does_not_cache_a_missing_file(tmp_path):
    index = ImageMetadataIndex()
    meta = index.get_stat(str(tmp_path / "gone.png"))
    assert (meta.size, meta.mtime_ns, meta.mtime_date) == (0, 0, None)
    assert index.peek(str(tmp_path / "gone.png")) is None


def test_move_of_a_stat_only_entry_re_reads_without_dimensions(tmp_path):
    old = _png(tmp_path / "a.png")
    index = ImageMetadataIndex()
    index.get_stat(old)
    new = str(tmp_path / "b.png")
    os.replace(old, new)
    index.move(old, new)
    moved = index.peek(new)
    assert moved is not None
    assert moved.width is None
    assert moved.name == "b.png"
    assert index.peek(old) is None


def test_move_of_an_unknown_path_only_carries_nothing(tmp_path):
    index = ImageMetadataIndex()
    index.move("/x", "/y")
    assert index.peek("/y") is None


def test_sample_hash_hashes_head_and_tail_and_skips_missing(tmp_path):
    chunk = 64 * 1024
    a = _file(tmp_path / "a.bin", b"A" * chunk + b"middle" + b"Z" * chunk)
    b = _file(tmp_path / "b.bin", b"A" * chunk + b"MIDDLE" + b"Z" * chunk)
    c = _file(tmp_path / "c.bin", b"A" * chunk + b"middle" + b"Y" * chunk)
    index = ImageMetadataIndex()
    assert index.sample_hash(a) == index.sample_hash(b)
    assert index.sample_hash(a) != index.sample_hash(c)
    gone = str(tmp_path / "gone.bin")
    assert index.sample_hash(gone) == ""
    _file(tmp_path / "gone.bin", b"now")
    assert index.sample_hash(gone) != ""
