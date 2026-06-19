"""Tests for watched-folder automation (detection + dispatch)."""
from __future__ import annotations

from Imervue.system.watch_folder import (
    WatchFolderService,
    is_image,
    scan_images,
    select_new,
)


def test_is_image_extension_filter():
    assert is_image("photo.JPG")
    assert is_image("scan.tiff")
    assert not is_image("notes.txt")
    assert not is_image("archive.zip")


def test_scan_images_lists_only_images(tmp_path):
    (tmp_path / "a.png").write_bytes(b"\x00")
    (tmp_path / "b.jpg").write_bytes(b"\x00")
    (tmp_path / "c.txt").write_text("x")
    found = scan_images(str(tmp_path))
    assert any(p.endswith("a.png") for p in found)
    assert any(p.endswith("b.jpg") for p in found)
    assert not any(p.endswith("c.txt") for p in found)


def test_scan_images_missing_dir_is_empty():
    assert scan_images("/no/such/folder/here") == set()


def test_select_new_is_set_difference():
    assert select_new({"a", "b"}, {"a", "b", "c"}) == ["c"]
    assert select_new({"a"}, {"a"}) == []


def test_service_dispatches_only_new_files(qapp, tmp_path):
    seen: list[str] = []
    service = WatchFolderService(processor=seen.append)
    emitted: list[int] = []
    service.processed.connect(emitted.append)

    (tmp_path / "first.png").write_bytes(b"\x00")
    service._root = str(tmp_path)
    service._seen = scan_images(str(tmp_path))  # prime — "first" is already known

    # A new image arrives.
    (tmp_path / "second.jpg").write_bytes(b"\x00")
    service._dispatch()
    assert [p.replace("\\", "/").split("/")[-1] for p in seen] == ["second.jpg"]
    assert emitted == [1]

    # No further files → no extra dispatch, no extra signal.
    service._dispatch()
    assert len(seen) == 1
    assert emitted == [1]


def test_service_processor_error_does_not_stop_batch(qapp, tmp_path):
    def boom(_path):
        raise RuntimeError("bad file")

    service = WatchFolderService(processor=boom)
    (tmp_path / "x.png").write_bytes(b"\x00")
    service._root = str(tmp_path)
    service._seen = set()
    # Must swallow the processor error and still report the batch.
    emitted: list[int] = []
    service.processed.connect(emitted.append)
    service._dispatch()
    assert emitted == [1]


def test_dialog_smoke(qapp):
    from Imervue.gui.watch_folder_dialog import WatchFolderDialog

    dialog = WatchFolderDialog(object())
    try:
        assert dialog._service.root == ""
        assert dialog._toggle is not None
    finally:
        dialog._service.stop()
        dialog.deleteLater()
