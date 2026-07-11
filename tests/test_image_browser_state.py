from __future__ import annotations

import os

from PIL import Image

from Imervue.image.browser_state import (
    ImageFilterSpec,
    ImageMetadataIndex,
    auto_match_same_name,
    detect_renamed_paths,
    filter_paths,
    is_missing_file_error,
    is_transient_load_error,
    migrate_view_path_state,
    relocate_root,
    remove_missing,
)


def _png(path, size=(8, 8), color=(20, 40, 60)):
    Image.new("RGB", size, color).save(path)
    return str(path)


def test_structured_filter_matches_filename_rating_and_date(tmp_path):
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    a = _png(tmp_path / "sunset.png")
    b = _png(tmp_path / "portrait.png")
    old = user_setting_dict.get("image_ratings")
    try:
        user_setting_dict["image_ratings"] = {a: 4, b: 1}
        index = ImageMetadataIndex()
        result = filter_paths(
            [a, b],
            ImageFilterSpec(filename="sun", rating=">=3"),
            index,
        )
        assert result == [a]
        assert index.get(a).width == 8
    finally:
        if old is None:
            user_setting_dict.pop("image_ratings", None)
        else:
            user_setting_dict["image_ratings"] = old


def test_missing_batch_helpers_match_remove_and_relocate(tmp_path):
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    missing = str(old_root / "a.png")
    matched = _png(new_root / "a.png")

    assert auto_match_same_name([missing], str(new_root)) == {missing: matched}
    assert remove_missing([missing, matched]) == [matched]
    assert relocate_root([missing], str(old_root), str(new_root)) == {missing: matched}


def test_detect_renamed_paths_uses_cached_old_signature(tmp_path):
    old = tmp_path / "old_name.png"
    _png(old)
    index = ImageMetadataIndex()
    index.get(str(old))
    new = tmp_path / "new_name.png"
    os.replace(old, new)

    assert detect_renamed_paths([str(old)], [str(new)], index) == {
        str(old): str(new),
    }


def test_migrate_view_path_state_moves_cache_and_selection():
    class View:
        pass

    view = View()
    view.tile_cache = {"old.png": object()}
    view.tile_errors = {"old.png": "bad"}
    view.selected_tiles = {"old.png"}
    view.offline_paths = {"old.png"}
    migrate_view_path_state(view, {"old.png": "new.png"})

    assert "new.png" in view.tile_cache
    assert view.tile_errors == {"new.png": "bad"}
    assert view.selected_tiles == {"new.png"}
    assert view.offline_paths == {"new.png"}


def test_transient_load_error_detection():
    assert is_transient_load_error("The file is locked by another process")
    assert not is_transient_load_error("invalid image header")


def test_missing_file_error_detection():
    # str(FileNotFoundError) shapes from PIL / os on POSIX and Windows.
    assert is_missing_file_error("[Errno 2] No such file or directory: 'a.png'")
    assert is_missing_file_error("The system cannot find the file specified")
    assert is_missing_file_error("The system cannot find the path specified")
    assert is_missing_file_error("file not found: a.png")
    assert is_missing_file_error("Path 'a.png' does not exist")


def test_missing_file_error_rejects_other_failures():
    assert not is_missing_file_error("invalid image header")
    assert not is_missing_file_error("The file is locked by another process")
    assert not is_missing_file_error("")
    assert not is_missing_file_error(None)


def test_metadata_index_sample_hash_tracks_same_content(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    payload = b"x" * 200_000
    a.write_bytes(payload)
    b.write_bytes(payload)
    index = ImageMetadataIndex()
    assert index.sample_hash(str(a)) == index.sample_hash(str(b))
