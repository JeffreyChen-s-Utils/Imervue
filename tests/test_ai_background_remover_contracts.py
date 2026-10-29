"""Behaviour contracts for the AI background-remover plugin.

They pin the subprocess argv and stdout protocol of the frozen-build workers,
the in-process workers' rembg call and output naming, the dialogs' state and
worker choice, and the plugin hooks. Nothing here needs rembg, onnxruntime or a
real model: ``subprocess.Popen`` is replaced, rembg is a fake module, and every
worker body runs inline.
"""
from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtWidgets import QDialog, QFileDialog

from ai_background_remover import ai_background_remover as mod
from Imervue.plugin.pip_installer import _subprocess_kwargs

_MATTING = {
    "alpha_matting_foreground_threshold": 240,
    "alpha_matting_background_threshold": 10,
    "alpha_matting_erode_size": 10,
}


class _FakeProc:
    """A child whose stdout yields ``lines``; records how far it was read."""

    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.read = 0
        self.returncode = returncode
        self.waited = 0

    @property
    def stdout(self):
        for line in self._lines:
            self.read += 1
            yield line

    def wait(self, timeout=None):
        self.waited += 1
        return self.returncode


@pytest.fixture
def popen(monkeypatch):
    """Replace Popen with one returning the queued proc; record each call."""
    calls: list[tuple[list, dict]] = []
    state = {"proc": _FakeProc([])}

    def fake(cmd, **kwargs):
        calls.append((cmd, kwargs))
        result = state["proc"]
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(subprocess, "Popen", fake)
    return SimpleNamespace(calls=calls, state=state)


def _collect(worker):
    progress: list = []
    results: list = []
    worker.progress.connect(lambda *a: progress.append(a))
    worker.result_ready.connect(lambda *a: results.append(a))
    return progress, results


# ===========================
# Subprocess single worker
# ===========================

class TestSubprocessRemoveWorker:
    def _run(self, qapp, popen, proc, alpha=True):
        popen.state["proc"] = proc
        worker = mod._SubprocessRemoveWorker("py.exe", "site", "in.png", "out.png", "u2netp", alpha)
        progress, results = _collect(worker)
        worker.run()
        return worker, progress, results

    def test_argv_and_pipes(self, qapp, popen):
        worker, _, _ = self._run(qapp, popen, _FakeProc(["OK:out.png\n"]))
        cmd, kwargs = popen.calls[0]
        assert cmd == ["py.exe", str(mod._RUNNER_SCRIPT), "site", "single", "in.png",
                       "out.png", "u2netp", "True", str(mod._MODELS_DIR)]
        assert kwargs["stdout"] is subprocess.PIPE
        assert kwargs["stderr"] is subprocess.STDOUT
        assert {k: v for k, v in kwargs.items() if k not in ("stdout", "stderr")} \
            == _subprocess_kwargs()
        assert worker._proc is popen.state["proc"]

    def test_progress_then_ok_stops_reading(self, qapp, popen):
        proc = _FakeProc(["PROGRESS:Loading\r\n", "\n", "PROGRESS:Model\n",
                          "OK:done.png\n", "ERROR:never read\n"])
        _, progress, results = self._run(qapp, popen, proc)
        assert progress == [("Loading",), ("Model",)]
        assert results == [(True, "done.png")]
        assert proc.read == 4
        assert proc.waited == 1

    def test_error_line_reports_failure(self, qapp, popen):
        proc = _FakeProc(["noise\n", "ERROR:bad model\n", "OK:late\n"])
        _, progress, results = self._run(qapp, popen, proc, alpha=False)
        assert popen.calls[0][0][7] == "False"
        assert progress == []
        assert results == [(False, "bad model")]
        assert proc.waited == 1

    def test_silent_exit_with_error_code(self, qapp, popen):
        _, _, results = self._run(qapp, popen, _FakeProc(["chatter\n"], returncode=3))
        assert results == [(False, "Process exited with code 3")]

    def test_silent_clean_exit_reports_output_path(self, qapp, popen):
        _, _, results = self._run(qapp, popen, _FakeProc([]))
        assert results == [(True, "out.png")]

    def test_popen_failure_reports_message(self, qapp, popen):
        _, _, results = self._run(qapp, popen, FileNotFoundError("no python"))
        assert results == [(False, "no python")]


