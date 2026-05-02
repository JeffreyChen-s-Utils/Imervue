"""Tests for the multi-page PaintProject + save / load."""
from __future__ import annotations

import json
import zipfile

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.paint_project import (
    MAX_PAGES,
    PaintProject,
    ProjectPage,
)
from Imervue.paint.paint_project_io import (
    PROJECT_FILE_EXTENSION,
    PROJECT_FORMAT_VERSION,
    load_project,
    save_project,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_with_color(rgb, h=4, w=4):
    doc = PaintDocument()
    base = np.zeros((h, w, 4), dtype=np.uint8)
    base[..., :3] = rgb
    base[..., 3] = 255
    doc.load_image(base)
    return doc


def _three_page_project():
    project = PaintProject(name="Comic", author="Jeffrey")
    project.pages = [
        ProjectPage(_doc_with_color((255, 0, 0)), name="Cover"),
        ProjectPage(_doc_with_color((0, 255, 0)), name="Page 1"),
        ProjectPage(_doc_with_color((0, 0, 255)), name="Page 2"),
    ]
    return project


# ---------------------------------------------------------------------------
# ProjectPage / PaintProject construction
# ---------------------------------------------------------------------------


def test_project_page_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        ProjectPage(_doc_with_color((0, 0, 0)), name="   ")


def test_project_default_name_is_non_empty():
    p = PaintProject()
    assert p.name.strip() != ""
    assert p.page_count == 0


def test_project_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        PaintProject(name="   ")


def test_project_clamps_active_page_index():
    project = _three_page_project()
    project.active_page_index = 99
    project.__post_init__()
    assert project.active_page_index == 2


# ---------------------------------------------------------------------------
# add_page / remove_page / move_page / set_active / rename
# ---------------------------------------------------------------------------


def test_add_page_inserts_after_active():
    p = _three_page_project()
    p.set_active_page(0)
    new = ProjectPage(_doc_with_color((10, 10, 10)), name="Inserted")
    idx = p.add_page(new)
    assert idx == 1
    assert p.pages[1] is new
    assert p.active_page_index == 1


def test_add_page_to_empty_project_appends():
    p = PaintProject()
    new = ProjectPage(_doc_with_color((0, 0, 0)), name="First")
    p.add_page(new)
    assert p.page_count == 1
    assert p.active_page_index == 0


def test_add_page_at_max_raises():
    p = _three_page_project()
    while p.page_count < MAX_PAGES:
        p.pages.append(ProjectPage(_doc_with_color((0, 0, 0))))
    with pytest.raises(ValueError, match=str(MAX_PAGES)):
        p.add_page(ProjectPage(_doc_with_color((0, 0, 0))))


def test_remove_page_drops_one():
    p = _three_page_project()
    assert p.remove_page(1) is True
    assert p.page_count == 2


def test_remove_last_page_returns_false():
    p = PaintProject(pages=[ProjectPage(_doc_with_color((0, 0, 0)))])
    assert p.remove_page(0) is False


def test_remove_page_out_of_range_returns_false():
    p = _three_page_project()
    assert p.remove_page(99) is False


def test_move_page_re_orders():
    p = _three_page_project()
    p.move_page(0, 2)
    names = [page.name for page in p.pages]
    assert names == ["Page 1", "Page 2", "Cover"]


def test_move_page_keeps_active_pointer_at_same_content():
    p = _three_page_project()
    p.set_active_page(0)   # "Cover"
    p.move_page(0, 2)
    assert p.pages[p.active_page_index].name == "Cover"


def test_move_page_same_index_returns_false():
    p = _three_page_project()
    assert p.move_page(1, 1) is False


def test_set_active_page_out_of_range_raises():
    p = _three_page_project()
    with pytest.raises(IndexError):
        p.set_active_page(99)


def test_rename_page_updates_name():
    p = _three_page_project()
    p.rename_page(0, "New Cover")
    assert p.pages[0].name == "New Cover"


def test_rename_page_blank_raises():
    p = _three_page_project()
    with pytest.raises(ValueError, match="non-empty"):
        p.rename_page(0, "   ")


def test_rename_page_idempotent_returns_false():
    p = _three_page_project()
    assert p.rename_page(0, "Cover") is False


def test_rename_page_out_of_range_returns_false():
    p = _three_page_project()
    assert p.rename_page(99, "X") is False


# ---------------------------------------------------------------------------
# Save / load round-trip
# ---------------------------------------------------------------------------


def test_save_then_load_round_trips_project_metadata(tmp_path):
    project = _three_page_project()
    path = tmp_path / f"comic{PROJECT_FILE_EXTENSION}"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded.name == "Comic"
    assert loaded.author == "Jeffrey"
    assert loaded.page_count == 3


def test_save_then_load_round_trips_page_names(tmp_path):
    project = _three_page_project()
    path = tmp_path / f"comic{PROJECT_FILE_EXTENSION}"
    save_project(project, path)
    loaded = load_project(path)
    assert [p.name for p in loaded.pages] == ["Cover", "Page 1", "Page 2"]


def test_save_then_load_preserves_page_pixels(tmp_path):
    project = _three_page_project()
    path = tmp_path / f"comic{PROJECT_FILE_EXTENSION}"
    save_project(project, path)
    loaded = load_project(path)
    for original, restored in zip(project.pages, loaded.pages, strict=True):
        np.testing.assert_array_equal(
            original.document.layers()[0].image,
            restored.document.layers()[0].image,
        )


def test_save_then_load_preserves_active_page_index(tmp_path):
    project = _three_page_project()
    project.set_active_page(2)
    path = tmp_path / f"comic{PROJECT_FILE_EXTENSION}"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded.active_page_index == 2


def test_save_creates_parent_directory(tmp_path):
    project = _three_page_project()
    path = tmp_path / "nested" / "deep" / f"comic{PROJECT_FILE_EXTENSION}"
    save_project(project, path)
    assert path.exists()


def test_save_empty_project_raises(tmp_path):
    project = PaintProject()
    with pytest.raises(ValueError, match="empty"):
        save_project(project, tmp_path / f"empty{PROJECT_FILE_EXTENSION}")


# ---------------------------------------------------------------------------
# load_project error paths
# ---------------------------------------------------------------------------


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_project(tmp_path / f"ghost{PROJECT_FILE_EXTENSION}")


def test_load_missing_manifest_raises(tmp_path):
    path = tmp_path / f"no_manifest{PROJECT_FILE_EXTENSION}"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("page_0.imervue", b"\x00\x00")
    with pytest.raises(ValueError, match="manifest.json"):
        load_project(path)


def test_load_unsupported_format_version_raises(tmp_path):
    path = tmp_path / f"future{PROJECT_FILE_EXTENSION}"
    manifest = {
        "format_version": 999,
        "name": "X",
        "author": "",
        "active_page_index": 0,
        "pages": [{"name": "P"}],
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="format version"):
        load_project(path)


def test_load_missing_page_blob_raises(tmp_path):
    path = tmp_path / f"missing_page{PROJECT_FILE_EXTENSION}"
    manifest = {
        "format_version": PROJECT_FORMAT_VERSION,
        "name": "X",
        "author": "",
        "active_page_index": 0,
        "pages": [{"name": "P"}],
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        # no page_0.imervue inside
    with pytest.raises(ValueError, match="missing page_0"):
        load_project(path)


def test_load_corrupt_manifest_raises(tmp_path):
    path = tmp_path / f"bad{PROJECT_FILE_EXTENSION}"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", b"not valid json {")
    with pytest.raises(ValueError, match="manifest"):
        load_project(path)


def test_load_manifest_no_pages_raises(tmp_path):
    path = tmp_path / f"no_pages{PROJECT_FILE_EXTENSION}"
    manifest = {
        "format_version": PROJECT_FORMAT_VERSION,
        "name": "X",
        "author": "",
        "active_page_index": 0,
        "pages": [],
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="no pages"):
        load_project(path)
