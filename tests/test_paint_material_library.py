"""Tests for the material library index — pure logic, no Qt."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Imervue.paint.material_library import (
    DEFAULT_CATEGORY,
    MATERIAL_CATEGORIES,
    MaterialEntry,
    MaterialIndex,
    find_index_file,
)


def _touch_image(path: Path) -> Path:
    """Create a 1×1 PNG-ish placeholder. The index never opens the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG placeholder")
    return path


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def test_categories_includes_documented_set():
    assert set(MATERIAL_CATEGORIES) == {
        "texture", "tone", "pattern", "brush_tip", "pose",
    }


def test_default_category_in_set():
    assert DEFAULT_CATEGORY in MATERIAL_CATEGORIES


# ---------------------------------------------------------------------------
# MaterialEntry round-trip
# ---------------------------------------------------------------------------


def test_entry_to_dict_emits_json_friendly_types(tmp_path):
    entry = MaterialEntry(
        name="dot_60", path=tmp_path / "tone" / "dot_60.png",
        category="tone", tags=("halftone", "dotted"),
    )
    raw = entry.to_dict()
    assert raw["name"] == "dot_60"
    assert raw["category"] == "tone"
    assert raw["tags"] == ["halftone", "dotted"]
    # path is serialised as a string so json.dumps doesn't choke.
    assert isinstance(raw["path"], str)


def test_entry_from_dict_round_trip(tmp_path):
    original = MaterialEntry(
        name="paper",
        path=tmp_path / "texture" / "paper.png",
        category="texture",
        tags=("rough", "fibre"),
    )
    rebuilt = MaterialEntry.from_dict(original.to_dict())
    assert rebuilt == original


def test_entry_from_dict_resolves_relative_against_root(tmp_path):
    rebuilt = MaterialEntry.from_dict(
        {"name": "paper", "path": "texture/paper.png", "category": "texture"},
        root=tmp_path,
    )
    assert rebuilt.path == tmp_path / "texture" / "paper.png"


def test_entry_from_dict_drops_unknown_category(tmp_path):
    rebuilt = MaterialEntry.from_dict({
        "name": "x", "path": str(tmp_path / "x.png"), "category": "fractal",
    })
    assert rebuilt.category == DEFAULT_CATEGORY


def test_entry_from_dict_recovers_corrupt_tags(tmp_path):
    rebuilt = MaterialEntry.from_dict({
        "name": "x", "path": str(tmp_path / "x.png"), "tags": "not a list",
    })
    assert rebuilt.tags == ()


def test_entry_from_dict_uses_path_stem_when_name_missing(tmp_path):
    rebuilt = MaterialEntry.from_dict({"path": str(tmp_path / "rough.png")})
    assert rebuilt.name == "rough"


# ---------------------------------------------------------------------------
# MaterialIndex.from_directory
# ---------------------------------------------------------------------------


def test_from_directory_returns_empty_for_missing_root(tmp_path):
    idx = MaterialIndex.from_directory(tmp_path / "does-not-exist")
    assert len(idx) == 0


def test_from_directory_returns_empty_for_file_root(tmp_path):
    f = tmp_path / "single.png"
    f.write_bytes(b"x")
    idx = MaterialIndex.from_directory(f)
    assert len(idx) == 0


def test_from_directory_categorises_by_first_component(tmp_path):
    _touch_image(tmp_path / "tone" / "dot.png")
    _touch_image(tmp_path / "pattern" / "bricks.png")
    _touch_image(tmp_path / "texture" / "paper.png")
    idx = MaterialIndex.from_directory(tmp_path)
    by_cat = {entry.category: entry for entry in idx.entries}
    assert by_cat["tone"].name == "dot"
    assert by_cat["pattern"].name == "bricks"
    assert by_cat["texture"].name == "paper"


def test_from_directory_unknown_subdir_falls_back_to_default(tmp_path):
    _touch_image(tmp_path / "my_random" / "thing.png")
    idx = MaterialIndex.from_directory(tmp_path)
    assert idx.entries[0].category == DEFAULT_CATEGORY


def test_from_directory_skips_non_image_files(tmp_path):
    _touch_image(tmp_path / "tone" / "good.png")
    (tmp_path / "tone" / "readme.txt").write_text("notes", encoding="utf-8")
    idx = MaterialIndex.from_directory(tmp_path)
    assert len(idx) == 1


def test_from_directory_respects_default_category_argument(tmp_path):
    _touch_image(tmp_path / "loose.png")
    idx = MaterialIndex.from_directory(tmp_path, default_category="brush_tip")
    assert idx.entries[0].category == "brush_tip"