# ===========================
# Subprocess batch worker
# ===========================

class TestSubprocessBatchWorker:
    def _run(self, qapp, popen, proc, paths=("a.png", "b.png", "c.png")):
        popen.state["proc"] = proc
        worker = mod._SubprocessBatchWorker("py.exe", "site", list(paths), "outdir", "silueta", False)
        progress, results = _collect(worker)
        worker.run()
        return progress, results

    def test_argv(self, qapp, popen):
        self._run(qapp, popen, _FakeProc(["BATCH_OK:3:0\n"]))
        cmd, kwargs = popen.calls[0]
        assert cmd[:4] == ["py.exe", str(mod._RUNNER_SCRIPT), "site", "batch"]
        assert cmd[4].endswith(".json")
        assert cmd[5:] == ["outdir", "silueta", "False", str(mod._MODELS_DIR)]
        assert kwargs["stdout"] is subprocess.PIPE
        assert kwargs["stderr"] is subprocess.STDOUT

    def test_progress_name_keeps_colons_and_short_lines_are_ignored(self, qapp, popen):
        proc = _FakeProc(["BATCH_PROGRESS:0:3:C:/x/a.png\n", "BATCH_PROGRESS:1:3\n", "\n",
                          "BATCH_OK:2:1\n", "BATCH_OK:9:9\n"])
        progress, results = self._run(qapp, popen, proc)
        assert progress == [(0, 3, "C:/x/a.png")]
        assert results == [(2, 1)]
        assert proc.read == 4
        assert proc.waited == 1

    def test_error_line_counts_every_path_failed(self, qapp, popen):
        proc = _FakeProc(["ERROR:boom\n", "BATCH_OK:3:0\n"])
        _, results = self._run(qapp, popen, proc)
        assert results == [(0, 3)]
        assert proc.waited == 1

    def test_stream_end_without_result_counts_every_path_failed(self, qapp, popen):
        proc = _FakeProc(["chatter\n"])
        _, results = self._run(qapp, popen, proc)
        assert results == [(0, 3)]
        assert proc.waited == 1

    def test_unparsable_progress_fails_and_removes_list(self, qapp, popen):
        _, results = self._run(qapp, popen, _FakeProc(["BATCH_PROGRESS:x:3:a\n"]))
        assert results == [(0, 3)]
        assert not Path(popen.calls[0][0][4]).exists()


# ===========================
# In-process workers
# ===========================

class _FakeOutput:
    def __init__(self, saved: list):
        self._saved = saved

    def save(self, path):
        self._saved.append(path)


@pytest.fixture
def fake_rembg(monkeypatch):
    """Install a fake ``rembg`` whose ``remove`` records its call."""
    module = types.ModuleType("rembg")
    log = SimpleNamespace(sessions=[], removes=[], saved=[], fail_on=set())

    def new_session(name):
        log.sessions.append(name)
        return ("session", name)

    def remove(img, **kwargs):
        log.removes.append((img.size, kwargs))
        if img.size in log.fail_on:
            raise RuntimeError("remove failed")
        return _FakeOutput(log.saved)

    module.new_session = new_session
    module.remove = remove
    monkeypatch.setitem(sys.modules, "rembg", module)
    return log


def _png(path: Path, size=(8, 6)) -> str:
    Image.new("RGB", size).save(path)
    return str(path)


