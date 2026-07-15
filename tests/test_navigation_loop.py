"""Tests for switch_to_next/previous_image auto-loop and cross-folder nav."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def nav():
    from Imervue.gpu_image_view.actions import select as m
    return m


def _make_stub_gui(images):
    """Build a minimal mock viewer accepted by switch_to_{next,previous}_image."""
    gui = MagicMock()
    gui.model.images = list(images)
    gui.current_index = 0
    gui.main_window = MagicMock()
    # toast lookups expect a language dict
    gui.main_window.language_wrapper.language_word_dict = {}
    return gui


class TestAutoLoop:
    def test_default_loops_forward(self, nav, monkeypatch):
        # Auto-loop enabled by default
        monkeypatch.setattr(nav, "_auto_loop_enabled", lambda: True)
        gui = _make_stub_gui(["a.png", "b.png", "c.png"])
        gui.current_index = 2  # At last image

        nav.switch_to_next_image(main_gui=gui)
        assert gui.current_index == 0
        gui.load_deep_zoom_image.assert_called_once_with("a.png")

    def test_default_loops_backward(self, nav, monkeypatch):
        monkeypatch.setattr(nav, "_auto_loop_enabled", lambda: True)
        gui = _make_stub_gui(["a.png", "b.png", "c.png"])
        gui.current_index = 0  # At first image

        nav.switch_to_previous_image(main_gui=gui)
        assert gui.current_index == 2
        gui.load_deep_zoom_image.assert_called_once_with("c.png")

    def test_disabled_stops_at_ends(self, nav, monkeypatch):
        monkeypatch.setattr(nav, "_auto_loop_enabled", lambda: False)
        gui = _make_stub_gui(["a.png", "b.png"])
        gui.current_index = 1

        nav.switch_to_next_image(main_gui=gui)
        assert gui.current_index == 1
        gui.load_deep_zoom_image.assert_not_called()

    def test_empty_list_is_noop(self, nav):
        gui = _make_stub_gui([])
        nav.switch_to_next_image(main_gui=gui)
        nav.switch_to_previous_image(main_gui=gui)
        gui.load_deep_zoom_image.assert_not_called()

    def test_normal_advance_does_not_loop(self, nav, monkeypatch):
        monkeypatch.setattr(nav, "_auto_loop_enabled", lambda: True)
        gui = _make_stub_gui(["a.png", "b.png", "c.png"])
        gui.current_index = 0

        nav.switch_to_next_image(main_gui=gui)
        assert gui.current_index == 1


class TestWrapForgetsViewMemory:
    """Wrapping past an end must open the target fitted, not at a leftover zoom.

    The per-image zoom memory made the first image reopen 'too large' after
    looping from the last one: its remembered zoom-in was restored and kept.
    Wrap now forgets the target's saved view so ``load_deep_zoom_image`` fits it
    fresh. A normal (non-wrapping) step still resumes where the user left off.
    """

    def test_forward_wrap_forgets_target(self, nav, monkeypatch):
        monkeypatch.setattr(nav, "_auto_loop_enabled", lambda: True)
        gui = _make_stub_gui(["a.png", "b.png", "c.png"])
        gui.current_index = 2  # last image
        gui._view_memory = {"a.png": {"zoom": 3.0}, "c.png": {"zoom": 1.0}}

        nav.switch_to_next_image(main_gui=gui)

        assert gui.current_index == 0
        assert "a.png" not in gui._view_memory      # wrapped-to target forgotten
        assert "c.png" in gui._view_memory          # others untouched

    def test_backward_wrap_forgets_target(self, nav, monkeypatch):
        monkeypatch.setattr(nav, "_auto_loop_enabled", lambda: True)
        gui = _make_stub_gui(["a.png", "b.png", "c.png"])
        gui.current_index = 0  # first image
        gui._view_memory = {"c.png": {"zoom": 4.0}, "a.png": {"zoom": 1.0}}

        nav.switch_to_previous_image(main_gui=gui)

        assert gui.current_index == 2
        assert "c.png" not in gui._view_memory
        assert "a.png" in gui._view_memory

    def test_normal_step_keeps_memory(self, nav, monkeypatch):
        monkeypatch.setattr(nav, "_auto_loop_enabled", lambda: True)
        gui = _make_stub_gui(["a.png", "b.png", "c.png"])
        gui.current_index = 0
        gui._view_memory = {"b.png": {"zoom": 2.0}}

        nav.switch_to_next_image(main_gui=gui)  # 0 -> 1, no wrap

        assert gui.current_index == 1
        assert "b.png" in gui._view_memory       # resume preserved on normal step

    def test_forget_helper_is_safe_without_a_dict(self, nav):
        # A stubbed viewer whose _view_memory isn't a real dict must be a no-op.
        gui = MagicMock()  # _view_memory is an auto-mock, not a dict
        nav._forget_view_on_wrap(gui, "x.png")   # must not raise
        gui = MagicMock()
        gui._view_memory = None
        nav._forget_view_on_wrap(gui, "x.png")   # must not raise

    def test_forget_helper_pops_only_the_target(self, nav):
        gui = MagicMock()
        gui._view_memory = {"x.png": {"zoom": 2.0}, "y.png": {"zoom": 1.0}}
        nav._forget_view_on_wrap(gui, "x.png")
        assert gui._view_memory == {"y.png": {"zoom": 1.0}}
        nav._forget_view_on_wrap(gui, "missing.png")  # absent → no error
        assert gui._view_memory == {"y.png": {"zoom": 1.0}}


class TestCrossFolder:
    def test_no_images_is_noop(self, nav):
        gui = _make_stub_gui([])
        # Shouldn't raise even with empty images
        nav.switch_to_next_folder(main_gui=gui)
        nav.switch_to_previous_folder(main_gui=gui)

    def test_scans_sibling_folders(self, nav, tmp_path, monkeypatch):
        # Build: parent/{a,b,c}/image.png
        for name in ("a", "b", "c"):
            folder = tmp_path / name
            folder.mkdir()
            (folder / "img.png").write_bytes(b"")  # placeholder

        # ``image_loader`` pulls in rawpy which isn't available in CI/dev VMs;
        # skip if the module can't be imported. The function under test is still
        # exercised via monkeypatching, but only when the loader itself works.
        image_loader = pytest.importorskip(
            "Imervue.gpu_image_view.images.image_loader"
        )

        monkeypatch.setattr(
            image_loader, "_scan_images",
            lambda p: [str(Path(p) / "img.png")] if Path(p).is_dir() else [],
        )
        monkeypatch.setattr(image_loader, "open_path", lambda **kw: None)

        gui = _make_stub_gui([str(tmp_path / "a" / "img.png")])
        nav.switch_to_next_folder(main_gui=gui)

        # Main window's model/tree/filename_label/watch_folder should have been touched
        gui.main_window.model.setRootPath.assert_called()
        gui.main_window.watch_folder.assert_called()
