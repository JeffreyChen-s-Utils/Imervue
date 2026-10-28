"""Review regressions exercise persistence and input boundaries with real temporary files."""
import json
import os
import runpy
import sys
from pathlib import Path

import pytest
from PIL import Image

from Imervue.library import image_index
from Imervue.library.maintenance import run_maintenance
from Imervue.mcp_server import tools_edit
from Imervue.sessions.session_manager import load_session_from_path


@pytest.fixture
def catalog(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    yield image_index
    image_index.close()


def test_maintenance_preserves_existing_and_removed_root_metadata(catalog, tmp_path):
    root = tmp_path / "active"
    other = tmp_path / "removed"
    root.mkdir()
    other.mkdir()
    paths = [root / ".hidden.png", other / "photo.png"]
    for path in paths:
        path.write_bytes(b"image")
        catalog.upsert_image(str(path))
        catalog.set_note(str(path), "valuable note")
        catalog.set_cull_state(str(path), "pick")
        catalog.add_image_tag(str(path), "travel")
    catalog.add_library_root(str(root))
    catalog.add_library_root(str(other))
    catalog.remove_library_root(str(other))
    result = run_maintenance(catalog.list_library_roots(), prune=True)
    assert result["pruned"] == 0
    for path in paths:
        assert catalog.get_image(str(path)) is not None
        assert catalog.get_note(str(path)) == "valuable note"
        assert catalog.get_cull_state(str(path)) == "pick"
    assert catalog.conn().execute("SELECT count(*) FROM image_tags").fetchone()[0] == 2


def test_maintenance_does_not_prune_unavailable_root(catalog, tmp_path):
    unavailable = tmp_path / "offline"
    path = str(unavailable / "photo.png")
    catalog.upsert_image(path)
    assert run_maintenance([str(unavailable)], prune=True)["pruned"] == 0
    assert catalog.get_image(path) is not None


def test_maintenance_retains_unreadable_file(catalog, tmp_path, monkeypatch):
    path = tmp_path / "photo.png"
    catalog.upsert_image(str(path))
    original = os.lstat

    def denied(candidate, *args, **kwargs):
        if os.fspath(candidate) == str(path):
            raise PermissionError("unreadable")
        return original(candidate, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", denied)
    assert run_maintenance([str(tmp_path)], prune=True)["pruned"] == 0
    assert catalog.get_image(str(path)) is not None


@pytest.mark.parametrize("payload", [[], None, 1, {"version": 1, "tabs": 42},
                                     {"version": 1, "selection": 42},
                                     {"version": 1, "tabs": "invalid"}])
def test_session_bad_shapes_raise_load_error(tmp_path, payload):
    source = tmp_path / "session.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_session_from_path(source)


@pytest.mark.parametrize("same_source", [False, True])
def test_mcp_encoder_failure_preserves_destination(tmp_path, monkeypatch, same_source):
    source, target = tmp_path / "source.png", tmp_path / "target.png"
    Image.new("RGB", (2, 2), "red").save(source)
    Image.new("RGB", (2, 2), "blue").save(target)
    if same_source:
        target = source
    original = target.read_bytes()

    def broken_encoder(_image, stream, _name, **_kwargs):
        stream.write(b"partial-image")
        raise OSError("disk write failed")

    monkeypatch.setitem(Image.SAVE, "PNG", broken_encoder)
    with pytest.raises(OSError, match="disk write failed"):
        tools_edit.rotate_image(str(source), str(target), "rotate_90")
    assert target.read_bytes() == original
    assert sorted(path.name for path in tmp_path.iterdir()) == ["source.png", "target.png"]


@pytest.mark.parametrize("geometry", [{"border": 50000}, {"bottom_extra": 100_000_000}])
def test_mcp_frame_rejects_large_canvas_before_allocation(tmp_path, monkeypatch, geometry):
    source = tmp_path / "source.png"
    Image.new("RGB", (2, 2)).save(source)
    original = Image.new

    def guarded_new(mode, size, *args, **kwargs):
        assert size[0] * size[1] <= 100_000_000, "oversized canvas reached allocator"
        return original(mode, size, *args, **kwargs)

    monkeypatch.setattr(Image, "new", guarded_new)
    with pytest.raises(ValueError, match="pixel"):
        tools_edit.apply_frame(str(source), str(tmp_path / "frame.png"), **geometry)
    assert not (tmp_path / "frame.png").exists()


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_frozen_entry_uses_host_gl_platform(monkeypatch, platform):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.delenv("PYOPENGL_PLATFORM", raising=False)
    runpy.run_path(str(Path(__file__).parents[1] / "Imervue" / "__main__.py"),
                   run_name="review_entry")
    assert os.environ.get("PYOPENGL_PLATFORM") == ("nt" if platform == "win32" else None)



@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_frozen_entry_preserves_explicit_gl_override(monkeypatch, platform):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setenv("PYOPENGL_PLATFORM", "egl")
    runpy.run_path(str(Path(__file__).parents[1] / "Imervue" / "__main__.py"),
                   run_name="review_entry")
    assert os.environ["PYOPENGL_PLATFORM"] == "egl"