class TestInProcessRemoveWorker:
    def test_success_path(self, qapp, tmp_path, fake_rembg):
        src = _png(tmp_path / "a.png")
        worker = mod._RemoveBackgroundWorker(src, "out.png", "isnet-anime", True)
        progress, results = _collect(worker)
        worker.run()
        assert progress == [("Loading rembg...",), ("Loading model: isnet-anime...",),
                            ("Processing image...",), ("Saving result...",)]
        assert fake_rembg.sessions == ["isnet-anime"]
        assert fake_rembg.removes == [((8, 6), {"session": ("session", "isnet-anime"),
                                                "alpha_matting": True, **_MATTING})]
        assert fake_rembg.saved == ["out.png"]
        assert results == [(True, "out.png")]

    def test_failure_reports_message(self, qapp, tmp_path, fake_rembg):
        worker = mod._RemoveBackgroundWorker(str(tmp_path / "missing.png"), "o.png", "u2net", False)
        _, results = _collect(worker)
        worker.run()
        assert len(results) == 1
        assert results[0][0] is False
        assert "missing.png" in results[0][1]

    def test_svg_goes_through_the_svg_loader(self, monkeypatch):
        import numpy as np

        from Imervue.gpu_image_view.images import image_loader
        calls: list = []

        def fake_svg(path, thumbnail):
            calls.append((path, thumbnail))
            return np.zeros((5, 7, 4), dtype=np.uint8)

        monkeypatch.setattr(image_loader, "_load_svg", fake_svg)
        img = mod._RemoveBackgroundWorker._load_image("x.SVG")
        assert img.size == (7, 5)
        assert calls == [("x.SVG", False)]


class TestInProcessBatchWorker:
    def test_names_avoid_collisions_and_failures_are_counted(self, qapp, tmp_path, fake_rembg):
        out = tmp_path / "out"
        out.mkdir()
        (out / "a_nobg.png").write_bytes(b"")
        (out / "a_nobg_1.png").write_bytes(b"")
        a = _png(tmp_path / "a.png")
        b = _png(tmp_path / "b.png", size=(3, 3))
        c = _png(tmp_path / "c.png", size=(4, 4))
        fake_rembg.fail_on = {(3, 3)}
        worker = mod._BatchRemoveWorker([a, b, c, str(tmp_path / "gone.png")],
                                        str(out), "u2net", False)
        progress, results = _collect(worker)
        worker.run()
        assert progress == [(0, 4, "a.png"), (1, 4, "b.png"), (2, 4, "c.png"),
                            (3, 4, "gone.png")]
        assert fake_rembg.saved == [str(out / "a_nobg_2.png"), str(out / "c_nobg.png")]
        assert fake_rembg.removes[0][1] == {"session": ("session", "u2net"),
                                            "alpha_matting": False, **_MATTING}
        assert results == [(2, 2)]


# ===========================
# Dialogs
# ===========================

class _Toast:
    def __init__(self):
        self.calls: list = []

    def success(self, msg):
        self.calls.append(("success", msg))

    def info(self, msg):
        self.calls.append(("info", msg))


def _gui():
    return SimpleNamespace(main_window=None)


def _with_toast(dlg) -> _Toast:
    toast = _Toast()
    dlg._gui = SimpleNamespace(main_window=SimpleNamespace(toast=toast))
    return toast


@pytest.fixture
def no_start(monkeypatch):
    started: list = []
    for cls in (mod._SubprocessRemoveWorker, mod._RemoveBackgroundWorker,
                mod._SubprocessBatchWorker, mod._BatchRemoveWorker):
        monkeypatch.setattr(cls, "start", lambda self: started.append(self))
    return started


