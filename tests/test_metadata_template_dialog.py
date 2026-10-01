"""Extra Tools > Library & Metadata > Metadata Template stamps title, description and keywords.

``user_settings/metadata_template.py`` (a stationery pad that fills or
overwrites fields with ``{token}`` expansion and merges keyword lists) was
tested but unreachable. The dialog applies it to a selection's title,
description and tags, remembers the template, and confirms first.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from PIL import Image

from Imervue.gui import metadata_template_dialog as mod
from Imervue.user_settings.metadata_template import photo_tokens
from Imervue.user_settings.tags import get_tags_for_image
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for key in ("image_titles", "image_descriptions", "image_tags", mod.SETTING_KEY):
        monkeypatch.setitem(user_setting_dict, key, {})
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


def _photo(tmp_path, name="beach.jpg", when="2024:07:01 10:00:00"):
    exif = Image.Exif()
    exif[0x8769] = {0x9003: when}
    path = tmp_path / "Trip" / name
    path.parent.mkdir(exist_ok=True)
    Image.new("RGB", (4, 4)).save(path, exif=exif)
    return str(path)


def test_photo_tokens():
    tokens = photo_tokens("D:/Trip/beach.jpg", datetime(2024, 7, 1, 10))
    assert tokens == {"filename": "beach", "name": "beach.jpg", "folder": "Trip",
                      "date": "2024-07-01", "year": "2024"}
    assert photo_tokens("x.png", None)["date"] == ""


def test_the_template_leaves_out_empty_fields_and_splits_keywords():
    assert mod.template_from_fields("  ", "", "") == {}
    assert mod.template_from_fields("T", " ", "sea, , sun ,sea") == {
        "title": "T", "keywords": ["sea", "sun"]}


def test_fill_empty_keeps_what_is_there_and_adds_keywords(tmp_path):
    path = _photo(tmp_path)
    user_setting_dict["image_titles"][path] = "Mine"
    user_setting_dict["image_tags"] = {"old": [path]}
    template = {"title": "{folder} {date}", "description": "{filename} in {year}",
                "keywords": ["sea"]}
    assert mod.apply_to_photo(path, template, fill_empty_only=True) is True
    assert user_setting_dict["image_titles"][path] == "Mine"
    assert user_setting_dict["image_descriptions"][path] == "beach in 2024"
    assert sorted(get_tags_for_image(path)) == ["old", "sea"]


def test_overwrite_replaces_fields_and_tags(tmp_path):
    path = _photo(tmp_path)
    user_setting_dict["image_titles"][path] = "Mine"
    user_setting_dict["image_tags"] = {"old": [path]}
    template = {"title": "{folder} {date}", "keywords": ["sea"]}
    assert mod.apply_to_photo(path, template, fill_empty_only=False) is True
    assert user_setting_dict["image_titles"][path] == "Trip 2024-07-01"
    assert get_tags_for_image(path) == ["sea"]
    assert "old" not in user_setting_dict["image_tags"]


def test_a_photo_already_stamped_is_not_counted(tmp_path):
    path = _photo(tmp_path)
    template = {"title": "Fixed"}
    assert mod.apply_to_photos([path], template, fill_empty_only=True) == 1
    assert mod.apply_to_photos([path], template, fill_empty_only=True) == 0


@pytest.fixture
def dialog(qapp, tmp_path, monkeypatch):
    paths = [_photo(tmp_path, "a.jpg"), _photo(tmp_path, "b.jpg")]
    asked = []
    monkeypatch.setattr(mod, "confirm", lambda parent, title, q: asked.append(q) or True)
    dlg = mod.MetadataTemplateDialog(paths)
    yield dlg, paths, asked
    dlg.deleteLater()


def test_apply_stamps_every_photo_after_asking_and_remembers(dialog):
    dlg, paths, asked = dialog
    dlg._description.setText("{filename} at {folder}")  # noqa: SLF001
    dlg._keywords.setText("sea, sun")  # noqa: SLF001
    assert dlg.apply() == 2
    assert asked == ["Stamp the template on 2 photo(s)?"]
    assert user_setting_dict["image_descriptions"][paths[1]] == "b at Trip"
    assert get_tags_for_image(paths[0]) == ["sea", "sun"]
    assert user_setting_dict[mod.SETTING_KEY] == {
        "title": "", "description": "{filename} at {folder}", "keywords": ["sea", "sun"],
        "fill_empty_only": True}
    assert dlg._status.text() == "Changed 2 of 2 photo(s)."  # noqa: SLF001


def test_the_template_comes_back_next_time(qapp, tmp_path, monkeypatch):
    user_setting_dict[mod.SETTING_KEY] = {"title": "T", "description": "D",
                                          "keywords": ["k1", "k2"], "fill_empty_only": False}
    dlg = mod.MetadataTemplateDialog([])
    try:
        assert (dlg._title.text(), dlg._keywords.text()) == ("T", "k1, k2")  # noqa: SLF001
        assert not dlg._fill_empty.isChecked()  # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_an_empty_template_asks_for_a_field(dialog):
    dlg, _paths, asked = dialog
    assert dlg.apply() == 0
    assert asked == [] and dlg._status.text() == "Fill in at least one field."  # noqa: SLF001


def test_declining_changes_nothing(dialog, monkeypatch):
    dlg, paths, _asked = dialog
    monkeypatch.setattr(mod, "confirm", lambda *a: False)
    dlg._title.setText("T")  # noqa: SLF001
    assert dlg.apply() == 0
    assert paths[0] not in user_setting_dict["image_titles"]
