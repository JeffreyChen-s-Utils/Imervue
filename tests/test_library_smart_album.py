"""
Unit tests for ``Imervue.library.smart_album``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from Imervue.library import image_index, smart_album
from Imervue.user_settings.user_setting_dict import user_setting_dict

_rng = np.random.default_rng(seed=0x5A1B)


def _make_image(path: Path, w: int, h: int) -> str:
    arr = _rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
    Image.fromarray(arr).save(str(path))
    return str(path)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


def _touch(path: Path) -> str:
    path.write_bytes(b"\x00")
    return str(path)


class TestPersistence:
    def test_save_get_delete(self):
        smart_album.save("only-png", {"exts": ["png"]})
        got = smart_album.get("only-png")
        assert got is not None
        assert got["rules"]["exts"] == ["png"]
        assert smart_album.delete("only-png")
        assert smart_album.get("only-png") is None

    def test_list_all_sorted(self):
        smart_album.save("b", {})
        smart_album.save("a", {})
        names = [row["name"] for row in smart_album.list_all()]
        assert names == ["a", "b"]

    def test_save_rejects_empty_name(self):
        with pytest.raises(ValueError):
            smart_album.save("", {})


class TestWriteBatch:
    def test_commits_on_success(self, tmp_path):
        a = str(tmp_path / "a.png")
        b = str(tmp_path / "b.png")
        with image_index.write_batch():
            image_index.upsert_image(a, size=10)
            image_index.upsert_image(b, size=20)
        assert image_index.get_image(a) is not None
        assert image_index.get_image(b) is not None

    def test_rolls_back_on_exception(self, tmp_path):
        c = str(tmp_path / "c.png")
        with pytest.raises(RuntimeError), image_index.write_batch():
            image_index.upsert_image(c, size=10)
            raise RuntimeError("boom")
        # The whole batch is discarded, not just the row after the failure.
        assert image_index.get_image(c) is None


class TestApplyToPaths:
    def test_filter_by_ext(self, tmp_path):
        a = _touch(tmp_path / "one.png")
        b = _touch(tmp_path / "two.jpg")
        assert smart_album.apply_to_paths([a, b], {"exts": ["png"]}) == [a]

    def test_name_contains_case_insensitive(self, tmp_path):
        a = _touch(tmp_path / "CatPhoto.png")
        b = _touch(tmp_path / "dog.png")
        assert smart_album.apply_to_paths([a, b], {"name_contains": "cat"}) == [a]

    def test_favorites_only(self, tmp_path):
        a = _touch(tmp_path / "a.png")
        b = _touch(tmp_path / "b.png")
        user_setting_dict["image_favorites"] = [a]
        try:
            result = smart_album.apply_to_paths([a, b], {"favorites_only": True})
        finally:
            user_setting_dict["image_favorites"] = []
        assert result == [a]

    def test_cull_filter(self, tmp_path):
        a = _touch(tmp_path / "a.png")
        b = _touch(tmp_path / "b.png")
        image_index.set_cull_state(a, "pick")
        assert smart_album.apply_to_paths([a, b], {"cull": "pick"}) == [a]

    def test_tags_all_requires_every_tag(self, tmp_path):
        a = _touch(tmp_path / "a.png")
        b = _touch(tmp_path / "b.png")
        image_index.add_image_tag(a, "animal/cat")
        image_index.add_image_tag(a, "indoor")
        image_index.add_image_tag(b, "animal/cat")
        result = smart_album.apply_to_paths(
            [a, b], {"tags_all": ["animal/cat", "indoor"]}
        )
        assert result == [a]

    def test_min_size_filter(self, tmp_path):
        small = tmp_path / "small.bin"
        small.write_bytes(b"\x00" * 100)
        big = tmp_path / "big.bin"
        big.write_bytes(b"\x00" * 5000)
        result = smart_album.apply_to_paths(
            [str(small), str(big)], {"min_size": 1000}
        )
        assert result == [str(big)]

    def test_max_size_filter(self, tmp_path):
        small = tmp_path / "small.bin"
        small.write_bytes(b"\x00" * 100)
        big = tmp_path / "big.bin"
        big.write_bytes(b"\x00" * 5000)
        result = smart_album.apply_to_paths(
            [str(small), str(big)], {"max_size": 1000}
        )
        assert result == [str(small)]

    def test_min_width_and_height_filter(self, tmp_path):
        wide = _make_image(tmp_path / "wide.png", 200, 50)
        tall = _make_image(tmp_path / "tall.png", 50, 200)
        big = _make_image(tmp_path / "big.png", 200, 200)
        result = smart_album.apply_to_paths(
            [wide, tall, big], {"min_width": 100, "min_height": 100}
        )
        assert result == [big]

    def test_dimension_filter_skips_unreadable(self, tmp_path):
        not_image = tmp_path / "broken.png"
        not_image.write_bytes(b"not really a png")
        result = smart_album.apply_to_paths([str(not_image)], {"min_width": 1})
        assert result == []

    def test_no_size_rules_is_passthrough(self, tmp_path):
        a = _touch(tmp_path / "a.png")
        assert smart_album.apply_to_paths([a], {}) == [a]

    def test_combined_rules(self, tmp_path):
        a = _touch(tmp_path / "cat.png")
        b = _touch(tmp_path / "dog.jpg")
        c = _touch(tmp_path / "cat.jpg")
        image_index.set_cull_state(a, "pick")
        image_index.set_cull_state(c, "pick")
        rules = {"exts": ["png"], "cull": "pick", "name_contains": "cat"}
        assert smart_album.apply_to_paths([a, b, c], rules) == [a]


class TestLocationAlbums:
    def test_auto_location_albums_groups_by_city(self):
        coords = [
            ("/a.jpg", 48.85, 2.35),    # Paris
            ("/b.jpg", 48.86, 2.34),    # Paris
            ("/c.jpg", 35.68, 139.69),  # Tokyo
        ]
        albums = dict(smart_album.auto_location_albums(coords))
        assert albums["Paris, France"] == {"place": "Paris, France"}
        assert "Tokyo, Japan" in albums

    def test_place_rule_filters_by_city(self, monkeypatch):
        from Imervue.image import gps
        coords = {"/a.jpg": (48.85, 2.35), "/b.jpg": (35.68, 139.69)}
        monkeypatch.setattr(gps, "extract_gps", lambda p: coords.get(str(p)))
        result = smart_album.apply_to_paths(
            ["/a.jpg", "/b.jpg"], {"place": "Paris, France"},
        )
        assert result == ["/a.jpg"]

    def test_generate_location_albums_persists(self, monkeypatch):
        from Imervue.image import gps
        coords = {"/a.jpg": (48.85, 2.35), "/b.jpg": (35.68, 139.69)}
        monkeypatch.setattr(gps, "extract_gps", lambda p: coords.get(str(p)))
        count = smart_album.generate_location_albums(["/a.jpg", "/b.jpg"])
        assert count == 2
        names = {row["name"] for row in smart_album.list_all()}
        assert {"Paris, France", "Tokyo, Japan"} <= names