class TestRemoveBackgroundDialog:
    def test_initial_state(self, qapp, tmp_path):
        dlg = mod.RemoveBackgroundDialog(_gui(), str(tmp_path / "pic.jpg"))
        assert dlg.windowTitle() == "AI Background Removal"
        combo = dlg._model_combo
        assert [combo.itemData(i) for i in range(combo.count())] == mod.MODELS
        assert combo.itemText(0) == "u2net  \u2014  General purpose (173 MB)"
        assert combo.currentIndex() == 0
        assert not dlg._alpha_check.isChecked()
        assert dlg._path_edit.text() == str(tmp_path / "pic_nobg.png")
        assert not dlg._progress_bar.isVisibleTo(dlg)
        assert dlg._progress_bar.maximum() == 0
        assert dlg._status_label.text() == ""
        assert dlg._worker is None
        dlg.deleteLater()

    def test_blank_output_does_nothing(self, qapp, no_start):
        dlg = mod.RemoveBackgroundDialog(_gui(), "pic.png")
        dlg._path_edit.setText("   ")
        dlg._do_remove()
        assert dlg._worker is None
        assert dlg._run_btn.isEnabled()
        assert no_start == []
        dlg.deleteLater()

    def test_frozen_env_uses_the_subprocess_worker(self, qapp, no_start):
        dlg = mod.RemoveBackgroundDialog(_gui(), "pic.png", frozen_env=("py.exe", "site"))
        dlg._path_edit.setText(" out.png ")
        dlg._model_combo.setCurrentIndex(1)
        dlg._alpha_check.setChecked(True)
        dlg._do_remove()
        worker = dlg._worker
        assert type(worker) is mod._SubprocessRemoveWorker
        assert (worker._python, worker._site_packages, worker._input, worker._output,
                worker._model, worker._alpha_matting) == (
            "py.exe", "site", "pic.png", "out.png", "u2netp", True)
        assert no_start == [worker]
        assert not dlg._run_btn.isEnabled()
        assert dlg._progress_bar.isVisibleTo(dlg)
        worker.progress.emit("hello")
        assert dlg._status_label.text() == "hello"
        worker.finished.emit()
        assert dlg._worker is None
        dlg.deleteLater()

    def test_dev_env_uses_the_in_process_worker(self, qapp, no_start):
        dlg = mod.RemoveBackgroundDialog(_gui(), "pic.png")
        dlg._do_remove()
        worker = dlg._worker
        assert type(worker) is mod._RemoveBackgroundWorker
        assert (worker._input, worker._output, worker._model, worker._alpha_matting) == (
            "pic.png", "pic_nobg.png", "u2net", False)
        dlg._worker = None
        dlg.deleteLater()

    def test_success_toasts_and_accepts(self, qapp, pump_until):
        dlg = mod.RemoveBackgroundDialog(_gui(), "pic.png")
        toast = _with_toast(dlg)
        dlg._run_btn.setEnabled(False)
        dlg._on_finished(True, "c:/o.png")
        assert dlg._status_label.text() == "Done! Saved to: c:/o.png"
        assert dlg._run_btn.isEnabled()
        assert toast.calls == [("success", "Background removed!")]
        pump_until(lambda: dlg.result() == QDialog.DialogCode.Accepted)
        dlg.deleteLater()

    def test_failure_reports_and_stays_open(self, qapp):
        dlg = mod.RemoveBackgroundDialog(_gui(), "pic.png")
        toast = _with_toast(dlg)
        dlg._on_finished(False, "boom")
        assert dlg._status_label.text() == "Error: boom"
        assert toast.calls == [("info", "Error: boom")]
        qapp.processEvents()
        assert dlg.result() == QDialog.DialogCode.Rejected
        dlg.deleteLater()

    def test_finish_without_toast_host(self, qapp):
        dlg = mod.RemoveBackgroundDialog(_gui(), "pic.png")
        dlg._on_finished(False, "x")
        assert dlg._status_label.text() == "Error: x"
        dlg.deleteLater()

    def test_browse(self, qapp, monkeypatch):
        dlg = mod.RemoveBackgroundDialog(_gui(), "pic.png")
        answers = iter([("chosen.png", "PNG (*.png)"), ("", "")])
        seen: list = []

        def fake(parent, title, start, filt):
            seen.append((title, start, filt))
            return next(answers)

        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(fake))
        dlg._browse()
        assert dlg._path_edit.text() == "chosen.png"
        dlg._browse()
        assert dlg._path_edit.text() == "chosen.png"
        assert seen[0] == ("Save", "pic_nobg.png", "PNG (*.png)")
        dlg.deleteLater()