def test_from_directory_rejects_unknown_default_category(tmp_path):
    with pytest.raises(ValueError, match="unknown default_category"):
        MaterialIndex.from_directory(tmp_path, default_category="zalgo")


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def _populated_index(tmp_path: Path) -> MaterialIndex:
    return MaterialIndex(entries=[
        MaterialEntry(
            name="halftone_60", path=tmp_path / "h.png",
            category="tone", tags=("halftone", "dot"),
        ),
        MaterialEntry(
            name="brick_red", path=tmp_path / "b.png",
            category="pattern", tags=("seamless",),
        ),
        MaterialEntry(
            name="paper_rough", path=tmp_path / "p.png",
            category="texture", tags=("paper", "rough"),
        ),
    ])


def test_filter_by_category(tmp_path):
    idx = _populated_index(tmp_path)
    out = idx.filter(category="tone")
    assert [e.name for e in out] == ["halftone_60"]


def test_filter_by_query_matches_name_or_tag(tmp_path):
    idx = _populated_index(tmp_path)
    out = idx.filter(query="rough")
    assert [e.name for e in out] == ["paper_rough"]


def test_filter_query_is_case_insensitive(tmp_path):
    idx = _populated_index(tmp_path)
    out = idx.filter(query="HALFTONE")
    assert [e.name for e in out] == ["halftone_60"]


def test_filter_query_requires_all_tokens(tmp_path):
    """Multiple tokens are AND-combined — both must appear."""
    idx = _populated_index(tmp_path)
    out = idx.filter(query="paper rough")
    assert [e.name for e in out] == ["paper_rough"]
    assert idx.filter(query="paper halftone") == []


def test_filter_combined_category_and_query(tmp_path):
    idx = _populated_index(tmp_path)
    out = idx.filter(category="texture", query="rough")
    assert [e.name for e in out] == ["paper_rough"]
    out_no_match = idx.filter(category="tone", query="rough")
    assert out_no_match == []


def test_filter_empty_query_returns_all_in_category(tmp_path):
    idx = _populated_index(tmp_path)
    out = idx.filter(category="pattern", query="")
    assert [e.name for e in out] == ["brick_red"]


def test_filter_empty_query_no_category_returns_all(tmp_path):
    idx = _populated_index(tmp_path)
    out = idx.filter(query="")
    assert len(out) == 3


# ---------------------------------------------------------------------------
# categories()
# ---------------------------------------------------------------------------


def test_categories_returns_only_present_categories(tmp_path):
    idx = MaterialIndex(entries=[
        MaterialEntry(name="x", path=tmp_path / "x.png", category="tone"),
        MaterialEntry(name="y", path=tmp_path / "y.png", category="texture"),
    ])
    assert idx.categories() == ("texture", "tone")


def test_categories_preserves_canonical_order(tmp_path):
    idx = MaterialIndex(entries=[
        MaterialEntry(name="x", path=tmp_path / "x.png", category="pose"),
        MaterialEntry(name="y", path=tmp_path / "y.png", category="texture"),
        MaterialEntry(name="z", path=tmp_path / "z.png", category="tone"),
    ])
    # Even though entries were added pose / texture / tone, the
    # output follows the canonical MATERIAL_CATEGORIES order.
    assert idx.categories() == ("texture", "tone", "pose")


def test_categories_empty_when_no_entries():
    assert MaterialIndex().categories() == ()


# ---------------------------------------------------------------------------
# save_to / load_from / find_index_file
# ---------------------------------------------------------------------------


def test_save_to_and_load_from_round_trip(tmp_path):
    original = _populated_index(tmp_path)
    target = tmp_path / "library.json"
    original.save_to(target)
    rebuilt = MaterialIndex.load_from(target)
    assert [e.name for e in rebuilt.entries] == [e.name for e in original.entries]


def test_load_from_missing_file_yields_empty_index(tmp_path):
    idx = MaterialIndex.load_from(tmp_path / "absent.json")
    assert len(idx) == 0


def test_load_from_corrupt_json_yields_empty_index(tmp_path):
    target = tmp_path / "broken.json"
    target.write_text("{not valid json", encoding="utf-8")
    idx = MaterialIndex.load_from(target)
    assert len(idx) == 0


