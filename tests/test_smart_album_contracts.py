"""Contract tests pinning ``Imervue.library.smart_album`` behaviour.

They cover what the feature tests in ``test_library_smart_album.py`` leave
open: the exact JSON written and read back, the decode fallbacks, the order in
which the rule filters run (the expensive ones only see what the cheap ones
kept), and the edge values of each rule.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from Imervue.library import image_index, smart_album
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


def _file(path: Path, size: int = 1) -> str:
    path.write_bytes(b"\x00" * size)
    return str(path)


@pytest.fixture
def saved_json(monkeypatch):
    """Capture every ``(name, rules_json)`` handed to the catalog."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        image_index, "save_smart_album", lambda name, raw: calls.append((name, raw)),
    )
    return calls


class TestEncode:
    def test_save_keeps_non_ascii_literal(self, saved_json):
        smart_album.save("貓", {"name_contains": "貓", "min_rating": 3})
        assert saved_json == [("貓", '{"name_contains": "貓", "min_rating": 3}')]

    def test_save_rejects_empty_name_before_writing(self, saved_json):
        with pytest.raises(ValueError, match="album name required"):
            smart_album.save("", {"exts": ["png"]})
        assert saved_json == []

    def test_touch_re_encodes_with_ascii_escapes(self, monkeypatch, saved_json):
        monkeypatch.setattr(image_index, "get_smart_album", lambda name: {
            "name": name, "rules_json": '{"name_contains": "貓"}', "updated_at": 1.0,
        })
        smart_album.touch("a")
        assert saved_json == [("a", '{"name_contains": "\\u8c93"}')]

    def test_touch_of_a_missing_album_writes_nothing(self, saved_json):
        smart_album.touch("nope")
        assert saved_json == []


class TestDecode:
    @pytest.mark.parametrize("raw", ["not json", None, "{bad"])
    def test_get_falls_back_to_empty_rules(self, monkeypatch, raw):
        monkeypatch.setattr(image_index, "get_smart_album", lambda name: {
            "name": name, "rules_json": raw, "updated_at": None,
        })
        assert smart_album.get("x") == {"name": "x", "rules": {}, "updated_at": None}

    def test_get_of_a_missing_album_is_none(self):
        assert smart_album.get("missing") is None

    def test_list_all_decodes_and_defaults_timestamp(self, monkeypatch):
        monkeypatch.setattr(image_index, "list_smart_albums", lambda: [
            {"name": "a", "rules_json": '{"exts": ["png"]}', "updated_at": 5.0},
            {"name": "b", "rules_json": "oops", "updated_at": None},
            {"name": "c", "rules_json": None, "updated_at": 0},
        ])
        assert smart_album.list_all() == [
            {"name": "a", "rules": {"exts": ["png"]}, "updated_at": 5.0},
            {"name": "b", "rules": {}, "updated_at": 0.0},
            {"name": "c", "rules": {}, "updated_at": 0.0},
        ]


class TestRoundTrip:
    RULES = {
        "exts": ["jpg", "png"], "min_width": 100, "max_aspect": 1.5,
        "color_labels": ["red"], "min_rating": 2, "favorites_only": True,
        "cull": "pick", "tags_any": ["家/貓"], "name_regex": r"^IMG_\d+",
        "camera": "Canon", "date_from": 1.5, "place": "Paris, France",
    }

    def test_save_then_get_returns_equal_rules(self):
        smart_album.save("all", self.RULES)
        got = smart_album.get("all")
        assert got["name"] == "all"
        assert got["rules"] == self.RULES
        assert isinstance(got["updated_at"], float)

    def test_list_all_and_touch_preserve_rules(self):
        smart_album.save("all", self.RULES)
        smart_album.touch("all")
        rows = smart_album.list_all()
        assert [(r["name"], r["rules"]) for r in rows] == [("all", self.RULES)]