class TestBatchRemoveBackgroundDialog:
    def test_initial_state(self, qapp, tmp_path):
        paths = [str(tmp_path / "a.png"), str(tmp_path / "b.png")]
        dlg = mod.BatchRemoveBackgroundDialog(_gui(), paths)
        assert dlg.windowTitle() == "Batch AI Background Removal"
        assert dlg._model_combo.count() == len(mod.MODELS)
        assert dlg._dir_edit.text() == str(tmp_path)
        assert not dlg._alpha_check.isChecked()
        assert not dlg._progress.isVisibleTo(dlg)
        dlg.deleteLater()
        empty = mod.BatchRemoveBackgroundDialog(_gui(), [])
        assert empty._dir_edit.text() == ""
        empty.deleteLater()

    def test_missing_folder_does_nothing(self, qapp, tmp_path, no_start):
        dlg = mod.BatchRemoveBackgroundDialog(_gui(), ["a.png"])
        dlg._dir_edit.setText(str(tmp_path / "nope"))
        dlg._do_remove()
        dlg._dir_edit.setText("")
        dlg._do_remove()
        assert no_start == []
        assert dlg._run_btn.isEnabled()
        dlg.deleteLater()

    def test_frozen_env_uses_the_subprocess_worker(self, qapp, tmp_path, no_start):
        paths = ["a.png", "b.png", "c.png"]
        dlg = mod.BatchRemoveBackgroundDialog(_gui(), paths, frozen_env=("py.exe", "site"))
        dlg._dir_edit.setText(f" {tmp_path} ")
        dlg._alpha_check.setChecked(True)
        dlg._do_remove()
        worker = dlg._worker
        assert type(worker) is mod._SubprocessBatchWorker
        assert (worker._python, worker._site_packages, worker._paths, worker._output_dir,
                worker._model, worker._alpha_matting) == (
            "py.exe", "site", paths, str(tmp_path), "u2net", True)
        assert no_start == [worker]
        assert dlg._progress.maximum() == 3
        assert dlg._progress.value() == 0
        assert not dlg._run_btn.isEnabled()
        worker.progress.emit(2, 3, "c.png")
        assert dlg._progress.value() == 2
        assert dlg._status_label.text() == "2/3  c.png"
        worker.finished.emit()
        assert dlg._worker is None
        dlg.deleteLater()

    def test_dev_env_uses_the_in_process_worker(self, qapp, tmp_path, no_start):
        dlg = mod.BatchRemoveBackgroundDialog(_gui(), ["a.png"])
        dlg._dir_edit.setText(str(tmp_path))
        dlg._do_remove()
        assert type(dlg._worker) is mod._BatchRemoveWorker
        assert dlg._worker._output_dir == str(tmp_path)
        dlg._worker = None
        dlg.deleteLater()

    @pytest.mark.parametrize(("failed", "kind"), [(0, "success"), (2, "info")])
    def test_finish_toasts_by_outcome_and_accepts(self, qapp, pump_until, failed, kind):
        dlg = mod.BatchRemoveBackgroundDialog(_gui(), ["a.png"])
        toast = _with_toast(dlg)
        dlg._on_finished(3, failed)
        msg = f"Processed 3/{3 + failed} image(s)"
        assert dlg._status_label.text() == msg
        assert toast.calls == [(kind, msg)]
        assert dlg._run_btn.isEnabled()
        pump_until(lambda: dlg.result() == QDialog.DialogCode.Accepted)
        dlg.deleteLater()

    def test_browse(self, qapp, monkeypatch):
        dlg = mod.BatchRemoveBackgroundDialog(_gui(), ["x/a.png"])
        answers = iter(["D:/out", ""])
        monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                            staticmethod(lambda parent, title: next(answers)))
        dlg._browse()
        assert dlg._dir_edit.text() == "D:/out"
        dlg._browse()
        assert dlg._dir_edit.text() == "D:/out"
        dlg.deleteLater()


# ===========================
# Plugin hooks
# ===========================

class _Action:
    def __init__(self, title):
        self.title = title
        self.slots: list = []
        self.triggered = SimpleNamespace(connect=self.slots.append)


