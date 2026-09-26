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



def test_a_cache_from_before_natural_name_order_is_ignored(tmp_path, monkeypatch):
    """Cached name orders put img10 before img2; they must be rebuilt, not reused."""
    import json
    cache = tmp_path / "cache"
    monkeypatch.setattr(folder_index, "_cache_dir", lambda: cache)
    folder = tmp_path / "images"
    folder.mkdir()
    image = folder / "a.png"
    image.write_bytes(b"fake")
    folder_index.save(str(folder), [str(image)], sort_by="name", ascending=True)
    cached = folder_index._cache_path(str(folder))  # noqa: SLF001
    data = json.loads(cached.read_text(encoding="utf-8"))
    del data["format"]
    cached.write_text(json.dumps(data), encoding="utf-8")
    assert folder_index.load(str(folder), sort_by="name", ascending=True) is None



def _cached_folder(tmp_path, monkeypatch, names=("a.png", "b.png")):
    cache = tmp_path / "cache"
    monkeypatch.setattr(folder_index, "_cache_dir", lambda: cache)
    folder = tmp_path / "images"
    folder.mkdir()
    images = []
    for name in names:
        image = folder / name
        image.write_bytes(b"fake")
        images.append(image)
    folder_index.save(str(folder), [str(i) for i in images], sort_by="taken", ascending=True)
    return folder, images


def _keep_folder_time(folder, stat):
    """Put the folder's mtime back: only the file under test may look changed."""
    os.utime(folder, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def test_a_file_rewritten_in_place_rebuilds_the_order(tmp_path, monkeypatch):
    """Editing a file's contents leaves the folder's time alone on NTFS: the old order came back."""
    folder, images = _cached_folder(tmp_path, monkeypatch)
    folder_stat = folder.stat()
    before = images[0].stat()
    images[0].write_bytes(b"a longer rewrite")
    os.utime(images[0], ns=(before.st_atime_ns, before.st_mtime_ns + 5_000_000))
    _keep_folder_time(folder, folder_stat)
    assert folder_index.load(str(folder), sort_by="taken", ascending=True) is None


def test_a_touched_file_of_the_same_size_rebuilds_too(tmp_path, monkeypatch):
    folder, images = _cached_folder(tmp_path, monkeypatch)
    folder_stat = folder.stat()
    before = images[1].stat()
    os.utime(images[1], ns=(before.st_atime_ns, before.st_mtime_ns + 5_000_000))
    _keep_folder_time(folder, folder_stat)
    assert folder_index.load(str(folder), sort_by="taken", ascending=True) is None


def test_a_deleted_file_is_dropped_and_the_rest_keep_their_order(tmp_path, monkeypatch):
    folder, images = _cached_folder(tmp_path, monkeypatch, names=("c.png", "a.png", "b.png"))
    folder_stat = folder.stat()
    images[1].unlink()
    _keep_folder_time(folder, folder_stat)
    assert folder_index.load(str(folder), sort_by="taken", ascending=True) == [
        str(images[0]), str(images[2])]


def test_an_unchanged_folder_reuses_the_order(tmp_path, monkeypatch):
    folder, images = _cached_folder(tmp_path, monkeypatch, names=("c.png", "a.png"))
    assert folder_index.load(str(folder), sort_by="taken", ascending=True) == [str(i) for i in images]


def test_a_cache_without_stamps_is_ignored(tmp_path, monkeypatch):
    import json
    folder, _images = _cached_folder(tmp_path, monkeypatch)
    cached = folder_index._cache_path(str(folder))  # noqa: SLF001
    data = json.loads(cached.read_text(encoding="utf-8"))
    del data["stamps"]
    cached.write_text(json.dumps(data), encoding="utf-8")
    assert folder_index.load(str(folder), sort_by="taken", ascending=True) is None
