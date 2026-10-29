"""Contract tests for the AI upscale dialog's run lifecycle, worker helpers and entry points.

Pins what ``tests/test_ai_upscale_dialog.py`` (layout) and ``tests/test_ai_upscale.py``
(registry, tiling, worker runs) leave open: how ``_do_start`` validates the options,
launches the worker directly or behind the dependency offer and registers its retry
factory; the progress / finish slots and the viewer reload after an overwrite; the
worker's output naming and provider order; and the three ``open_*`` entry points.
Patches go to the module that owns the code under test, found at run time, so the
contracts hold wherever a function lives. No worker thread is started and no model
is downloaded.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from Imervue.gui import ai_upscale_dialog as mod
from Imervue.gui.ai_upscale_dialog import (
    REQUIRED_PACKAGES,
    TRADITIONAL_METHODS,
    UPSCALE_MODELS,
    AIUpscaleDialog,
    _UpscaleWorker,
)

_TRAD_KEY = next(iter(TRADITIONAL_METHODS))
_AI_KEY = "realesrgan-x2plus"


def _owner(func):
    return sys.modules[func.__module__]


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


class _Registry:
    def __init__(self):
        self.added = []

    def add(self, worker, title, factory):
        self.added.append((worker, title, factory))


class _Toast:
    def __init__(self):
        self.calls = []

    def info(self, msg):
        self.calls.append(("info", msg))

    def success(self, msg):
        self.calls.append(("success", msg))


@pytest.fixture
def registry(monkeypatch):
    reg = _Registry()
    monkeypatch.setattr(_owner(AIUpscaleDialog._do_start), "job_registry", lambda: reg)
    monkeypatch.setattr(_UpscaleWorker, "start", lambda self: None)
    return reg


@pytest.fixture
def make_dialog(qapp):
    made = []

    def _make(**kwargs):
        dlg = AIUpscaleDialog(SimpleNamespace(main_window=None), **kwargs)
        made.append(dlg)
        return dlg

    yield _make
    for dlg in made:
        if dlg._worker is not None:  # noqa: SLF001
            dlg._worker.deleteLater()  # noqa: SLF001
            dlg._worker = None  # noqa: SLF001
        dlg.deleteLater()


def _select(dlg, key):
    combo = dlg._model_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(key))


# ---------------------------------------------------------------------------
# _do_start validation
# ---------------------------------------------------------------------------

def test_start_without_paths_does_nothing(make_dialog, registry):
    dlg = make_dialog()
    dlg._do_start()  # noqa: SLF001
    assert registry.added == []
    assert dlg._worker is None  # noqa: SLF001
    assert dlg._model_combo.isEnabled()  # noqa: SLF001


def test_start_without_output_folder_returns_before_locking(make_dialog, registry):
    dlg = make_dialog(paths=["C:/pics/a.png"])
    dlg._out_edit.setText("   ")  # noqa: SLF001
    dlg._do_start()  # noqa: SLF001
    assert registry.added == []
    assert dlg._start_btn.isEnabled()  # noqa: SLF001
    assert dlg._model_combo.isEnabled()  # noqa: SLF001
    assert dlg._overwrite_check.isEnabled()  # noqa: SLF001


def test_traditional_start_creates_the_folder_and_launches(make_dialog, registry, tmp_path):
    out = tmp_path / "made" / "deep"
    dlg = make_dialog(paths=["C:/pics/a.png", "C:/pics/b.png", "C:/pics/a.png"])
    _select(dlg, _TRAD_KEY)
    dlg._scale_spin.setValue(5)  # noqa: SLF001
    dlg._out_edit.setText(f"  {out}  ")  # noqa: SLF001
    dlg._status_label.setText("stale")  # noqa: SLF001
    dlg._do_start()  # noqa: SLF001
    assert out.is_dir()
    assert not dlg._start_btn.isEnabled()  # noqa: SLF001
    assert not dlg._model_combo.isEnabled()  # noqa: SLF001
    assert not dlg._overwrite_check.isEnabled()  # noqa: SLF001
    assert dlg._progress.maximum() == 3 and dlg._progress.value() == 0  # noqa: SLF001
    assert not dlg._progress.isHidden()  # noqa: SLF001
    assert dlg._tile_progress.isHidden()  # noqa: SLF001
    assert dlg._status_label.text() == ""  # noqa: SLF001
    [(worker, title, factory)] = registry.added
    assert worker is dlg._worker and isinstance(worker, _UpscaleWorker)  # noqa: SLF001
    assert title == dlg.windowTitle() == "AI Image Upscale"
    assert worker._paths == ["C:/pics/a.png", "C:/pics/b.png"]  # noqa: SLF001
    assert worker._output_dir == str(out)  # noqa: SLF001
    assert (worker._model_key, worker._overwrite, worker._scale_override) == (  # noqa: SLF001
        _TRAD_KEY, False, 5)
    assert factory.func is _UpscaleWorker and factory.args == ()
    assert factory.keywords == {"output_dir": str(out), "model_key": _TRAD_KEY,
                                "overwrite": False, "scale_override": 5}


def test_overwrite_start_passes_an_empty_output_dir(make_dialog, registry):
    dlg = make_dialog(paths=["C:/pics/a.png"])
    _select(dlg, _TRAD_KEY)
    dlg._out_edit.setText("")  # noqa: SLF001
    dlg._overwrite_check.setChecked(True)  # noqa: SLF001
    dlg._do_start()  # noqa: SLF001
    [(worker, _title, factory)] = registry.added
    assert worker._output_dir == "" and worker._overwrite is True  # noqa: SLF001
    assert factory.keywords["output_dir"] == ""


def test_worker_signals_reach_the_dialog(make_dialog, registry, tmp_path):
    dlg = make_dialog(paths=["C:/pics/a.png", "C:/pics/b.png"])
    _select(dlg, _TRAD_KEY)
    dlg._out_edit.setText(str(tmp_path))  # noqa: SLF001
    dlg._do_start()  # noqa: SLF001
    worker = dlg._worker  # noqa: SLF001
    worker.progress.emit(1, 2, "b.png")
    assert dlg._progress.value() == 1  # noqa: SLF001
    assert dlg._status_label.text() == "2/2  b.png"  # noqa: SLF001
    worker.tile_progress.emit(3, 9)
    assert (dlg._tile_progress.maximum(), dlg._tile_progress.value()) == (9, 3)  # noqa: SLF001
    worker.result_ready.emit(2, 0)
    assert dlg._status_label.text() == "Done — 2 upscaled, 0 failed."  # noqa: SLF001
    worker.finished.emit()
    assert dlg._worker is None  # noqa: SLF001
    worker.deleteLater()


def test_ai_start_goes_through_the_dependency_offer(make_dialog, registry, monkeypatch, tmp_path):
    offers = []
    monkeypatch.setattr(_owner(AIUpscaleDialog._do_start), "ensure_dependencies",
                        lambda parent, packages, cb: offers.append((parent, packages, cb)))
    dlg = make_dialog(paths=["C:/pics/a.png"])
    _select(dlg, _AI_KEY)
    dlg._out_edit.setText(str(tmp_path))  # noqa: SLF001
    dlg._do_start()  # noqa: SLF001
    assert dlg._status_label.text() == "Installing dependencies..."  # noqa: SLF001
    assert registry.added == []
    [(parent, packages, launch)] = offers
    assert parent is None and packages is REQUIRED_PACKAGES
    launch()
    [(worker, _title, factory)] = registry.added
    assert (worker._model_key, worker._scale_override) == (_AI_KEY, 0)  # noqa: SLF001
    assert factory.keywords["scale_override"] == 0
    assert not dlg._tile_progress.isHidden()  # noqa: SLF001
    assert dlg._status_label.text() == ""  # noqa: SLF001


def test_dependency_offer_failure_reenables_start_only(make_dialog, registry, monkeypatch,
                                                       tmp_path, caplog):
    def _boom(*_a):
        raise RuntimeError("pip broke")

    monkeypatch.setattr(_owner(AIUpscaleDialog._do_start), "ensure_dependencies", _boom)
    dlg = make_dialog(paths=["C:/pics/a.png"])
    _select(dlg, _AI_KEY)
    dlg._out_edit.setText(str(tmp_path))  # noqa: SLF001
    with caplog.at_level("ERROR", logger="Imervue.ai_upscale"):
        dlg._do_start()  # noqa: SLF001
    assert "ensure_dependencies raised" in caplog.text
    assert dlg._start_btn.isEnabled()  # noqa: SLF001
    assert not dlg._model_combo.isEnabled()  # noqa: SLF001
    assert not dlg._overwrite_check.isEnabled()  # noqa: SLF001
    assert registry.added == []


# ---------------------------------------------------------------------------
# _on_finished
# ---------------------------------------------------------------------------

def _finish_gui(**extra):
    return SimpleNamespace(main_window=SimpleNamespace(toast=_Toast()), **extra)


@pytest.mark.parametrize(("failed", "kind"), [(0, "success"), (1, "info")])
def test_finish_resets_controls_and_toasts(make_dialog, failed, kind):
    dlg = make_dialog(paths=["a.png", "b.png"])
    dlg._gui = gui = _finish_gui()  # noqa: SLF001
    for widget in (dlg._start_btn, dlg._model_combo, dlg._overwrite_check):  # noqa: SLF001
        widget.setEnabled(False)
    dlg._tile_progress.setVisible(True)  # noqa: SLF001
    dlg._progress.setMaximum(2)  # noqa: SLF001
    dlg._on_finished(2 - failed, failed)  # noqa: SLF001
    msg = f"Done — {2 - failed} upscaled, {failed} failed."
    assert dlg._status_label.text() == msg  # noqa: SLF001
    assert dlg._progress.value() == 2  # noqa: SLF001
    assert dlg._tile_progress.isHidden()  # noqa: SLF001
    assert all(w.isEnabled() for w in (dlg._start_btn, dlg._model_combo,  # noqa: SLF001
                                       dlg._overwrite_check))  # noqa: SLF001
    assert gui.main_window.toast.calls == [(kind, msg)]


def test_finish_without_a_toast_still_reports(make_dialog):
    dlg = make_dialog(paths=["a.png"])
    dlg._gui = SimpleNamespace(main_window=SimpleNamespace())  # noqa: SLF001
    dlg._on_finished(1, 0)  # noqa: SLF001
    assert dlg._status_label.text() == "Done — 1 upscaled, 0 failed."  # noqa: SLF001


def _overwrite_dialog(make_dialog, gui):
    dlg = make_dialog(paths=["a.png"])
    dlg._gui = gui  # noqa: SLF001
    dlg._overwrite_check.setChecked(True)  # noqa: SLF001
    return dlg


def test_finish_after_overwrite_reloads_the_tile_grid(make_dialog):
    loads = []
    gui = _finish_gui(tile_grid_mode=True, deep_zoom=None,
                      model=SimpleNamespace(images=("a.png", "b.png")),
                      load_tile_grid_async=loads.append)
    _overwrite_dialog(make_dialog, gui)._on_finished(1, 0)  # noqa: SLF001
    assert loads == [["a.png", "b.png"]]


@pytest.mark.parametrize(("index", "expected"), [
    (1, ["clear", "b.png"]), (2, []), (-1, []),
])
def test_finish_after_overwrite_reloads_deep_zoom(make_dialog, index, expected):
    calls = []
    gui = _finish_gui(tile_grid_mode=False, deep_zoom=object(), current_index=index,
                      model=SimpleNamespace(images=["a.png", "b.png"]),
                      _clear_deep_zoom=lambda: calls.append("clear"),
                      load_deep_zoom_image=calls.append)
    _overwrite_dialog(make_dialog, gui)._on_finished(1, 0)  # noqa: SLF001
    assert calls == expected


def test_finish_after_overwrite_with_no_images_skips_reload(make_dialog):
    calls = []
    gui = _finish_gui(tile_grid_mode=False, deep_zoom=object(), current_index=0,
                      model=SimpleNamespace(images=[]),
                      _clear_deep_zoom=lambda: calls.append("clear"),
                      load_deep_zoom_image=calls.append)
    _overwrite_dialog(make_dialog, gui)._on_finished(1, 0)  # noqa: SLF001
    assert calls == []


def test_finish_reload_failure_is_logged_not_raised(make_dialog, caplog):
    gui = _finish_gui()  # no tile_grid_mode attribute: the reload raises
    with caplog.at_level("WARNING", logger="Imervue.ai_upscale"):
        _overwrite_dialog(make_dialog, gui)._on_finished(1, 0)  # noqa: SLF001
    assert "reload the viewer after upscaling" in caplog.text


def test_finish_without_overwrite_leaves_the_viewer(make_dialog):
    gui = _finish_gui()  # a reload would raise on the missing attributes
    dlg = make_dialog(paths=["a.png"])
    dlg._gui = gui  # noqa: SLF001
    dlg._on_finished(1, 0)  # noqa: SLF001
    assert gui.main_window.toast.calls == [("success", "Done — 1 upscaled, 0 failed.")]


def test_cleanup_drops_the_worker(make_dialog):
    dlg = make_dialog()
    dlg._worker = object()  # noqa: SLF001
    dlg._cleanup()  # noqa: SLF001
    assert dlg._worker is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# Worker helpers and the AI path
# ---------------------------------------------------------------------------

def test_output_path_naming(tmp_path):
    src = str(tmp_path / "shot.jpg")
    assert _UpscaleWorker._output_path(src, "ignored", 4, True) == src  # noqa: SLF001
    out = tmp_path / "out"
    out.mkdir()
    first = _UpscaleWorker._output_path(src, str(out), 4, False)  # noqa: SLF001
    assert first == str(out / "shot_x4.jpg")
    (out / "shot_x4.jpg").write_bytes(b"")
    (out / "shot_x4_1.jpg").write_bytes(b"")
    assert _UpscaleWorker._output_path(src, str(out), 4, False) == str(  # noqa: SLF001
        out / "shot_x4_2.jpg")
    assert _UpscaleWorker._output_path(  # noqa: SLF001
        str(tmp_path / "photo.cr2"), str(out), 2, False) == str(out / "photo_x2.png")


def test_skip_unwritable_only_in_overwrite_mode(qapp, tmp_path):
    frames = [Image.new("RGB", (4, 4), c) for c in ("red", "blue")]
    gif = tmp_path / "anim.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:])
    png = tmp_path / "still.png"
    frames[0].save(png)
    keep = _UpscaleWorker([str(gif)], str(tmp_path), _TRAD_KEY, False)
    over = _UpscaleWorker([str(gif)], str(tmp_path), _TRAD_KEY, True)
    try:
        assert keep._skip_unwritable(str(gif)) is False  # noqa: SLF001
        assert over._skip_unwritable(str(gif)) is True  # noqa: SLF001
        assert over._skip_unwritable(str(png)) is False  # noqa: SLF001
    finally:
        keep.deleteLater()
        over.deleteLater()


def test_traditional_scale_defaults_to_two(qapp, tmp_path):
    src = tmp_path / "a.png"
    Image.new("RGB", (3, 5)).save(src)
    out = tmp_path / "out"
    out.mkdir()
    worker = _UpscaleWorker([str(src)], str(out), _TRAD_KEY, False)
    results = []
    worker.result_ready.connect(lambda ok, bad: results.append((ok, bad)))
    try:
        worker.run()
    finally:
        worker.deleteLater()
    assert results == [(1, 0)]
    with Image.open(out / "a_x2.png") as done:
        assert done.size == (6, 10)


@pytest.mark.parametrize(("available", "expected"), [
    ([], ["CPUExecutionProvider"]),
    (["CPUExecutionProvider"], ["CPUExecutionProvider"]),
    (["DmlExecutionProvider", "CUDAExecutionProvider", "X"],
     ["CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"]),
])
def test_preferred_providers(available, expected):
    assert mod._preferred_providers(available) == expected  # noqa: SLF001


def test_ai_upscale_converts_palette_images_to_rgb(monkeypatch):
    seen = []

    def _fake(session, arr, scale, progress_cb=None):
        seen.append((session, arr.shape, scale, progress_cb))
        return np.repeat(np.repeat(arr, scale, axis=0), scale, axis=1)

    monkeypatch.setattr(_owner(mod._ai_upscale), "_upscale_image", _fake)  # noqa: SLF001
    cb = object()
    out = mod._ai_upscale("S", Image.new("P", (3, 2)), 2, cb)  # noqa: SLF001
    assert out.mode == "RGB" and out.size == (6, 4)
    assert seen == [("S", (2, 3, 3), 2, cb)]


def test_ai_upscale_resizes_alpha_alongside(monkeypatch):
    monkeypatch.setattr(_owner(mod._ai_upscale), "_upscale_image",  # noqa: SLF001
                        lambda s, arr, scale, progress_cb=None:
                        np.repeat(np.repeat(arr, scale, axis=0), scale, axis=1))
    img = Image.new("RGBA", (2, 2), (10, 20, 30, 77))
    out = mod._ai_upscale(None, img, 3, None)  # noqa: SLF001
    assert out.mode == "RGBA" and out.size == (6, 6)
    assert out.getpixel((5, 5)) == (10, 20, 30, 77)


def test_every_ai_model_resolves_its_scale():
    assert {k: v["scale"] for k, v in UPSCALE_MODELS.items()} == {
        "realesrgan-x4plus": 4, "realesrgan-x4plus-anime": 4, "realesrgan-x2plus": 2}


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

@pytest.fixture
def opened(monkeypatch):
    shown = []

    def _exec(self):
        shown.append(self)
        return 0

    monkeypatch.setattr(AIUpscaleDialog, "exec", _exec)
    yield shown
    for dlg in shown:
        dlg.deleteLater()


def test_open_prefills_the_current_folder(qapp, opened, image_folder):
    mod.open_ai_upscale(SimpleNamespace(main_window=None,
                                        model=SimpleNamespace(folder_path=str(image_folder))))
    [dlg] = opened
    assert dlg._src_edit.text() == str(image_folder)  # noqa: SLF001
    assert dlg._paths  # noqa: SLF001


def test_open_without_a_model_starts_empty(qapp, opened):
    mod.open_ai_upscale(SimpleNamespace(main_window=None))
    [dlg] = opened
    assert dlg._src_edit.text() == "" and dlg._paths == []  # noqa: SLF001


def test_open_single_presets_one_path(qapp, opened):
    mod.open_ai_upscale_single(SimpleNamespace(main_window=None), "C:/pics/a.png")
    [dlg] = opened
    assert dlg._paths == ["C:/pics/a.png"]  # noqa: SLF001
    assert dlg._src_row_widget.isHidden()  # noqa: SLF001


def test_open_batch_uses_the_selection(qapp, opened):
    mod.open_ai_upscale_batch(SimpleNamespace(main_window=None, selected_tiles={"C:/x.png"}))
    [dlg] = opened
    assert dlg._paths == ["C:/x.png"]  # noqa: SLF001


@pytest.mark.parametrize("tiles", [None, set()])
def test_open_batch_without_a_selection_opens_nothing(qapp, opened, tiles):
    mod.open_ai_upscale_batch(SimpleNamespace(main_window=None, selected_tiles=tiles))
    assert opened == []
