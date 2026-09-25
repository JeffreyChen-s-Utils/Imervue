"""The viewer's wiring of :class:`ShownFileWatch`: an external save reloads the deep-zoom picture."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from _qt_skip import pytestmark  # noqa: E402,F401
from Imervue.gpu_image_view import shown_file_watch
from Imervue.gpu_image_view.gpu_image_view import GPUImageView


@pytest.fixture
def view(qapp, monkeypatch):
    monkeypatch.setattr(shown_file_watch, "SETTLE_MS", 20)
    widget = GPUImageView(SimpleNamespace())
    yield widget
    widget._shown_file_watch.follow(None)
    widget.deleteLater()


def test_an_external_save_of_the_shown_picture_reloads_it_and_its_thumbnail(
        view, tmp_path, monkeypatch, pump_until):
    path = tmp_path / "a.png"
    path.write_bytes(b"x" * 100)
    reloads, thumbnails, rows = [], [], []
    monkeypatch.setattr(view, "reload_current_image_with_recipe", reloads.append)
    monkeypatch.setattr("Imervue.gpu_image_view.tile_loader.refresh_rewritten_tile",
                        lambda _view, p, _gen: thumbnails.append(p))
    view.main_window.refetch_list_rows = rows.append
    view._deep_zoom_path = str(path)
    view._shown_file_watch.follow(str(path))
    later = path.stat().st_mtime + 2   # Qt tells a change by the time alone: a real save is later
    path.write_bytes(b"y" * 300)
    os.utime(path, (later, later))
    assert pump_until(lambda: reloads == [str(path)])
    assert thumbnails == [str(path)]
    assert rows == [{str(path)}]


def test_a_picture_the_viewer_has_left_is_not_reloaded(view, tmp_path, monkeypatch):
    path = tmp_path / "a.png"
    path.write_bytes(b"x" * 100)
    reloads = []
    monkeypatch.setattr(view, "reload_current_image_with_recipe", reloads.append)
    view._deep_zoom_path = str(path)
    view._shown_file_watch.follow(str(path))
    view._deep_zoom_path = None   # back to the grid
    path.write_bytes(b"y" * 300)
    view._shown_file_watch._check()
    assert reloads == []
