"""Tests for XMP sidecar read/write (Lightroom interop)."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def xmp():
    from Imervue.image import xmp_sidecar
    return xmp_sidecar


@pytest.fixture
def image_path(tmp_path: Path) -> str:
    p = tmp_path / "photo.jpg"
    p.write_bytes(b"fake-jpeg")
    return str(p)


class TestSidecarPath:
    def test_replaces_extension(self, xmp, tmp_path):
        assert xmp.sidecar_path_for(tmp_path / "foo.jpg").name == "foo.xmp"

    def test_has_sidecar_false(self, xmp, image_path):
        assert xmp.has_sidecar(image_path) is False

    def test_has_sidecar_true_after_write(self, xmp, image_path):
        xmp.save(image_path, xmp.XmpData(rating=3))
        assert xmp.has_sidecar(image_path) is True


class TestRoundTrip:
    def test_save_then_load_preserves_fields(self, xmp, image_path):
        data = xmp.XmpData(
            rating=4,
            title="Golden Hour",
            description="Sunset over the lake.",
            keywords=["landscape", "sunset"],
            color_label="red",
        )
        xmp.save(image_path, data)
        loaded = xmp.load(image_path)
        assert loaded.rating == 4
        assert loaded.title == "Golden Hour"
        assert loaded.description == "Sunset over the lake."
        assert loaded.keywords == ["landscape", "sunset"]
        assert loaded.color_label == "red"

    def test_missing_sidecar_returns_empty(self, xmp, image_path):
        loaded = xmp.load(image_path)
        assert loaded.is_empty()

    def test_empty_data_removes_existing_sidecar(self, xmp, image_path):
        xmp.save(image_path, xmp.XmpData(rating=2))
        assert xmp.has_sidecar(image_path)
        xmp.save(image_path, xmp.XmpData())
        assert xmp.has_sidecar(image_path) is False

    def test_rating_clamped_to_five(self, xmp, image_path):
        xmp.save(image_path, xmp.XmpData(rating=99))
        # 99 serialised as-is, loader clamps on parse
        loaded = xmp.load(image_path)
        assert loaded.rating == 5

    def test_rating_accepts_reject(self, xmp, image_path):
        xmp.save(image_path, xmp.XmpData(rating=-1))
        loaded = xmp.load(image_path)
        assert loaded.rating == -1

    def test_malformed_xml_returns_empty(self, xmp, image_path):
        sidecar = xmp.sidecar_path_for(image_path)
        sidecar.write_text("<not valid xml", encoding="utf-8")
        assert xmp.load(image_path).is_empty()


class TestSettingsIntegration:
    def test_export_for_includes_rating_and_tags(self, xmp, image_path):
        from Imervue.user_settings.tags import add_tag
        from Imervue.user_settings.user_setting_dict import user_setting_dict

        user_setting_dict["image_ratings"] = {image_path: 5}
        user_setting_dict["image_titles"] = {image_path: "Hero"}
        add_tag("travel", image_path)
        add_tag("japan", image_path)

        xmp.export_for(image_path)
        loaded = xmp.load(image_path)
        assert loaded.rating == 5
        assert loaded.title == "Hero"
        assert set(loaded.keywords) == {"travel", "japan"}

    def test_import_for_restores_rating_and_tags(self, xmp, image_path):
        from Imervue.user_settings.tags import get_tags_for_image
        from Imervue.user_settings.user_setting_dict import user_setting_dict

        xmp.save(image_path, xmp.XmpData(
            rating=3,
            title="Imported",
            keywords=["alpha", "beta"],
            color_label="blue",
        ))
        xmp.import_for(image_path)

        assert user_setting_dict["image_ratings"][image_path] == 3
        assert user_setting_dict["image_titles"][image_path] == "Imported"
        assert set(get_tags_for_image(image_path)) == {"alpha", "beta"}

    def test_import_empty_rating_clears_existing(self, xmp, image_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict

        user_setting_dict["image_ratings"] = {image_path: 4}
        xmp.save(image_path, xmp.XmpData(title="No rating"))
        xmp.import_for(image_path)
        assert image_path not in user_setting_dict.get("image_ratings", {})


class TestXmpData:
    def test_is_empty_default(self, xmp):
        assert xmp.XmpData().is_empty()

    def test_is_empty_false_with_rating(self, xmp):
        assert xmp.XmpData(rating=1).is_empty() is False

    def test_is_empty_false_with_keywords(self, xmp):
        assert xmp.XmpData(keywords=["x"]).is_empty() is False
