"""
Unit tests for ``Imervue.library.smart_album``.
"""
from __future__ import annotations

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

    def test_combined_rules(self, tmp_path):
        a = _touch(tmp_path / "cat.png")
        b = _touch(tmp_path / "dog.jpg")
        c = _touch(tmp_path / "cat.jpg")
        image_index.set_cull_state(a, "pick")
        image_index.set_cull_state(c, "pick")
        rules = {"exts": ["png"], "cull": "pick", "name_contains": "cat"}
        assert smart_album.apply_to_paths([a, b, c], rules) == [a]
