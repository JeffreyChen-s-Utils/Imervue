"""Contract tests for the image sanitizer's helpers, worker and dialog plumbing.

Pins the paths ``test_image_sanitize.py`` / ``test_image_sanitize_dialog.py``
leave open: output-extension and encoder-option choice, collision retry,
upscale dispatch, the worker's upscale preparation and target folders, the
dialog's early returns, progress text and lifecycle, and the public names the
dialog module keeps exporting. Helpers are reached through the module that
owns them (``sys.modules[fn.__module__]``) so patches land where they are read.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest
from PIL import Image

from Imervue.gui import image_sanitize_dialog as mod
from Imervue.gui.image_sanitize_dialog import (
    ImageSanitizeDialog,
    SanitizeSettings,
    UpscaleSpec,
    _SanitizeWorker,
    open_image_sanitize,
)

_LOGGER_NAME = "Imervue.image_sanitize"


def _owner(fn):
    return sys.modules[fn.__module__]


# ---------------------------------------------------------------------------
# Public names the dialog module keeps exporting
# ---------------------------------------------------------------------------

_EXPORTED = (
    "TARGET_RESOLUTIONS", "SanitizeSettings", "UpscaleSpec", "sanitize_image",
    "ImageSanitizeDialog", "open_image_sanitize", "_SanitizeWorker", "_scan_folder",
    "_get_image_date", "_generate_name", "_compute_upscale_params", "_PIL_FORMAT_MAP",
    "_IMAGE_EXTS", "_resolve_output_ext", "_final_dims", "_ai_upscale", "_maybe_upscale",
    "_allocate_output_path", "_save_kwargs_for", "_make_unseeded_rng", "_scramble_lsb",
    "_LSB_SCRAMBLE_RATE", "logger",
)


@pytest.mark.parametrize("name", _EXPORTED)
def test_dialog_module_exports(name):
    assert hasattr(mod, name)


def test_every_logger_uses_the_sanitize_name():
    assert mod.logger.name == _LOGGER_NAME
    assert _owner(mod.sanitize_image).logger.name == _LOGGER_NAME
    assert sys.modules[_SanitizeWorker.__module__].logger.name == _LOGGER_NAME


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("path", "output_ext", "expected"), [
    ("a.PNG", "same", (".png", "PNG")),
    ("a.jpeg", "same", (".jpeg", "JPEG")),
    ("a.tif", "same", (".tif", "TIFF")),
    ("a.gif", "same", (".png", "PNG")),
    ("noext", "same", (".png", "PNG")),
    ("a.png", ".webp", (".webp", "WebP")),
    ("a.png", ".bmp", (".bmp", "BMP")),
    ("a.png", ".xyz", (".xyz", "PNG")),
])
def test_resolve_output_ext(path, output_ext, expected):
    assert mod._resolve_output_ext(path, output_ext) == expected  # noqa: SLF001


@pytest.mark.parametrize(("w", "h", "target", "expected"), [
    (100, 50, 200, (200, 100)),
    (50, 100, 200, (100, 200)),
    (100, 100, 300, (300, 300)),
    (1000, 1, 10, (10, 1)),
    (1, 1000, 10, (1, 10)),
])
def test_final_dims(w, h, target, expected):
    assert mod._final_dims(w, h, target) == expected  # noqa: SLF001


@pytest.mark.parametrize(("fmt", "expected"), [
    ("JPEG", {"format": "JPEG", "quality": 70, "subsampling": 0}),
    ("PNG", {"format": "PNG", "compress_level": 3}),
    ("WebP", {"format": "WebP"}),
    ("TIFF", {"format": "TIFF"}),
])
def test_save_kwargs_for(fmt, expected):
    assert mod._save_kwargs_for(fmt, 70, 3) == expected  # noqa: SLF001


def test_allocate_output_path_retries_until_free(tmp_path, monkeypatch):
    owner = _owner(mod._allocate_output_path)  # noqa: SLF001
    names = iter(["taken.png", "taken.png", "free.png"])
    monkeypatch.setattr(owner, "_generate_name", lambda *_a: next(names))
    (tmp_path / "taken.png").write_bytes(b"")
    out = mod._allocate_output_path(str(tmp_path), datetime(2026, 1, 2), 8, ".png")  # noqa: SLF001
    assert out == os.path.join(str(tmp_path), "free.png")


def test_allocate_output_path_uses_date_rand_len_and_ext(tmp_path):
    out = mod._allocate_output_path(str(tmp_path), datetime(2026, 1, 2), 5, ".bmp")  # noqa: SLF001
    name = os.path.basename(out)
    assert name.startswith("20260102_") and name.endswith(".bmp")
    assert len(name) == len("20260102_") + 5 + len(".bmp")


def _img(size=(10, 5)):
    return Image.new("RGB", size, (10, 20, 30))


def test_maybe_upscale_keeps_image_without_target():
    img = _img()
    assert mod._maybe_upscale(img, UpscaleSpec(target_long_edge=0)) is img  # noqa: SLF001


def test_maybe_upscale_keeps_image_at_or_above_target():
    img = _img()
    spec = UpscaleSpec(target_long_edge=10, trad_resampling=Image.Resampling.NEAREST)
    assert mod._maybe_upscale(img, spec) is img  # noqa: SLF001


def test_maybe_upscale_traditional_wins_over_session(monkeypatch):
    owner = _owner(mod._maybe_upscale)  # noqa: SLF001
    monkeypatch.setattr(owner, "_ai_upscale", lambda *_a: pytest.fail("AI path used"))
    spec = UpscaleSpec(target_long_edge=20, trad_resampling=Image.Resampling.NEAREST,
                       ort_session=object(), ort_scale=2)
    assert mod._maybe_upscale(_img(), spec).size == (20, 10)  # noqa: SLF001


def test_maybe_upscale_session_needs_positive_scale():
    img = _img()
    spec = UpscaleSpec(target_long_edge=20, ort_session=object(), ort_scale=0)
    assert mod._maybe_upscale(img, spec) is img  # noqa: SLF001


def test_maybe_upscale_routes_to_ai_with_final_dims(monkeypatch):
    owner = _owner(mod._maybe_upscale)  # noqa: SLF001
    calls = []
    session, cb = object(), (lambda _d, _t: None)

    def fake_ai(clean, final_w, final_h, ort_session, ort_scale, tile_progress_cb):
        calls.append((final_w, final_h, ort_session, ort_scale, tile_progress_cb))
        return clean

    monkeypatch.setattr(owner, "_ai_upscale", fake_ai)
    spec = UpscaleSpec(target_long_edge=40, ort_session=session, ort_scale=4,
                       tile_progress_cb=cb)
    mod._maybe_upscale(_img(), spec)  # noqa: SLF001
    assert calls == [(40, 20, session, 4, cb)]


def test_scramble_lsb_converts_palette_and_keeps_rgba():
    pal = Image.new("P", (4, 4))
    assert mod._scramble_lsb(pal).mode == "RGB"  # noqa: SLF001
    assert mod._scramble_lsb(Image.new("PA", (4, 4))).mode == "RGBA"  # noqa: SLF001
    assert mod._scramble_lsb(Image.new("LA", (4, 4))).mode == "LA"  # noqa: SLF001


def test_scramble_lsb_reads_the_rng_through_its_owner(monkeypatch):
    import numpy as np
    owner = _owner(mod._scramble_lsb)  # noqa: SLF001
    seen = []

    def rng():
        seen.append(1)
        return np.random.default_rng(1)

    monkeypatch.setattr(owner, "_make_unseeded_rng", rng)
    mod._scramble_lsb(Image.new("L", (3, 3)))  # noqa: SLF001
    assert seen == [1]


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _worker(settings=None, src_root=None, out="out"):
    return _SanitizeWorker([], out, settings or SanitizeSettings(".png"), src_root=src_root)


@pytest.mark.parametrize("settings", [
    SanitizeSettings(".png", target_long_edge=0, model_key="trad:lanczos"),
    SanitizeSettings(".png", target_long_edge=1920, model_key=""),
])
def test_prepare_upscale_without_target_or_model(qapp, settings):
    assert _worker(settings)._prepare_upscale(1) == (None, None, 0)  # noqa: SLF001


@pytest.mark.parametrize(("key", "expected"), [
    ("trad:lanczos", Image.Resampling.LANCZOS),
    ("trad:bicubic", Image.Resampling.BICUBIC),
    ("trad:nearest", Image.Resampling.NEAREST),
    ("trad:unknown", None),
])
def test_prepare_upscale_traditional(qapp, key, expected):
    w = _worker(SanitizeSettings(".png", target_long_edge=1920, model_key=key))
    assert w._prepare_upscale(1) == (expected, None, 0)  # noqa: SLF001


def _fake_ort(providers, sessions):
    def make_session(path, providers):
        sessions.append((path, providers))
        return "SESSION"
    return SimpleNamespace(get_available_providers=lambda: providers,
                           InferenceSession=make_session)


@pytest.mark.parametrize(("available", "expected"), [
    ([], ["CPUExecutionProvider"]),
    (["CPUExecutionProvider"], ["CPUExecutionProvider"]),
    (["DmlExecutionProvider", "CUDAExecutionProvider"],
     ["CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"]),
    (["DmlExecutionProvider"], ["DmlExecutionProvider", "CPUExecutionProvider"]),
])
def test_preferred_ort_providers(available, expected):
    ort = _fake_ort(available, [])
    assert _SanitizeWorker._preferred_ort_providers(ort) == expected  # noqa: SLF001


def test_prepare_upscale_ai_loads_session(qapp, monkeypatch):
    from Imervue.gui import ai_upscale_dialog
    sessions = []
    monkeypatch.setitem(sys.modules, "onnxruntime",
                        _fake_ort(["CUDAExecutionProvider"], sessions))
    monkeypatch.setattr(ai_upscale_dialog, "_download_model", lambda key: f"/m/{key}")
    w = _worker(SanitizeSettings(".png", target_long_edge=1920, model_key="realesrgan-x2plus"))
    progress = []
    w.progress.connect(lambda *a: progress.append(a))
    assert w._prepare_upscale(3) == (None, "SESSION", 2)  # noqa: SLF001
    assert progress == [(0, 3, "Downloading AI model..."), (0, 3, "Loading AI model...")]
    assert sessions == [("/m/realesrgan-x2plus",
                         ["CUDAExecutionProvider", "CPUExecutionProvider"])]


def test_prepare_upscale_ai_failure_is_logged(qapp, monkeypatch, caplog):
    from Imervue.gui import ai_upscale_dialog
    monkeypatch.setitem(sys.modules, "onnxruntime", _fake_ort([], []))

    def boom(_key):
        raise OSError("offline")

    monkeypatch.setattr(ai_upscale_dialog, "_download_model", boom)
    w = _worker(SanitizeSettings(".png", target_long_edge=1920, model_key="realesrgan-x4plus"))
    with caplog.at_level(logging.ERROR, logger=_LOGGER_NAME):
        assert w._prepare_upscale(1) == (None, None, 0)  # noqa: SLF001
    assert "Failed to load AI upscale model" in caplog.text


def test_target_dir_without_root_is_flat(qapp, tmp_path):
    assert _worker(out=str(tmp_path))._target_dir_for(str(tmp_path / "x.png")) == str(tmp_path)  # noqa: SLF001


def test_target_dir_same_folder_is_flat(qapp, tmp_path):
    w = _worker(src_root=str(tmp_path / "src"), out=str(tmp_path / "out"))
    assert w._target_dir_for(str(tmp_path / "src" / "a.png")) == str(tmp_path / "out")  # noqa: SLF001


def test_target_dir_relpath_error_is_flat(qapp, tmp_path, monkeypatch):
    owner = sys.modules[_SanitizeWorker.__module__]

    def bad_relpath(*_a):
        raise ValueError("different drives")

    monkeypatch.setattr(owner.os.path, "relpath", bad_relpath)
    w = _worker(src_root="C:/src", out=str(tmp_path))
    assert w._target_dir_for("D:/src/sub/a.png") == str(tmp_path)  # noqa: SLF001


def test_target_dir_creates_the_mirrored_folder(qapp, tmp_path):
    w = _worker(src_root=str(tmp_path / "src"), out=str(tmp_path / "out"))
    target = w._target_dir_for(str(tmp_path / "src" / "a" / "b" / "x.png"))  # noqa: SLF001
    assert target == os.path.join(str(tmp_path / "out"), os.path.join("a", "b"))
    assert os.path.isdir(target)


def test_run_reports_counts_and_passes_settings(qapp, tmp_path, monkeypatch):
    owner = sys.modules[_SanitizeWorker.__module__]
    calls = []

    def fake_sanitize(path, out_dir, output_ext, **kw):
        if path.endswith("bad"):
            raise OSError("nope")
        calls.append((path, out_dir, output_ext, kw))
        return path

    monkeypatch.setattr(owner, "sanitize_image", fake_sanitize)
    settings = SanitizeSettings(".jpg", rand_len=5, jpeg_quality=70, png_compress=2,
                                target_long_edge=64, model_key="trad:nearest")
    w = _SanitizeWorker(["a.png", "bad", "b.png"], str(tmp_path), settings)
    results = []
    w.result_ready.connect(lambda *a: results.append(a))
    w.run()
    assert results == [(2, 1)]
    _path, out_dir, ext, kw = calls[0]
    assert (out_dir, ext) == (str(tmp_path), ".jpg")
    assert (kw["rand_len"], kw["jpeg_quality"], kw["png_compress"]) == (5, 70, 2)
    assert kw["upscale"] == UpscaleSpec(target_long_edge=64,
                                        trad_resampling=Image.Resampling.NEAREST)


# ---------------------------------------------------------------------------
# Dialog plumbing
# ---------------------------------------------------------------------------

@pytest.fixture
def dialog(qapp, monkeypatch):
    monkeypatch.setattr(_SanitizeWorker, "start", lambda self: None)
    dlg = ImageSanitizeDialog(SimpleNamespace(main_window=None))
    yield dlg
    dlg.deleteLater()


def test_start_without_source_does_nothing(dialog, tmp_path):
    dialog._out_edit.setText(str(tmp_path / "out"))  # noqa: SLF001
    dialog._do_start()  # noqa: SLF001
    dialog._src_edit.setText(str(tmp_path / "missing"))  # noqa: SLF001
    dialog._do_start()  # noqa: SLF001
    assert dialog._worker is None  # noqa: SLF001
    assert not (tmp_path / "out").exists()


def test_start_without_output_does_nothing(dialog, tmp_path):
    dialog._src_edit.setText(str(tmp_path))  # noqa: SLF001
    dialog._out_edit.setText("   ")  # noqa: SLF001
    dialog._do_start()  # noqa: SLF001
    assert dialog._worker is None  # noqa: SLF001
    assert dialog._status_label.text() == ""  # noqa: SLF001


def test_start_with_no_images_reports_it(dialog, tmp_path):
    dialog._src_edit.setText(str(tmp_path))  # noqa: SLF001
    dialog._out_edit.setText(str(tmp_path / "out"))  # noqa: SLF001
    dialog._do_start()  # noqa: SLF001
    assert dialog._status_label.text() == "No supported images found."  # noqa: SLF001
    assert dialog._worker is None  # noqa: SLF001
    assert not (tmp_path / "out").exists()


def _with_one_image(dialog, tmp_path, *, recursive=False):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    Image.new("RGB", (4, 4)).save(src / "sub" / "a.png")
    Image.new("RGB", (4, 4)).save(src / "b.png")
    dialog._src_edit.setText(f"  {src}  ")  # noqa: SLF001
    dialog._out_edit.setText(str(tmp_path / "out"))  # noqa: SLF001
    dialog._recursive_check.setChecked(recursive)  # noqa: SLF001
    return src


def test_start_flat_scan_creates_output_and_launches(dialog, tmp_path):
    src = _with_one_image(dialog, tmp_path)
    dialog._do_start()  # noqa: SLF001
    w = dialog._worker  # noqa: SLF001
    assert w._paths == [str(src / "b.png")]  # noqa: SLF001
    assert w._src_root is None  # noqa: SLF001
    assert w._output_dir == str(tmp_path / "out")  # noqa: SLF001
    assert (tmp_path / "out").is_dir()
    assert not dialog._start_btn.isEnabled()  # noqa: SLF001
    assert not dialog._progress.isHidden()  # noqa: SLF001
    assert dialog._tile_progress.isHidden()  # noqa: SLF001


def test_start_recursive_mirrors_from_the_source_root(dialog, tmp_path):
    src = _with_one_image(dialog, tmp_path, recursive=True)
    dialog._do_start()  # noqa: SLF001
    w = dialog._worker  # noqa: SLF001
    assert len(w._paths) == 2  # noqa: SLF001
    assert w._src_root == str(src)  # noqa: SLF001


def test_start_with_upscale_shows_tile_progress(dialog, tmp_path):
    _with_one_image(dialog, tmp_path)
    dialog._res_combo.setCurrentIndex(1)  # noqa: SLF001
    dialog._model_combo.setCurrentIndex(dialog._model_combo.findData("trad:bicubic"))  # noqa: SLF001
    dialog._tile_progress.setMaximum(10)  # noqa: SLF001
    dialog._tile_progress.setValue(7)  # noqa: SLF001
    dialog._do_start()  # noqa: SLF001
    assert not dialog._tile_progress.isHidden()  # noqa: SLF001
    assert dialog._tile_progress.value() == 0  # noqa: SLF001


def test_dependency_install_error_keeps_start_enabled(dialog, tmp_path, monkeypatch, caplog):
    from Imervue.plugin import pip_installer

    def boom(*_a):
        raise RuntimeError("pip broke")

    monkeypatch.setattr(pip_installer, "ensure_dependencies", boom)
    _with_one_image(dialog, tmp_path)
    dialog._res_combo.setCurrentIndex(1)  # noqa: SLF001
    dialog._model_combo.setCurrentIndex(dialog._model_combo.findData("realesrgan-x4plus"))  # noqa: SLF001
    with caplog.at_level(logging.ERROR, logger=_LOGGER_NAME):
        dialog._do_start()  # noqa: SLF001
    assert "ensure_dependencies failed" in caplog.text
    assert dialog._start_btn.isEnabled()  # noqa: SLF001
    assert dialog._worker is None  # noqa: SLF001
    assert dialog._status_label.text() == "Installing dependencies..."  # noqa: SLF001


def test_worker_signals_drive_the_dialog(dialog, tmp_path):
    _with_one_image(dialog, tmp_path)
    dialog._do_start()  # noqa: SLF001
    w = dialog._worker  # noqa: SLF001
    w.progress.emit(2, 5, "x.png")
    assert (dialog._progress.maximum(), dialog._progress.value()) == (5, 2)  # noqa: SLF001
    assert dialog._status_label.text() == "Sanitizing: x.png"  # noqa: SLF001
    w.tile_progress.emit(3, 9)
    assert (dialog._tile_progress.maximum(), dialog._tile_progress.value()) == (9, 3)  # noqa: SLF001
    w.result_ready.emit(4, 1)
    assert dialog._status_label.text() == "Done — 4 sanitized, 1 failed."  # noqa: SLF001
    w.finished.emit()
    assert dialog._worker is None  # noqa: SLF001
    assert dialog._start_btn.isEnabled()  # noqa: SLF001
    assert dialog._progress.isHidden() and dialog._tile_progress.isHidden()  # noqa: SLF001


@pytest.mark.parametrize(("gui", "expect_folder"), [
    (SimpleNamespace(main_window=None), False),
    (SimpleNamespace(main_window=None, model=SimpleNamespace()), False),
    (SimpleNamespace(main_window=None, model=SimpleNamespace(folder_path="X")), True),
])
def test_open_image_sanitize_passes_the_model_folder(qapp, monkeypatch, gui, expect_folder):
    seen = []

    class FakeDialog:
        def __init__(self, main_gui, folder):
            seen.append((main_gui, folder))

        def exec(self):
            seen.append("exec")

    monkeypatch.setattr(mod, "ImageSanitizeDialog", FakeDialog)
    open_image_sanitize(gui)
    assert seen == [(gui, "X" if expect_folder else None), "exec"]