def test_load_from_root_param_resolves_relative_paths(tmp_path):
    target = tmp_path / "lib.json"
    target.write_text(json.dumps({
        "entries": [{
            "name": "rel", "path": "tone/dot.png", "category": "tone",
        }],
    }), encoding="utf-8")
    rebuilt = MaterialIndex.load_from(target, root=tmp_path)
    assert rebuilt.entries[0].path == tmp_path / "tone" / "dot.png"


def test_load_from_drops_malformed_entries(tmp_path):
    target = tmp_path / "lib.json"
    target.write_text(json.dumps({
        "entries": [
            "garbage",
            None,
            {"name": "ok", "path": str(tmp_path / "ok.png"), "category": "tone"},
        ],
    }), encoding="utf-8")
    rebuilt = MaterialIndex.load_from(target)
    assert len(rebuilt) == 1
    assert rebuilt.entries[0].name == "ok"


def test_find_index_file(tmp_path):
    assert find_index_file(tmp_path) == tmp_path / "index.json"


# ---------------------------------------------------------------------------
# merged()
# ---------------------------------------------------------------------------


def test_merged_concatenates_sources(tmp_path):
    a = MaterialIndex(entries=[
        MaterialEntry(name="a", path=tmp_path / "a.png", category="tone"),
    ])
    b = MaterialIndex(entries=[
        MaterialEntry(name="b", path=tmp_path / "b.png", category="pattern"),
    ])
    out = MaterialIndex.merged((a, b))
    assert [e.name for e in out.entries] == ["a", "b"]


def test_merged_first_seen_wins_for_duplicates(tmp_path):
    """User library entries (listed first) override built-ins."""
    user_path = tmp_path / "shared.png"
    user_path.write_bytes(b"x")
    user = MaterialIndex(entries=[
        MaterialEntry(name="user_shared", path=user_path, category="tone"),
    ])
    builtin = MaterialIndex(entries=[
        MaterialEntry(name="builtin_shared", path=user_path, category="tone"),
    ])
    out = MaterialIndex.merged((user, builtin))
    assert len(out) == 1
    assert out.entries[0].name == "user_shared"


# ---------------------------------------------------------------------------
# MaterialDock — Qt smoke test
# ---------------------------------------------------------------------------


def test_material_dock_initially_shows_empty_hint(qapp):
    from Imervue.paint.dock_panels import MaterialDock
    dock = MaterialDock()
    try:
        # isVisible() requires the widget tree to be shown; check the
        # explicit flag instead so the test stays headless.
        assert not dock._empty_hint.isHidden()  # noqa: SLF001
    finally:
        dock.deleteLater()


def test_material_dock_set_index_populates_grid(qapp, tmp_path):
    from Imervue.paint.dock_panels import MaterialDock

    p = tmp_path / "tone" / "dot.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    idx = MaterialIndex(entries=[
        MaterialEntry(name="dot", path=p, category="tone"),
    ])
    dock = MaterialDock()
    try:
        dock.set_index(idx)
        # Grid contains one widget; empty hint hidden.
        assert dock._grid_layout.count() == 1  # noqa: SLF001
        assert dock._empty_hint.isHidden()  # noqa: SLF001
    finally:
        dock.deleteLater()


def test_material_dock_search_filters_grid(qapp, tmp_path):
    from Imervue.paint.dock_panels import MaterialDock

    p1 = tmp_path / "a.png"
    p1.write_bytes(b"x")
    p2 = tmp_path / "b.png"
    p2.write_bytes(b"x")
    idx = MaterialIndex(entries=[
        MaterialEntry(name="halftone", path=p1, category="tone"),
        MaterialEntry(name="bricks", path=p2, category="pattern"),
    ])
    dock = MaterialDock(index=idx)
    try:
        dock._search.setText("halftone")  # noqa: SLF001
        assert dock._grid_layout.count() == 1  # noqa: SLF001
    finally:
        dock.deleteLater()


def test_material_dock_emits_path_on_thumbnail_click(qapp, tmp_path):
    from Imervue.paint.dock_panels import MaterialDock
    from PySide6.QtWidgets import QToolButton

    p = tmp_path / "tile.png"
    p.write_bytes(b"x")
    idx = MaterialIndex(entries=[
        MaterialEntry(name="tile", path=p, category="texture"),
    ])
    dock = MaterialDock(index=idx)
    try:
        emitted: list[str] = []
        dock.material_chosen.connect(emitted.append)
        # The grid host's first child is the thumbnail button.
        thumb = dock._grid_host.findChildren(QToolButton)[0]  # noqa: SLF001
        thumb.click()
        assert emitted == [str(p)]
    finally:
        dock.deleteLater()
