"""The four real worker families preserve committed items and failure-only retries."""

from functools import partial
from io import BytesIO
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from PIL import Image

from Imervue.gui.background_jobs import JobRegistry
from Imervue.gui import ai_upscale_dialog as upscale
from Imervue.gui import batch_export_dialog as batch
from Imervue.gui.library_search_dialog import _retry_scan
from Imervue.library import image_index, scanner
from Imervue.plugin import plugin_downloader as download


@pytest.fixture
def registry(qapp):
    value = JobRegistry()
    yield value
    value.drain()
    value.poll()
    value.deleteLater()


def test_export_dialog_registers_captured_settings(
    registry, qapp, pump_until, tmp_path, monkeypatch
):
    source = tmp_path / "photo.png"
    Image.new("RGB", (4, 3)).save(source)
    output = tmp_path / "out"
    output.mkdir()
    monkeypatch.setattr(batch, "job_registry", lambda: registry)
    dialog = batch.BatchExportDialog(SimpleNamespace(main_window=None), [str(source)])
    dialog._dir_edit.setText(str(output))
    dialog._fmt_combo.setCurrentText("PNG")
    dialog._do_export()
    worker = registry.jobs[-1].worker
    try:
        job = registry.jobs[-1]
        assert pump_until(lambda: job.settled)
        assert job.state.snapshot().items[0].output == str(output / "photo.png")
        assert job.retry_factory is not None
    finally:
        assert worker.wait(5000)
        dialog.deleteLater()


def test_index_retry_does_not_probe_previously_committed_chunk(
    registry,
    qapp,
    pump_until,
    tmp_path,
    monkeypatch,
):
    image_index.set_db_path(tmp_path / "catalog.db")
    sources = [tmp_path / name for name in ("one.png", "two.png")]
    for source in sources:
        Image.new("RGB", (3, 2)).save(source)
    monkeypatch.setattr(scanner, "_SCAN_COMMIT_CHUNK", 1)
    original = scanner._probe
    attempted = []
    broken = True

    def probe(path, stat, **options):
        attempted.append(str(path))
        if broken and path == sources[1]:
            raise OSError("permission")
        return original(path, stat, **options)

    monkeypatch.setattr(scanner, "_probe", probe)
    worker = scanner.LibraryScanThread([], paths=[str(p) for p in sources], with_phash=False)
    job = registry.add(worker, "Index", partial(_retry_scan, with_phash=False))
    worker.start()
    try:
        assert pump_until(lambda: job.settled)
        assert job.state.snapshot().status == "partial"
        assert job.state.failed_paths() == (str(sources[1]),)
        assert image_index.get_image(str(sources[0])) is not None
        assert image_index.get_image(str(sources[1])) is None
        broken = False
        following = registry.retry(job)
        assert following is not None and pump_until(lambda: following.settled)
        assert attempted == [str(p) for p in (*sources, sources[1])]
        assert image_index.count_images() == 2
    finally:
        assert worker.wait(5000)
        registry.drain()
        image_index.close()


def test_upscale_partial_retry_and_model_initialization_failure(
    registry,
    qapp,
    pump_until,
    tmp_path,
    monkeypatch,
):
    sources = [str(tmp_path / name) for name in ("good.png", "missing.png")]
    Image.new("RGB", (3, 2)).save(sources[0])
    output = tmp_path / "out"
    output.mkdir()
    factory = partial(
        upscale._UpscaleWorker,
        output_dir=str(output),
        model_key="trad:nearest",
        overwrite=False,
        scale_override=2,
    )
    worker = factory(sources)
    job = registry.add(worker, "Upscale", factory)
    worker.start()
    try:
        assert pump_until(lambda: job.settled)
        assert job.state.snapshot().status == "partial"
        assert job.state.failed_paths() == (sources[1],)
        Image.new("RGB", (3, 2)).save(sources[1])
        following = registry.retry(job)
        assert following is not None and pump_until(lambda: following.settled)
        assert following.state.snapshot().status == "succeeded"
        assert sorted(p.name for p in output.iterdir()) == ["good_x2.png", "missing_x2.png"]
    finally:
        assert worker.wait(5000)
        registry.drain()
    failed = upscale._UpscaleWorker(sources, str(output), "realesrgan-x4plus", False)
    monkeypatch.setattr(
        failed, "_run_ai", lambda: (_ for _ in ()).throw(ImportError("model offline"))
    )
    failed.run()
    assert failed.job_state.failed_paths() == tuple(sources)
    assert all(item.error == "model offline" for item in failed.job_state.snapshot().items)


