"""Operation bounds and deferred work on progressive folder browsing paths."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image
from PySide6.QtTest import QTest

from Imervue.gpu_image_view.images.folder_scan_updates import FolderScanUpdates
from Imervue.image.browser_state import (
    ImageFilterSpec, ImageMetadataIndex, detect_renamed_paths, filter_paths,
)


def test_unchanged_large_lists_use_linear_membership_work():
    class Counted(str):
        comparisons = 0
        __hash__ = str.__hash__

        def __eq__(self, other):
            Counted.comparisons += 1
            return str.__eq__(self, other)

    old = [Counted(f"image_{i}.png") for i in range(3000)]
    new = [Counted(str(path)) for path in old]
    assert detect_renamed_paths(iter(old), iter(new)) == {}
    assert Counted.comparisons < len(old) * 10


def test_stat_priming_and_filters_never_probe_image_headers(tmp_path, monkeypatch):
    path = tmp_path / "image.png"
    Image.new("RGB", (20, 12)).save(path)
    index = ImageMetadataIndex()
    reader = MagicMock(side_effect=AssertionError("Image header read on a listing path"))
    monkeypatch.setattr(Image, "open", reader)
    index.prime([str(path)])
    assert index.peek(str(path)).width is None
    assert filter_paths([str(path)], ImageFilterSpec(filename="image"), index) == [str(path)]
    assert not reader.called
    assert index.peek(str(path)).size > 0


def test_dimensions_are_still_read_on_explicit_demand(tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGB", (20, 12)).save(path)
    index = ImageMetadataIndex()
    index.prime([str(path)])
    assert index.peek(str(path)).width is None
    assert (index.get(str(path)).width, index.get(str(path)).height) == (20, 12)


def test_cheap_metadata_still_follows_external_renames(tmp_path, monkeypatch):
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    before.write_bytes(b"header not needed for a rename")
    index = ImageMetadataIndex()
    index.prime([str(before)])
    before.rename(after)
    monkeypatch.setattr(Image, "open", MagicMock(side_effect=AssertionError("Header read")))
    assert detect_renamed_paths(iter([str(before)]), iter([str(after)]), index) == {
        str(before): str(after),
    }
    index.move(str(before), str(after))
    assert index.peek(str(before)) is None
    assert index.peek(str(after)).size > 0
    after.unlink()
    index.drop_missing()
    assert index.peek(str(after)) is None


def test_a_failed_stat_is_retried_when_the_file_appears(tmp_path):
    path = str(tmp_path / "later.png")
    index = ImageMetadataIndex()
    assert index.get_stat(path).size == 0
    assert index.peek(path) is None
    Image.new("RGB", (2, 2)).save(path)
    assert index.get_stat(path).size > 0


def test_hidden_list_view_does_no_population_work():
    from Imervue.gui.main_window_browse import MainWindowBrowseMixin
    table = MagicMock()
    owner = SimpleNamespace(_browse_mode="grid", image_list_view=table,
                            viewer=SimpleNamespace(model=SimpleNamespace(images=["a.png"])))
    MainWindowBrowseMixin.refresh_list_view(owner)
    table.set_paths.assert_not_called()
    owner._browse_mode = "list"
    MainWindowBrowseMixin.refresh_list_view(owner)
    assert table.set_paths.call_args.args[0] == ["a.png"]


def test_list_population_uses_cached_metadata_without_eager_header_reads(qapp, tmp_path, monkeypatch):
    from Imervue.gui.image_list_view import ImageListModel
    path = tmp_path / "image.png"
    Image.new("RGB", (20, 12)).save(path)
    index = ImageMetadataIndex()
    index.prime([str(path)])
    reader = MagicMock(side_effect=AssertionError("Eager image header read"))
    monkeypatch.setattr(index, "get", reader)
    model = ImageListModel([str(path)], metadata_index=index)
    try:
        assert model.rowCount() == 1
        assert model._rows[0].size_kb > 0
        assert not reader.called
    finally:
        model.deleteLater()


def test_scan_bursts_show_first_batch_then_only_the_final_sorted_list(qapp):
    applied = []
    updates = FolderScanUpdates(applied.append)
    try:
        updates.add(["img10.png"])
        assert applied == [["img10.png"]]
        for i in range(100):
            updates.add([f"img{i}.png"])
        assert len(applied) == 1
        final = ["img2.png", "img10.png"]
        updates.finish(final)
        QTest.qWait(80)
        assert applied[-1] == final
        assert len(applied) == 2
    finally:
        updates.deleteLater()


def test_slow_scan_publishes_accumulated_batches_and_cancel_stops_updates(qapp):
    applied = []
    updates = FolderScanUpdates(applied.append)
    try:
        updates.add(["first.png"])
        updates.add(["first.png", "second.png"])
        QTest.qWait(80)
        assert applied[-1] == ["first.png", "second.png"]
        updates.add(["third.png"])
        updates.cancel()
        updates.add(["stale.png"])
        QTest.qWait(80)
        assert len(applied) == 2
    finally:
        updates.deleteLater()


def test_cancelled_scan_drops_queued_batches_and_completion(qapp):
    from Imervue.gpu_image_view.images import image_loader
    applied = []
    updates = FolderScanUpdates(applied.append)
    view = SimpleNamespace(_folder_scan_generation=1, _folder_scan_updates=updates,
                           _folder_scan_worker=MagicMock(), _folder_scan_active=True)
    worker = view._folder_scan_worker
    updates.add(["first.png"])
    updates.add(["pending.png"])
    image_loader.cancel_folder_scan(view)
    image_loader._on_folder_scan_batch(view, "folder", ["stale.png"], 1)
    image_loader._on_folder_scan_finished(view, "folder", ["stale.png"], 1)
    QTest.qWait(80)
    worker.abort.assert_called_once()
    assert not view._folder_scan_active
    assert applied == [["first.png"]]


@pytest.mark.parametrize("images", [[], ["image.png"]])
def test_empty_finished_scan_stops_unknown_total_progress(qapp, monkeypatch, images):
    from Imervue.gpu_image_view.images import image_loader
    monkeypatch.setattr(image_loader, "_maybe_hint_heif", lambda *_: None)
    model = SimpleNamespace(images=[])
    updates = FolderScanUpdates(lambda paths: setattr(model, "images", paths))
    window = SimpleNamespace(_hide_progress=MagicMock())
    view = SimpleNamespace(_folder_scan_generation=1, _folder_scan_updates=updates,
                           _folder_scan_worker=object(), _folder_scan_active=True,
                           main_window=window, model=model)
    try:
        image_loader._on_folder_scan_finished(view, "folder", images, 1)
        assert not view._folder_scan_active
        assert window._hide_progress.call_count == (0 if images else 1)
    finally:
        updates.deleteLater()