class TestEvaluationOrder:
    def test_expensive_filters_see_only_what_cheaper_ones_kept(
        self, tmp_path, monkeypatch,
    ):
        from Imervue.image import dimensions, exif_merge, gps, reverse_geocode
        from Imervue.library import metadata_audit

        small = _file(tmp_path / "small.jpg", 1)
        paths = [_file(tmp_path / f"{n}.jpg", 50) for n in "abcde"]
        a, b, c, d, e = paths
        seen: dict[str, list[str]] = {}

        def _dims(p):
            seen.setdefault("dims", []).append(p)
            return None if p == a else (10, 10)

        def _gps(p):
            seen.setdefault("gps", []).append(p)
            return None if p == b else (1.0, 2.0)

        def _exif(p):
            seen.setdefault("exif", []).append(str(p))
            return {} if str(p) == c else {"Make": "Canon"}

        def _missing(ps, fields):
            seen["missing"] = list(ps)
            return [d]

        monkeypatch.setattr(dimensions, "image_dimensions", _dims)
        monkeypatch.setattr(gps, "extract_gps", _gps)
        monkeypatch.setattr(reverse_geocode, "reverse_geocode", lambda la, lo: "Paris, France")
        monkeypatch.setattr(exif_merge, "get_exif_data", _exif)
        monkeypatch.setattr(metadata_audit, "paths_missing", _missing)

        rules = {
            "min_size": 10, "min_width": 5, "place": "Paris",
            "camera": "canon", "missing": ["rating"],
        }
        result = smart_album.apply_to_paths([small, *paths, str(tmp_path / "x.png")], rules)
        assert seen["dims"] == paths  # size dropped small; ext not filtered
        assert seen["gps"] == [b, c, d, e]
        assert seen["exif"] == [c, d, e]
        assert seen["missing"] == [d, e]
        assert result == [d]

    def test_catalog_calls_go_through_the_image_index_facade(self, monkeypatch):
        calls: list[tuple] = []

        def _cull(ps, state):
            calls.append(("cull", list(ps), state))
            return [p for p in ps if p != "/c"]

        def _tagged(tag):
            calls.append(("tag", tag))
            return {"keep": ["/a", "/b"], "both": ["/a"], "bad": ["/b"]}[tag]

        monkeypatch.setattr(image_index, "filter_by_cull", _cull)
        monkeypatch.setattr(image_index, "images_with_tag", _tagged)
        rules = {"cull": "pick", "tags_any": ["keep"], "tags_all": ["both"],
                 "tags_exclude": ["bad"]}
        assert smart_album.apply_to_paths(["/a", "/b", "/c"], rules) == ["/a"]
        assert calls == [
            ("cull", ["/a", "/b", "/c"], "pick"),
            ("tag", "keep"), ("tag", "both"), ("tag", "bad"),
        ]

    def test_invalid_regex_empties_the_set_for_later_filters(self, monkeypatch):
        from Imervue.library import metadata_audit
        seen = []
        monkeypatch.setattr(metadata_audit, "paths_missing",
                            lambda ps, f: seen.append(list(ps)) or [])
        assert smart_album.apply_to_paths(["/a.jpg"], {
            "name_regex": "(", "missing": ["rating"]}) == []
        assert seen == [[]]


