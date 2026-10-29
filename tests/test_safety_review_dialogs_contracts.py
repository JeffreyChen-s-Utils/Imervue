"""Contract tests for the safety_review settings / scan / batch dialogs.

Pins the behaviour of ``safety_review._dialogs`` that the ScanAllDialog smoke
tests leave open: the dependency gate, the time and summary formatting, the
shared settings rows, the worker-host teardown, and the run / finish cycle of
all three dialogs. Every dialog here is a plain ``QDialog`` (no
``QOpenGLWidget``), so no headless-CI skip marker is needed. Workers are
never started: their ``start`` is patched to a no-op.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtWidgets import QDialog, QFileDialog

from safety_review import _constants, _workers
from safety_review import _dialogs
from safety_review._dialogs import (
    BatchSafetyReviewDialog,
    SafetyReviewDialog,
    ScanAllDialog,
    _WorkerHostMixin,
    _build_mode_row,
    _ensure_deps,
    _fmt_time,
    _format_result_message,
    _reload_grid_or_deepzoom,
    _selected_categories,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_everywhere(monkeypatch, name, value):
    """Replace *name* in every loaded safety_review module that binds it."""
    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith("safety_review") and hasattr(mod, name):
            monkeypatch.setattr(mod, name, value)


class _Toast:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def info(self, msg):
        self.calls.append(("info", msg))

    def success(self, msg):
        self.calls.append(("success", msg))


def _gui_with_toast():
    toast = _Toast()
    return SimpleNamespace(main_window=SimpleNamespace(toast=toast)), toast


def _png(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), (90, 120, 160)).save(path, format="PNG")
    return str(path)


@pytest.fixture
def no_start(monkeypatch):
    """Keep every worker class from spawning a thread."""
    for cls in (_workers._BatchWorker, _workers._SingleWorker,
                _workers._SubprocessBatchWorker, _workers._SubprocessSingleWorker):
        monkeypatch.setattr(cls, "start", lambda self: None)


@pytest.fixture
def deps(monkeypatch):
    """Record ``_ensure_deps`` calls and run the ready callback immediately."""
    calls = []

    def _fake(parent, on_ready, mode=_constants.MODE_REAL, precise=False):
        calls.append({"parent": parent, "mode": mode, "precise": precise})
        on_ready()

    _patch_everywhere(monkeypatch, "_ensure_deps", _fake)
    return calls


@pytest.fixture
def reloads(monkeypatch):
    calls = []
    _patch_everywhere(monkeypatch, "_reload_grid_or_deepzoom", calls.append)
    return calls


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("mode", "precise", "expected"), [
    (_constants.MODE_AUTO, False, list(_constants.REQUIRED_PACKAGES_AUTO)),
    (_constants.MODE_ANIME, False, list(_constants.REQUIRED_PACKAGES_ANIME)),
    (_constants.MODE_REAL, False, list(_constants.REQUIRED_PACKAGES_REAL)),
    ("unknown", False, list(_constants.REQUIRED_PACKAGES_REAL)),
])
def test_ensure_deps_picks_packages_per_mode(monkeypatch, mode, precise, expected):
    seen = []
    _patch_everywhere(monkeypatch, "ensure_dependencies",
                      lambda parent, pkgs, cb: seen.append((parent, pkgs, cb)))
    marker = object()
    _ensure_deps("parent", marker, mode=mode, precise=precise)
    assert seen == [("parent", expected, marker)]


def test_ensure_deps_precise_appends_missing_packages_once(monkeypatch):
    seen = []
    _patch_everywhere(monkeypatch, "ensure_dependencies",
                      lambda parent, pkgs, cb: seen.append(pkgs))
    _ensure_deps(None, None, mode=_constants.MODE_REAL, precise=True)
    pkgs = seen[0]
    base = list(_constants.REQUIRED_PACKAGES_REAL)
    assert pkgs[:len(base)] == base
    for pkg in _constants.REQUIRED_PACKAGES_PRECISE:
        assert pkgs.count(pkg) == 1


def test_ensure_deps_default_mode_is_real(monkeypatch):
    seen = []
    _patch_everywhere(monkeypatch, "ensure_dependencies",
                      lambda parent, pkgs, cb: seen.append(pkgs))
    _ensure_deps(None, None)
    assert seen == [list(_constants.REQUIRED_PACKAGES_REAL)]


def test_ensure_deps_logs_and_swallows_installer_error(monkeypatch, caplog):
    def _boom(parent, pkgs, cb):
        raise RuntimeError("pip exploded")

    _patch_everywhere(monkeypatch, "ensure_dependencies", _boom)
    with caplog.at_level("ERROR", logger="Imervue.plugin.safety_review"):
        _ensure_deps(None, None)
    assert "ensure_dependencies raised" in caplog.text


@pytest.mark.parametrize(("seconds", "text"), [
    (0, "0s"), (59.9, "59s"), (60, "1m 00s"), (61, "1m 01s"),
    (3599, "59m 59s"), (3600, "1h 00m 00s"), (3661, "1h 01m 01s"),
])
def test_fmt_time_boundaries(seconds, text):
    assert _fmt_time(seconds) == text


def test_selected_categories_returns_only_checked(qapp):
    checks = {
        "a": SimpleNamespace(isChecked=lambda: True),
        "b": SimpleNamespace(isChecked=lambda: False),
    }
    assert _selected_categories(checks) == frozenset({"a"})
    assert _selected_categories({}) == frozenset()


def test_format_result_message_with_and_without_regions():
    assert _format_result_message({}, 3, 1, 5) == (
        "Done — 3/4 images processed, 5 region(s) mosaiced, 1 failed.")
    assert _format_result_message({}, 3, 1, 0).startswith("Done — 3/4")
    assert _format_result_message({}, 2, 1, -1) == "Processed 2/3 image(s)"


class _FakeGui:
    def __init__(self, *, tile=False, deep=False, images=(), index=0, fail=False):
        self.tile_grid_mode = tile
        self.deep_zoom = deep
        self.model = SimpleNamespace(images=list(images))
        self.current_index = index
        self._fail = fail
        self.calls: list = []

    def load_tile_grid_async(self, images):
        if self._fail:
            raise RuntimeError("viewer gone")
        self.calls.append(("grid", images))

    def _clear_deep_zoom(self):
        self.calls.append(("clear",))

    def load_deep_zoom_image(self, path):
        self.calls.append(("deep", path))


def test_reload_prefers_the_tile_grid():
    gui = _FakeGui(tile=True, deep=True, images=["a", "b"])
    _reload_grid_or_deepzoom(gui)
    assert gui.calls == [("grid", ["a", "b"])]


def test_reload_deep_zoom_reloads_current_image():
    gui = _FakeGui(deep=True, images=["a", "b"], index=1)
    _reload_grid_or_deepzoom(gui)
    assert gui.calls == [("clear",), ("deep", "b")]


@pytest.mark.parametrize(("images", "index"), [([], 0), (["a"], 1), (["a"], -1)])
def test_reload_deep_zoom_skips_out_of_range(images, index):
    gui = _FakeGui(deep=True, images=images, index=index)
    _reload_grid_or_deepzoom(gui)
    assert gui.calls == []


def test_reload_neither_mode_does_nothing():
    gui = _FakeGui(images=["a"])
    _reload_grid_or_deepzoom(gui)
    assert gui.calls == []


def test_reload_failure_is_logged_not_raised(caplog):
    gui = _FakeGui(tile=True, fail=True)
    with caplog.at_level("DEBUG", logger="Imervue.plugin.safety_review"):
        _reload_grid_or_deepzoom(gui)
    assert "Viewer reload failed" in caplog.text


# ---------------------------------------------------------------------------
# Shared settings rows
# ---------------------------------------------------------------------------

def _mode_row(qapp):
    from PySide6.QtWidgets import QVBoxLayout, QWidget
    host = QWidget()
    layout = QVBoxLayout(host)
    return host, _build_mode_row(layout, {})


def test_build_mode_row_defaults(qapp):
    host, (mode, conf, expand, style, cats, shape) = _mode_row(qapp)
    assert [mode.itemData(i) for i in range(mode.count())] == [
        _constants.MODE_AUTO, _constants.MODE_REAL, _constants.MODE_ANIME]
    assert [style.itemData(i) for i in range(style.count())] == [
        _constants.STYLE_MOSAIC, _constants.STYLE_BLUR, _constants.STYLE_BLACK]
    assert [shape.itemData(i) for i in range(shape.count())] == [
        _constants.SHAPE_ELLIPSE, _constants.SHAPE_RECT, _constants.SHAPE_PRECISE]
    defaults = _constants._MODE_DEFAULTS[_constants.MODE_AUTO]
    assert conf.value() == pytest.approx(defaults["confidence"])
    assert expand.value() == defaults["expand_pct"]
    assert expand.suffix() == "%"
    assert list(cats) == list(_constants.ALL_CATEGORIES)
    for cat, cb in cats.items():
        assert cb.isChecked() is (cat in _constants.DEFAULT_CATEGORIES)
    host.deleteLater()


def test_mode_change_applies_defaults_and_gates_sexual_act(qapp):
    host, (mode, conf, expand, _style, cats, _shape) = _mode_row(qapp)
    sexual = cats[_constants.CAT_SEXUAL_ACT]
    sexual.setChecked(True)
    mode.setCurrentIndex(mode.findData(_constants.MODE_REAL))
    real = _constants._MODE_DEFAULTS[_constants.MODE_REAL]
    assert conf.value() == pytest.approx(real["confidence"])
    assert expand.value() == real["expand_pct"]
    assert sexual.isEnabled() is False
    assert sexual.isChecked() is False
    mode.setCurrentIndex(mode.findData(_constants.MODE_ANIME))
    anime = _constants._MODE_DEFAULTS[_constants.MODE_ANIME]
    assert conf.value() == pytest.approx(anime["confidence"])
    assert sexual.isEnabled() is True
    host.deleteLater()


@pytest.mark.parametrize(("available", "fragment"), [
    (True, "real pixel-level segmentation is available"),
    (False, "fall back to an ellipse"),
])
def test_precise_shape_shows_backend_hint(qapp, monkeypatch, available, fragment):
    from PySide6.QtWidgets import QLabel
    from safety_review import _detection
    monkeypatch.setattr(_detection, "_precise_backend_available", lambda: available)
    host, (*_rest, shape) = _mode_row(qapp)
    hints = [w for w in host.findChildren(QLabel) if w.wordWrap()]
    assert len(hints) == 1
    hint = hints[0]
    assert hint.isVisibleTo(host) is False
    shape.setCurrentIndex(shape.findData(_constants.SHAPE_PRECISE))
    assert hint.isVisibleTo(host) is True
    assert fragment in hint.text()
    shape.setCurrentIndex(shape.findData(_constants.SHAPE_RECT))
    assert hint.isVisibleTo(host) is False
    host.deleteLater()


# ---------------------------------------------------------------------------
# Worker host mixin
# ---------------------------------------------------------------------------

def _host():
    label = SimpleNamespace(text=None)
    label.setText = lambda t: setattr(label, "text", t)
    return SimpleNamespace(_time_label=label, _lang={}), label


def test_render_time_needs_elapsed_and_eta():
    host, label = _host()
    _WorkerHostMixin._render_time(host, 3, (1.0,))
    assert label.text is None


def test_render_time_formats_elapsed_eta_and_speed():
    host, label = _host()
    _WorkerHostMixin._render_time(host, 4, (8.0, 65.0))
    assert label.text == "Elapsed: 8s    ETA: 1m 05s    (~2.0s / image)"


def test_render_time_first_image_has_unknown_eta():
    host, label = _host()
    _WorkerHostMixin._render_time(host, 0, (3.0, 99.0))
    assert label.text == "Elapsed: 3s    ETA: ...    (~3.0s / image)"


def test_cleanup_drops_the_worker():
    host = SimpleNamespace(_worker=object())
    _WorkerHostMixin._cleanup(host)
    assert host._worker is None


def test_reject_and_close_stop_the_worker(qapp, monkeypatch):
    stops = []
    monkeypatch.setattr(_WorkerHostMixin, "_stop_worker",
                        lambda self: stops.append(type(self).__name__))
    dlg = BatchSafetyReviewDialog(SimpleNamespace(main_window=None), [])
    dlg.reject()
    assert dlg.result() == QDialog.DialogCode.Rejected
    dlg.close()
    assert stops == ["BatchSafetyReviewDialog", "BatchSafetyReviewDialog"]
    dlg.deleteLater()


# ---------------------------------------------------------------------------
# ScanAllDialog
# ---------------------------------------------------------------------------

def _scan(paths=None, frozen=None):
    return ScanAllDialog(SimpleNamespace(main_window=None), initial_paths=paths,
                         get_frozen_env=frozen)


def test_scan_initial_paths_fill_folder_and_count(qapp, tmp_path):
    img = _png(tmp_path / "a.png")
    dlg = _scan([img])
    assert dlg._folder_edit.text() == str(tmp_path)
    assert dlg._start_btn.isEnabled() is True
    assert "1" in dlg._count_label.text()
    assert dlg.minimumWidth() == 500
    dlg.deleteLater()


def test_scan_without_paths_disables_start_only_after_count(qapp):
    dlg = _scan()
    assert dlg._folder_edit.text() == ""
    dlg._update_count()
    assert dlg._start_btn.isEnabled() is False
    dlg.deleteLater()


def test_scan_browse_folder_scans_and_seeds_output(qapp, tmp_path, monkeypatch):
    _png(tmp_path / "a.png")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: str(tmp_path)))
    dlg = _scan()
    dlg._browse_folder()
    assert dlg._folder_edit.text() == str(tmp_path)
    assert len(dlg._paths) == 1
    assert dlg._out_dir_edit.text() == str(tmp_path)
    dlg._out_dir_edit.setText("kept")
    dlg._browse_folder()
    assert dlg._out_dir_edit.text() == "kept"
    dlg.deleteLater()


def test_scan_browse_cancelled_changes_nothing(qapp, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: ""))
    dlg = _scan()
    dlg._browse_folder()
    dlg._browse_out_dir()
    assert dlg._folder_edit.text() == ""
    assert dlg._out_dir_edit.text() == ""
    dlg.deleteLater()


def test_scan_browse_out_dir_sets_folder(qapp, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: "D:/out"))
    dlg = _scan()
    dlg._browse_out_dir()
    assert dlg._out_dir_edit.text() == "D:/out"
    dlg.deleteLater()


def test_scan_rescan_with_blank_folder_keeps_paths(qapp):
    dlg = _scan()
    dlg._paths = ["x"]
    dlg._rescan_current_folder()
    dlg._recursive_check.setChecked(True)
    assert dlg._paths == ["x"]
    dlg.deleteLater()


def test_scan_overwrite_toggle_shows_output_widgets(qapp):
    dlg = _scan()
    widgets = (dlg._out_dir_label, dlg._out_dir_edit, dlg._out_browse_btn,
               dlg._only_censored_check)
    assert all(not w.isVisibleTo(dlg) for w in widgets)
    dlg._overwrite_check.setChecked(False)
    assert all(w.isVisibleTo(dlg) for w in widgets)
    dlg._overwrite_check.setChecked(True)
    assert all(not w.isVisibleTo(dlg) for w in widgets)
    dlg.deleteLater()


def test_scan_mode_change_sets_padding(qapp):
    dlg = _scan()
    for mode in (_constants.MODE_ANIME, _constants.MODE_REAL, _constants.MODE_AUTO):
        dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData(mode))
        assert dlg._padding == _constants._MODE_DEFAULTS[mode]["padding"]
    dlg.deleteLater()


def test_scan_lock_disables_every_setting(qapp):
    dlg = _scan()
    dlg._lock_controls()
    assert all(not w.isEnabled() for w in dlg._controls())
    assert all(not cb.isEnabled() for cb in dlg._cat_checks.values())
    dlg.deleteLater()


def test_scan_unlock_keeps_sexual_act_off_in_real_mode(qapp):
    dlg = _scan()
    dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData(_constants.MODE_REAL))
    dlg._lock_controls()
    dlg._unlock_controls()
    assert all(w.isEnabled() for w in dlg._controls())
    for cat, cb in dlg._cat_checks.items():
        assert cb.isEnabled() is (cat != _constants.CAT_SEXUAL_ACT)
    dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData(_constants.MODE_ANIME))
    dlg._lock_controls()
    dlg._unlock_controls()
    assert all(cb.isEnabled() for cb in dlg._cat_checks.values())
    dlg.deleteLater()


def test_scan_frozen_env_builds_subprocess_worker(qapp, tmp_path):
    img = _png(tmp_path / "a.png")
    dlg = _scan([img], frozen=lambda: ("py.exe", "site"))
    dlg._folder_edit.setText(str(tmp_path))
    worker = dlg._make_worker(
        str(tmp_path / "out"), False, mode="real", conf=0.3, expand=5,
        style="blur", categories=frozenset({"x"}), shape="rect")
    assert isinstance(worker, _workers._SubprocessBatchWorker)
    assert (worker._python, worker._sp) == ("py.exe", "site")
    assert worker._paths == [img]
    assert worker._overwrite is False
    assert (worker._conf, worker._expand_pct, worker._style) == (0.3, 5, "blur")
    assert worker._scan_root == str(tmp_path)
    assert worker._failed_dir == dlg._last_failed_dir
    dlg.deleteLater()


def test_scan_frozen_env_none_falls_back_to_in_process(qapp, tmp_path):
    dlg = _scan(frozen=lambda: None)
    worker = dlg._make_worker(None, True, mode="real", conf=0.3, expand=0,
                              style="mosaic", categories=None, shape="rect")
    assert type(worker) is _workers._BatchWorker
    assert worker._scan_root is None
    dlg.deleteLater()


def test_scan_start_without_paths_is_a_no_op(qapp, deps):
    dlg = _scan()
    dlg._start()
    assert deps == []
    assert dlg._worker is None
    dlg.deleteLater()


def test_scan_start_runs_worker_after_deps(qapp, tmp_path, deps, no_start):
    img = _png(tmp_path / "a.png")
    dlg = _scan([img])
    out = tmp_path / "new" / "out"
    dlg._overwrite_check.setChecked(False)
    dlg._out_dir_edit.setText(str(out))
    dlg._shape_combo.setCurrentIndex(
        dlg._shape_combo.findData(_constants.SHAPE_PRECISE))
    dlg._start()
    assert out.is_dir()                      # separate output dir is created
    assert deps == [{"parent": None, "mode": dlg._mode_combo.currentData(),
                     "precise": True}]
    assert isinstance(dlg._worker, _workers._BatchWorker)
    assert dlg._worker._output_dir == str(out)
    assert dlg._worker._shape == _constants.SHAPE_PRECISE
    assert dlg._progress.maximum() == 1
    assert dlg._progress.isVisibleTo(dlg) is True
    assert dlg._status_label.text() == ""
    assert dlg._start_btn.isEnabled() is False
    dlg._worker.finished.emit()              # wired to _cleanup
    assert dlg._worker is None
    dlg.deleteLater()


def test_scan_start_shows_installing_until_deps_ready(qapp, tmp_path, monkeypatch):
    img = _png(tmp_path / "a.png")
    pending = []
    _patch_everywhere(monkeypatch, "_ensure_deps",
                      lambda parent, cb, mode, precise: pending.append((mode, precise)))
    dlg = _scan([img])
    dlg._lang = {}
    dlg._start()
    assert pending == [(dlg._mode_combo.currentData(), False)]
    assert dlg._status_label.text() == "Installing dependencies..."
    assert dlg._worker is None
    dlg.deleteLater()


def test_scan_progress_updates_bar_status_and_time(qapp):
    dlg = _scan()
    dlg._lang = {}
    dlg._progress.setMaximum(10)
    dlg._on_progress(2, 10, "b.png", 4.0, 8.0)
    assert dlg._progress.value() == 2
    assert dlg._status_label.text() == "3/10  b.png"
    assert dlg._time_label.text() == "Elapsed: 4s    ETA: 8s    (~2.0s / image)"
    dlg.deleteLater()


def test_scan_finished_with_failures_reports_folder(qapp, tmp_path, reloads):
    img = _png(tmp_path / "a.png")
    dlg = _scan([img])
    dlg._lang = {}
    gui, toast = _gui_with_toast()
    dlg._gui = gui
    dlg._last_failed_dir = "D:/failed"
    dlg._time_label.setText("busy")
    dlg._on_finished(0, 1, 0)
    expected = ("Done — 0/1 images processed, 0 region(s) mosaiced, 1 failed."
                "\n1 failed image(s) copied to: D:/failed")
    assert dlg._finished is True
    assert dlg._status_label.text() == expected
    assert dlg._time_label.text() == ""
    assert dlg._start_btn.text() == "Start"
    assert toast.calls == [("info", expected)]
    assert reloads == [gui]                  # overwrite is on by default
    dlg.deleteLater()


def test_scan_finished_clean_run_toasts_success_without_reload(qapp, reloads):
    dlg = _scan()
    dlg._lang = {}
    gui, toast = _gui_with_toast()
    dlg._gui = gui
    dlg._overwrite_check.setChecked(False)
    dlg._last_failed_dir = "D:/failed"
    dlg._on_finished(2, 0, 3)
    msg = "Done — 2/2 images processed, 3 region(s) mosaiced, 0 failed."
    assert dlg._status_label.text() == msg
    assert toast.calls == [("success", msg)]
    assert reloads == []
    dlg.deleteLater()


# ---------------------------------------------------------------------------
# SafetyReviewDialog (single image)
# ---------------------------------------------------------------------------

def _single(path="C:/pics/photo.jpg", frozen=None):
    return SafetyReviewDialog(SimpleNamespace(main_window=None), path,
                              get_frozen_env=frozen)


def test_single_defaults(qapp):
    dlg = _single()
    assert dlg._path_edit.text() == str(Path("C:/pics") / "photo_censored.jpg")
    assert dlg._overwrite_check.isChecked() is False
    assert dlg._progress_bar.maximum() == _workers._SingleWorker.STEPS
    assert dlg._progress_bar.isVisibleTo(dlg) is False
    assert dlg._block_spin.value() == _constants.DEFAULT_BLOCK_SIZE
    assert dlg._padding_spin.value() == _constants.DEFAULT_PADDING
    assert dlg.minimumWidth() == 480
    dlg.deleteLater()


def test_single_overwrite_toggle_locks_path(qapp):
    dlg = _single()
    dlg._overwrite_check.setChecked(True)
    assert dlg._path_edit.text() == "C:/pics/photo.jpg"
    assert dlg._path_edit.isEnabled() is False
    dlg._overwrite_check.setChecked(False)
    assert dlg._path_edit.isEnabled() is True
    assert dlg._path_edit.text() == "C:/pics/photo.jpg"
    dlg.deleteLater()


def test_single_browse_sets_path_only_when_chosen(qapp, monkeypatch):
    answers = iter([("", ""), ("D:/x.png", "Images")])
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: next(answers)))
    dlg = _single()
    before = dlg._path_edit.text()
    dlg._browse()
    assert dlg._path_edit.text() == before
    dlg._browse()
    assert dlg._path_edit.text() == "D:/x.png"
    dlg.deleteLater()


def test_single_mode_change_sets_padding_spin(qapp):
    dlg = _single()
    dlg._mode_combo.setCurrentIndex(dlg._mode_combo.findData(_constants.MODE_ANIME))
    assert dlg._padding_spin.value() == (
        _constants._MODE_DEFAULTS[_constants.MODE_ANIME]["padding"])
    dlg.deleteLater()


def test_single_collect_settings(qapp):
    dlg = _single()
    dlg._block_spin.setValue(12)
    dlg._padding_spin.setValue(7)
    settings = dlg._collect_settings()
    assert settings == {
        "bs": 12, "pad": 7, "mode": dlg._mode_combo.currentData(),
        "conf": dlg._conf_spin.value(), "expand": dlg._expand_spin.value(),
        "style": dlg._style_combo.currentData(),
        "categories": _selected_categories(dlg._cat_checks),
        "shape": dlg._shape_combo.currentData(),
    }
    dlg.deleteLater()


def test_single_make_worker_in_process_and_frozen(qapp):
    dlg = _single()
    settings = dict(bs=9, pad=3, mode="anime", conf=0.4, expand=10,
                    style="black", categories=frozenset({"c"}), shape="rect")
    worker = dlg._make_worker("out.png", settings)
    assert type(worker) is _workers._SingleWorker
    assert (worker._input, worker._output, worker._bs, worker._pad) == (
        "C:/pics/photo.jpg", "out.png", 9, 3)
    assert (worker._mode, worker._conf, worker._expand_pct, worker._style,
            worker._categories, worker._shape) == (
        "anime", 0.4, 10, "black", frozenset({"c"}), "rect")
    worker.progress.emit(2, "detecting")
    assert dlg._progress_bar.value() == 2
    assert dlg._status_label.text() == "detecting"

    dlg._get_frozen_env = lambda: ("py.exe", "site")
    sub = dlg._make_worker("out.png", settings)
    assert type(sub) is _workers._SubprocessSingleWorker
    assert (sub._python, sub._sp, sub._shape) == ("py.exe", "site", "rect")
    sub.progress.emit("remote step")
    assert dlg._status_label.text() == "remote step"
    dlg.deleteLater()


def test_single_do_run_with_blank_output_is_a_no_op(qapp, deps):
    dlg = _single()
    dlg._path_edit.setText("   ")
    dlg._do_run()
    assert deps == []
    assert dlg._run_btn.isEnabled() is True
    dlg.deleteLater()


def test_single_do_run_starts_worker(qapp, deps, no_start):
    dlg = _single()
    dlg._shape_combo.setCurrentIndex(
        dlg._shape_combo.findData(_constants.SHAPE_PRECISE))
    dlg._do_run()
    assert deps == [{"parent": None, "mode": dlg._mode_combo.currentData(),
                     "precise": True}]
    assert dlg._run_btn.isEnabled() is False
    assert dlg._progress_bar.isVisibleTo(dlg) is True
    assert type(dlg._worker) is _workers._SingleWorker
    dlg._worker.finished.emit()
    assert dlg._worker is None
    dlg.deleteLater()


def test_single_finished_error_toasts_and_stays_open(qapp, reloads, pump_until):
    dlg = _single()
    dlg._lang = {}
    gui, toast = _gui_with_toast()
    dlg._gui = gui
    dlg._run_btn.setEnabled(False)
    dlg._on_finished(False, "boom", 0)
    assert dlg._status_label.text() == "Error: boom"
    assert dlg._run_btn.isEnabled() is True
    assert toast.calls == [("info", "Error: boom")]
    assert reloads == []
    assert pump_until(lambda: dlg.result() == QDialog.DialogCode.Accepted,
                      timeout=0.8) is False
    dlg.deleteLater()


def test_single_finished_nothing_found(qapp, reloads, pump_until):
    dlg = _single()
    dlg._lang = {}
    gui, toast = _gui_with_toast()
    dlg._gui = gui
    dlg._on_finished(True, "out.png", 0)
    text = "No genitalia detected — image unchanged."
    assert dlg._status_label.text() == text
    assert toast.calls == [("success", text)]
    assert reloads == []
    assert pump_until(lambda: dlg.result() == QDialog.DialogCode.Accepted)
    dlg.deleteLater()


def test_single_finished_censored_with_overwrite_reloads(qapp, reloads, pump_until):
    dlg = _single()
    dlg._lang = {}
    gui, toast = _gui_with_toast()
    dlg._gui = gui
    dlg._overwrite_check.setChecked(True)
    dlg._on_finished(True, "out.png", 2)
    assert dlg._status_label.text() == "Done! Saved to: out.png"
    assert toast.calls == [("success", "Mosaic applied!")]
    assert reloads == [gui]
    assert pump_until(lambda: dlg.result() == QDialog.DialogCode.Accepted)
    dlg.deleteLater()


def test_single_finished_without_toast_still_accepts(qapp, reloads, pump_until):
    dlg = _single()
    dlg._on_finished(True, "out.png", 1)
    assert pump_until(lambda: dlg.result() == QDialog.DialogCode.Accepted)
    dlg.deleteLater()


# ---------------------------------------------------------------------------
# BatchSafetyReviewDialog
# ---------------------------------------------------------------------------

def _batch(paths, frozen=None):
    return BatchSafetyReviewDialog(SimpleNamespace(main_window=None), paths,
                                   get_frozen_env=frozen)


def test_batch_defaults_seed_output_from_first_path(qapp, tmp_path):
    img = _png(tmp_path / "a.png")
    dlg = _batch([img])
    assert dlg._dir_edit.text() == str(tmp_path)
    assert dlg._overwrite_check.isChecked() is False
    assert dlg._progress.isVisibleTo(dlg) is False
    dlg.deleteLater()
    empty = _batch([])
    assert empty._dir_edit.text() == ""
    empty.deleteLater()


def test_batch_overwrite_disables_output_widgets(qapp):
    dlg = _batch([])
    dlg._overwrite_check.setChecked(True)
    assert not dlg._dir_edit.isEnabled()
    assert not dlg._browse_btn.isEnabled()
    assert not dlg._dir_label.isEnabled()
    dlg._overwrite_check.setChecked(False)
    assert dlg._dir_edit.isEnabled() and dlg._browse_btn.isEnabled()
    dlg.deleteLater()


def test_batch_browse(qapp, monkeypatch):
    answers = iter(["", "D:/dest"])
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: next(answers)))
    dlg = _batch([])
    dlg._browse()
    assert dlg._dir_edit.text() == ""
    dlg._browse()
    assert dlg._dir_edit.text() == "D:/dest"
    dlg.deleteLater()


def test_batch_make_worker_in_process_and_frozen(qapp):
    dlg = _batch(["a.png"])
    settings = dict(bs=9, pad=3, mode="anime", conf=0.4, expand=10,
                    style="black", categories=None, shape="rect")
    worker = dlg._make_worker("D:/out", True, settings)
    assert type(worker) is _workers._BatchWorker
    assert (worker._paths, worker._output_dir, worker._bs, worker._pad,
            worker._overwrite) == (["a.png"], "D:/out", 9, 3, True)
    assert worker._source_root is None
    dlg._get_frozen_env = lambda: ("py.exe", "site")
    sub = dlg._make_worker("D:/out", False, settings)
    assert type(sub) is _workers._SubprocessBatchWorker
    assert (sub._python, sub._overwrite, sub._mode) == ("py.exe", False, "anime")
    dlg.deleteLater()


def test_batch_do_run_needs_existing_output_dir(qapp, tmp_path, deps):
    dlg = _batch(["a.png"])
    dlg._dir_edit.setText(str(tmp_path / "missing"))
    dlg._do_run()
    dlg._dir_edit.setText("")
    dlg._do_run()
    assert deps == []
    assert dlg._run_btn.isEnabled() is True
    dlg.deleteLater()


def test_batch_do_run_overwrite_ignores_output_dir(qapp, deps, no_start):
    dlg = _batch(["a.png", "b.png"])
    dlg._dir_edit.setText("")
    dlg._overwrite_check.setChecked(True)
    dlg._do_run()
    assert deps == [{"parent": None, "mode": dlg._mode_combo.currentData(),
                     "precise": False}]
    assert type(dlg._worker) is _workers._BatchWorker
    assert dlg._worker._overwrite is True
    assert dlg._progress.maximum() == 2
    assert dlg._progress.value() == 0
    assert dlg._run_btn.isEnabled() is False
    dlg._worker.finished.emit()
    assert dlg._worker is None
    dlg.deleteLater()


def test_batch_progress(qapp):
    dlg = _batch(["a.png"])
    dlg._lang = {}
    dlg._progress.setMaximum(5)
    dlg._on_progress(0, 5, "a.png", 1.0, 4.0)
    assert dlg._progress.value() == 0
    assert dlg._status_label.text() == "1/5  a.png"
    assert dlg._time_label.text() == "Elapsed: 1s    ETA: ...    (~1.0s / image)"
    dlg._on_progress(1, 5, "b.png")
    assert dlg._status_label.text() == "2/5  b.png"
    dlg.deleteLater()


@pytest.mark.parametrize(("failed", "kind"), [(0, "success"), (2, "info")])
def test_batch_finished(qapp, reloads, pump_until, failed, kind):
    dlg = _batch(["a.png"])
    dlg._lang = {}
    gui, toast = _gui_with_toast()
    dlg._gui = gui
    dlg._overwrite_check.setChecked(bool(failed))
    dlg._run_btn.setEnabled(False)
    dlg._on_finished(3, failed, -1)
    msg = f"Processed 3/{3 + failed} image(s)"
    assert dlg._status_label.text() == msg
    assert dlg._run_btn.isEnabled() is True
    assert toast.calls == [(kind, msg)]
    assert reloads == ([gui] if failed else [])
    assert pump_until(lambda: dlg.result() == QDialog.DialogCode.Accepted)
    dlg.deleteLater()


def test_dialogs_module_keeps_public_names():
    for name in ("BatchSafetyReviewDialog", "SafetyReviewDialog", "ScanAllDialog",
                 "_build_mode_row", "_ensure_deps", "_WorkerHostMixin",
                 "_reload_grid_or_deepzoom", "_fmt_time", "_selected_categories",
                 "_format_result_message", "_SettingsDialogBase"):
        assert hasattr(_dialogs, name), name