class _Menu:
    def __init__(self):
        self.actions: list[_Action] = []
        self.menus: list = []

    def addAction(self, title):  # noqa: N802 - Qt API
        action = _Action(title)
        self.actions.append(action)
        return action

    def addMenu(self, title):  # noqa: N802 - Qt API
        sub = _Menu()
        self.menus.append((title, sub))
        return sub


def _viewer(**overrides):
    base = dict(deep_zoom=None, model=SimpleNamespace(images=[]), current_index=0,
                tile_grid_mode=False, tile_selection_mode=False, selected_tiles=set())
    base.update(overrides)
    return SimpleNamespace(**base)


def _plugin(viewer=None):
    window = SimpleNamespace(viewer=viewer or _viewer())
    return mod.AIBackgroundRemoverPlugin(window)


def _record(plugin, name):
    calls: list = []
    setattr(plugin, name, lambda arg: calls.append(arg))
    return calls


class TestPluginHooks:
    def test_menu_bar(self):
        plugin = _plugin()
        bar = _Menu()
        plugin.on_build_menu_bar(bar)
        title, sub = bar.menus[0]
        assert title == "AI Tools"
        assert [a.title for a in sub.actions] == ["AI Background Removal",
                                                   "Batch AI Background Removal"]
        assert sub.actions[0].slots == [plugin._open_single_dialog]
        assert sub.actions[1].slots == [plugin._open_batch_dialog]

    def test_context_menu_single_and_batch(self):
        viewer = _viewer(deep_zoom=object(), model=SimpleNamespace(images=["a", "b"]),
                         current_index=1, tile_grid_mode=True, tile_selection_mode=True,
                         selected_tiles={"x"})
        plugin = _plugin(viewer)
        single = _record(plugin, "_remove_single")
        batch = _record(plugin, "_remove_batch")
        menu = _Menu()
        plugin.on_build_context_menu(menu, viewer)
        assert [a.title for a in menu.actions] == ["AI Background Removal",
                                                    "Batch AI Background Removal"]
        menu.actions[0].slots[0]()
        menu.actions[1].slots[0]()
        assert single == ["b"]
        assert batch == [["x"]]

    @pytest.mark.parametrize("overrides", [
        {"deep_zoom": object(), "model": SimpleNamespace(images=["a"]), "current_index": 1},
        {"deep_zoom": object(), "model": SimpleNamespace(images=["a"]), "current_index": -1},
        {"deep_zoom": object()},
        {"tile_grid_mode": True, "tile_selection_mode": True},
        {"tile_grid_mode": True, "selected_tiles": {"x"}},
        {"tile_selection_mode": True, "selected_tiles": {"x"}},
    ])
    def test_context_menu_adds_nothing(self, overrides):
        viewer = _viewer(**overrides)
        menu = _Menu()
        _plugin(viewer).on_build_context_menu(menu, viewer)
        assert menu.actions == []

    def test_frozen_env(self, monkeypatch):
        from Imervue.system import app_paths
        plugin = _plugin()
        monkeypatch.setattr(mod, "_is_frozen", lambda: False)
        assert plugin._get_frozen_env() is None
        monkeypatch.setattr(mod, "_is_frozen", lambda: True)
        monkeypatch.setattr(mod, "_find_external_python", lambda: None)
        assert plugin._get_frozen_env() is None
        monkeypatch.setattr(mod, "_find_external_python", lambda: "py.exe")
        monkeypatch.setattr(app_paths, "app_dir", lambda: Path("APP"))
        assert plugin._get_frozen_env() == ("py.exe", str(Path("APP") / "lib" / "site-packages"))

    @pytest.mark.parametrize(("images", "index", "expected"), [
        ([], 0, []), (["a"], 1, []), (["a", "b"], 1, ["b"]),
    ])
    def test_open_single_dialog(self, images, index, expected):
        plugin = _plugin(_viewer(model=SimpleNamespace(images=images), current_index=index))
        calls = _record(plugin, "_remove_single")
        plugin._open_single_dialog()
        assert calls == expected

    @pytest.mark.parametrize(("overrides", "expected"), [
        ({"tile_grid_mode": True, "tile_selection_mode": True, "selected_tiles": {"s"},
          "model": SimpleNamespace(images=["a"])}, [["s"]]),
        ({"tile_grid_mode": True, "selected_tiles": {"s"},
          "model": SimpleNamespace(images=["a", "b"])}, [["a", "b"]]),
        ({}, []),
    ])
    def test_open_batch_dialog(self, overrides, expected):
        plugin = _plugin(_viewer(**overrides))
        calls = _record(plugin, "_remove_batch")
        plugin._open_batch_dialog()
        assert calls == expected

    def test_remove_single_skips_missing_file(self, tmp_path, monkeypatch):
        calls: list = []
        monkeypatch.setattr(mod, "_ensure_deps", lambda *a: calls.append(a))
        _plugin()._remove_single(str(tmp_path / "missing.png"))
        assert calls == []

    @pytest.mark.parametrize(("method", "dialog_name"), [
        ("_remove_single", "RemoveBackgroundDialog"),
        ("_remove_batch", "BatchRemoveBackgroundDialog"),
    ])
    def test_remove_opens_dialog_once_deps_ready(self, tmp_path, monkeypatch, caplog,
                                                 method, dialog_name):
        src = _png(tmp_path / "a.png")
        arg = src if method == "_remove_single" else [src]
        plugin = _plugin()
        plugin.main_window.marker = "window"
        ready: list = []
        monkeypatch.setattr(mod, "_ensure_deps", lambda parent, cb: ready.append((parent, cb)))
        monkeypatch.setattr(plugin, "_get_frozen_env", lambda: ("py", "sp"))
        built: list = []

        class _Dlg:
            def __init__(self, viewer, payload, frozen_env=None):
                built.append((viewer, payload, frozen_env))

            def exec(self):
                built.append("exec")

        monkeypatch.setattr(mod, dialog_name, _Dlg)
        getattr(plugin, method)(arg)
        assert ready[0][0] is plugin.main_window
        ready[0][1]()
        assert built == [(plugin.viewer, arg, ("py", "sp")), "exec"]

        def broken(*_a, **_k):
            raise RuntimeError("dialog broke")

        monkeypatch.setattr(mod, dialog_name, broken)
        with caplog.at_level("ERROR", logger="Imervue.plugin.ai_bg_remover"):
            ready[0][1]()   # logged, not raised
        assert any(r.exc_info for r in caplog.records)

    def test_ensure_deps(self, monkeypatch, caplog):
        calls: list = []
        monkeypatch.setattr(mod, "ensure_dependencies", lambda *a: calls.append(a))
        cb = object()
        mod._ensure_deps("parent", cb)
        assert calls == [("parent", mod.REQUIRED_PACKAGES, cb)]

        def boom(*_a):
            raise RuntimeError("installer broke")

        monkeypatch.setattr(mod, "ensure_dependencies", boom)
        with caplog.at_level("ERROR", logger="Imervue.plugin.ai_bg_remover"):
            mod._ensure_deps("parent", cb)
        assert any(r.exc_info for r in caplog.records)

    def test_translations_share_one_key_set(self):
        tables = _plugin().get_translations()
        assert set(tables) == {"English", "Traditional_Chinese", "Chinese", "Japanese", "Korean"}
        keys = set(tables["English"])
        assert all(set(t) == keys for t in tables.values())
        assert tables["English"]["bg_remove_menu"] == "AI Tools"

    def test_module_constants(self):
        assert mod.REQUIRED_PACKAGES == [("rembg", "rembg"), ("onnxruntime", "onnxruntime")]
        assert set(mod.MODEL_DESCRIPTIONS) == set(mod.MODELS)
        assert mod._RUNNER_SCRIPT.name == "_rembg_runner.py"
        assert mod._RUNNER_SCRIPT.is_file()
        assert mod._RUNNER_SCRIPT.parent == mod._PLUGIN_DIR
        assert mod._MODELS_DIR.is_dir()
