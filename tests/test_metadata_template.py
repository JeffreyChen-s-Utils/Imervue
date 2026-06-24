"""Tests for the IPTC/XMP metadata template."""
from __future__ import annotations

from Imervue.user_settings.metadata_template import apply_template


def test_fills_empty_base():
    out = apply_template({}, {"creator": "Jane", "copyright": "(c) Jane"})
    assert out["creator"] == "Jane"
    assert out["copyright"] == "(c) Jane"


def test_fill_empty_only_keeps_existing_scalar():
    out = apply_template({"creator": "Original"}, {"creator": "Template"})
    assert out["creator"] == "Original"


def test_overwrite_mode_replaces_scalar():
    out = apply_template(
        {"creator": "Original"}, {"creator": "Template"}, fill_empty_only=False,
    )
    assert out["creator"] == "Template"


def test_token_expansion_from_meta():
    out = apply_template({}, {"caption": "Shot in {city}, {year}"},
                         {"city": "Oslo", "year": 2024})
    assert out["caption"] == "Shot in Oslo, 2024"


def test_unknown_token_left_verbatim():
    out = apply_template({}, {"caption": "By {creator}"}, {})
    assert out["caption"] == "By {creator}"


def test_keyword_list_merges_in_fill_mode():
    out = apply_template(
        {"keywords": ["sky", "blue"]}, {"keywords": ["blue", "landscape"]},
    )
    assert out["keywords"] == ["sky", "blue", "landscape"]


def test_keyword_list_replaced_in_overwrite_mode():
    out = apply_template(
        {"keywords": ["sky"]}, {"keywords": ["landscape"]}, fill_empty_only=False,
    )
    assert out["keywords"] == ["landscape"]


def test_list_elements_are_token_expanded():
    out = apply_template({}, {"keywords": ["{year} trip"]}, {"year": 2024})
    assert out["keywords"] == ["2024 trip"]


def test_empty_string_counts_as_blank():
    out = apply_template({"creator": ""}, {"creator": "Jane"})
    assert out["creator"] == "Jane"


def test_does_not_mutate_inputs():
    base = {"keywords": ["sky"]}
    template = {"keywords": ["sea"]}
    apply_template(base, template)
    assert base == {"keywords": ["sky"]}
    assert template == {"keywords": ["sea"]}


def test_non_template_base_fields_preserved():
    out = apply_template({"rating": 5}, {"creator": "Jane"})
    assert out["rating"] == 5
    assert out["creator"] == "Jane"
