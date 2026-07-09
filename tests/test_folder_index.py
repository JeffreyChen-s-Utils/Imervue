import os

from Imervue.image import folder_index


def test_folder_index_round_trip(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setattr(folder_index, "_cache_dir", lambda: cache)
    folder = tmp_path / "images"
    folder.mkdir()
    image = folder / "a.png"
    image.write_bytes(b"fake")

    folder_index.save(str(folder), [str(image)], sort_by="name", ascending=True)

    assert folder_index.load(str(folder), sort_by="name", ascending=True) == [str(image)]
    assert folder_index.load(str(folder), sort_by="mtime", ascending=True) is None


def test_folder_index_invalidates_when_folder_mtime_changes(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setattr(folder_index, "_cache_dir", lambda: cache)
    folder = tmp_path / "images"
    folder.mkdir()
    image = folder / "a.png"
    image.write_bytes(b"fake")
    folder_index.save(str(folder), [str(image)], sort_by="name", ascending=True)

    # Bump the folder mtime explicitly: creating a sibling file is not
    # guaranteed to tick the directory timestamp within CI clock resolution.
    stat = folder.stat()
    os.utime(folder, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    assert folder_index.load(str(folder), sort_by="name", ascending=True) is None