def test_cancel_during_upscale_does_not_save_late_result(qapp, tmp_path, pump_until, monkeypatch):
    source = tmp_path / "photo.png"
    Image.new("RGB", (3, 2)).save(source)
    entered, release = Event(), Event()
    worker = upscale._UpscaleWorker([str(source)], str(tmp_path), "trad:nearest", False)

    def transform(img):
        entered.set()
        release.wait(5)
        return img

    monkeypatch.setattr(worker, "_run_traditional", lambda: worker._upscale_each(2, transform))
    worker.start()
    try:
        assert entered.wait(3)
        worker.job_state.request_cancel()
        release.set()
        assert worker.wait(5000)
        assert worker.job_state.snapshot().status == "cancelled"
        assert list(tmp_path.iterdir()) == [source]
    finally:
        release.set()
        assert worker.wait(5000)


def test_download_is_one_atomic_retry_item_and_cancel_preserves_old_install(
    registry,
    qapp,
    pump_until,
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "plugin"
    root.mkdir()
    (root / "__init__.py").write_bytes(b"prior")
    infos = [
        {"name": "__init__.py", "download_url": "https://example.org/a"},
        {"name": "file.py", "download_url": "https://example.org/b"},
    ]
    monkeypatch.setattr(download, "_get_plugin_dir", lambda: tmp_path)
    calls = []
    blocked = True

    def fetch(req, **_options):
        calls.append(req.full_url)
        if blocked and req.full_url.endswith("/b"):
            raise OSError("offline")
        return BytesIO(b"new")

    monkeypatch.setattr(download, "_https_urlopen", fetch)
    worker = download.DownloadPluginWorker("plugin", infos)
    job = registry.add(
        worker, "Download", partial(download._retry_download, file_infos=tuple(infos))
    )
    worker.start()
    try:
        assert pump_until(lambda: job.settled)
        assert job.state.failed_paths() == ("plugin",)
        assert (root / "__init__.py").read_bytes() == b"prior"
        blocked = False
        following = registry.retry(job)
        assert following is not None and pump_until(lambda: following.settled)
        snap = following.state.snapshot()
        assert snap.status == "succeeded" and snap.current == snap.total == 2
        assert Path(snap.items[0].output) == root
        assert (root / "file.py").read_bytes() == b"new"
        assert len(calls) == 4
    finally:
        assert worker.wait(5000)
        registry.drain()
    cancelled = download.DownloadPluginWorker("plugin", infos)
    cancelled.stop()
    cancelled.run()
    assert cancelled.job_state.snapshot().status == "cancelled"
    assert (root / "__init__.py").read_bytes() == b"new"
    assert not (tmp_path / ".plugin.partial").exists()


def test_empty_download_exception_is_a_failure_with_a_retry_reason(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_get_plugin_dir", lambda: tmp_path)

    def offline(*_args, **_kwargs):
        raise OSError()

    monkeypatch.setattr(download, "_https_urlopen", offline)
    worker = download.DownloadPluginWorker(
        "plugin", [{"name": "__init__.py", "download_url": "https://example.org/a"}]
    )
    errors = []
    worker.error.connect(errors.append)
    worker.run()
    assert errors == ["OSError"]
    assert worker.job_state.snapshot().status == "failed"
    assert worker.job_state.failed_paths() == ("plugin",)
    assert not (tmp_path / "plugin").exists()