class TestRuleEdges:
    def test_empty_rules_return_a_list_copy(self):
        source = ["/a.jpg", "/b.png"]
        out = smart_album.apply_to_paths(iter(source), {})
        assert out == source
        assert out is not source

    def test_exts_ignore_dots_and_case(self):
        out = smart_album.apply_to_paths(["/a.JPG", "/b.png", "/c"], {"exts": [".jpg"]})
        assert out == ["/a.JPG"]

    def test_name_contains_then_glob(self):
        out = smart_album.apply_to_paths(
            ["/Trip_01.JPG", "/trip_02.png", "/home.jpg"],
            {"name_contains": "TRIP", "name_glob": "*.JPG"},
        )
        assert out == ["/Trip_01.JPG"]

    def test_zero_min_rating_is_ignored_but_zero_max_rating_applies(self):
        user_setting_dict["image_ratings"] = {"/a": 3}
        try:
            assert smart_album.apply_to_paths(["/a", "/b"], {"min_rating": 0}) == ["/a", "/b"]
            assert smart_album.apply_to_paths(["/a", "/b"], {"max_rating": 0}) == ["/b"]
        finally:
            user_setting_dict["image_ratings"] = {}

    def test_color_labels_union(self, monkeypatch):
        from Imervue.user_settings import color_labels
        flagged = {"red": ["/a"], "blue": ["/c"]}
        monkeypatch.setattr(color_labels, "filter_by_color",
                            lambda ps, c: [p for p in ps if p in flagged[c]])
        out = smart_album.apply_to_paths(["/a", "/b", "/c"], {"color_labels": ["red", "blue"]})
        assert out == ["/a", "/c"]

    def test_favorites_of_unexpected_type_match_nothing(self):
        user_setting_dict["image_favorites"] = "/a"
        try:
            assert smart_album.apply_to_paths(["/a"], {"favorites_only": True}) == []
        finally:
            user_setting_dict["image_favorites"] = []

    def test_date_bounds_and_missing_files(self, tmp_path):
        old = _file(tmp_path / "old.jpg")
        new = _file(tmp_path / "new.jpg")
        os.utime(old, (1000, 1000))
        os.utime(new, (5000, 5000))
        gone = str(tmp_path / "gone.jpg")
        rules = {"date_from": 2000}
        assert smart_album.apply_to_paths([old, new, gone], rules) == [new]
        assert smart_album.apply_to_paths([old, new, gone], {"date_to": 2000}) == [old]

    def test_size_rule_drops_missing_files(self, tmp_path):
        kept = _file(tmp_path / "a.jpg", 20)
        out = smart_album.apply_to_paths([kept, str(tmp_path / "gone.jpg")], {"max_size": 100})
        assert out == [kept]

    def test_zero_height_fails_only_an_aspect_rule(self, monkeypatch):
        from Imervue.image import dimensions
        monkeypatch.setattr(dimensions, "image_dimensions", lambda p: (10, 0))
        assert smart_album.apply_to_paths(["/a"], {"min_width": 5}) == ["/a"]
        assert smart_album.apply_to_paths(["/a"], {"min_aspect": 0.5}) == []

    @pytest.mark.parametrize(("dims", "rules", "kept"), [
        ((100, 50), {"max_width": 99}, False),
        ((100, 50), {"max_width": 100}, True),
        ((100, 50), {"min_height": 51}, False),
        ((100, 50), {"max_height": 50}, True),
        ((100, 50), {"min_aspect": 2.0, "max_aspect": 2.0}, True),
        ((100, 50), {"max_aspect": 1.99}, False),
    ])
    def test_dimension_boundaries(self, monkeypatch, dims, rules, kept):
        from Imervue.image import dimensions
        monkeypatch.setattr(dimensions, "image_dimensions", lambda p: dims)
        assert smart_album.apply_to_paths(["/a"], rules) == (["/a"] if kept else [])

    def test_lens_rule_alone(self, monkeypatch):
        from Imervue.image import exif_merge
        lenses = {"a": {"LensModel": "EF 50mm"}, "b": {"Make": "Canon"}}
        monkeypatch.setattr(exif_merge, "get_exif_data", lambda p: lenses[Path(p).name])
        assert smart_album.apply_to_paths(["/a", "/b"], {"lens": "50MM"}) == ["/a"]


class TestLocation:
    def test_auto_location_albums_sorted_and_untagged_dropped(self, monkeypatch):
        from Imervue.image import reverse_geocode
        names = {1.0: "Rome, Italy", 2.0: None, 3.0: "Paris, France"}
        monkeypatch.setattr(reverse_geocode, "reverse_geocode", lambda la, lo: names[la])
        out = smart_album.auto_location_albums(
            [("/a", 1.0, 0.0), ("/b", 2.0, 0.0), ("/c", 3.0, 0.0), ("/d", 1.0, 0.0)],
        )
        assert out == [
            ("Paris, France", {"place": "Paris, France"}),
            ("Rome, Italy", {"place": "Rome, Italy"}),
        ]

    def test_generate_location_albums_saves_each_city(self, monkeypatch, saved_json):
        from Imervue.image import gps, reverse_geocode
        monkeypatch.setattr(gps, "collect_gps", lambda ps: [(p, 1.0, 0.0) for p in ps])
        monkeypatch.setattr(reverse_geocode, "reverse_geocode", lambda la, lo: "Oslo, Norway")
        assert smart_album.generate_location_albums(iter(["/a", "/b"])) == 1
        assert saved_json == [("Oslo, Norway", '{"place": "Oslo, Norway"}')]

    @pytest.mark.parametrize(("found", "wanted", "ok"), [
        ("Paris, France", " PARIS , france ", True),
        ("Paris, France", "France, Paris", False),
        ("Paris, France", ",", False),
        ("", "Paris", False),
    ])
    def test_place_matches_edges(self, found, wanted, ok):
        assert smart_album.place_matches(found, wanted) is ok
