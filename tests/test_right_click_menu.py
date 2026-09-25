"""Tests for right-click menu actions that write files, Show in Explorer and Set as Wallpaper."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from PIL import Image

from Imervue.menu import right_click_menu


class _Toast:
    def __init__(self):
        self.calls = []

    def success(self, msg):
        self.calls.append(("success", msg))

    def info(self, msg):
        self.calls.append(("info", msg))


def _gui(paths):
    return SimpleNamespace(selected_tiles=list(paths),
                           main_window=SimpleNamespace(toast=_Toast()))


def test_auto_orient_writes_an_upright_srgb_copy(qapp, tmp_path):
    from _icc_profiles import DISPLAY_P3
    exif = Image.Exif()
    exif[0x0112] = 6
    src = tmp_path / "p.png"
    Image.new("RGB", (40, 20), (0, 255, 0)).save(src, exif=exif, icc_profile=DISPLAY_P3)
    gui = _gui([str(src)])
    right_click_menu._auto_orient(gui)  # noqa: SLF001
    with Image.open(tmp_path / "p_oriented.png") as out:
        assert out.size == (20, 40)
        assert "icc_profile" not in out.info
        assert out.getpixel((0, 0))[:2] == (0, 255)
    assert gui.main_window.toast.calls == [("success", "Oriented 1 photo(s)")]


def test_auto_orient_develops_a_raw_at_full_size(qapp, tmp_path, monkeypatch):
    from Imervue.gpu_image_view.images import image_loader
    monkeypatch.setattr(image_loader, "_load_raw",
                        lambda _p, thumbnail: np.zeros((30, 50, 3), dtype=np.uint8))
    raw = tmp_path / "shot.cr2"
    Image.new("RGB", (5, 3)).save(raw, format="TIFF")      # Pillow sees only a preview
    right_click_menu._auto_orient(_gui([str(raw)]))  # noqa: SLF001
    with Image.open(tmp_path / "shot_oriented.png") as out:
        assert out.size == (50, 30)


def test_auto_orient_skips_unreadable_files_and_says_so(qapp, tmp_path, caplog):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a png")
    gui = _gui([str(bad)])
    with caplog.at_level("WARNING", logger="Imervue"):
        right_click_menu._auto_orient(gui)  # noqa: SLF001
    assert gui.main_window.toast.calls == [("info", "No images to orient")]
    assert any("Auto-orient failed" in r.getMessage() for r in caplog.records)
    assert list(tmp_path.iterdir()) == [bad]


def test_auto_orient_keeps_an_earlier_copy(qapp, tmp_path):
    """Running it again replaced the last copy, retouching done to it since included."""
    src = tmp_path / "p.png"
    Image.new("RGB", (8, 4)).save(src)
    earlier = tmp_path / "p_oriented.png"
    earlier.write_bytes(b"retouched since")
    right_click_menu._auto_orient(_gui([str(src)]))  # noqa: SLF001
    assert earlier.read_bytes() == b"retouched since"
    with Image.open(tmp_path / "p_oriented_1.png") as out:
        assert out.size == (8, 4)


def test_auto_orient_gives_same_stem_photos_their_own_copies(qapp, tmp_path):
    """p.jpg and p.png in one selection both wrote p_oriented.png; the second won."""
    jpg, png = tmp_path / "p.jpg", tmp_path / "p.png"
    Image.new("RGB", (8, 4)).save(jpg)
    Image.new("RGB", (6, 2)).save(png)
    gui = _gui([str(jpg), str(png)])
    right_click_menu._auto_orient(gui)  # noqa: SLF001
    with Image.open(tmp_path / "p_oriented.png") as first, \
            Image.open(tmp_path / "p_oriented_1.png") as second:
        assert (first.size, second.size) == ((8, 4), (6, 2))
    assert gui.main_window.toast.calls == [("success", "Oriented 2 photo(s)")]


def _combine(monkeypatch, paths, dest):
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(right_click_menu, "selected_in_view_order", lambda _gui: list(paths))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a, **_k: (str(dest), ""))
    toast = _Toast()
    toast.error = lambda msg: toast.calls.append(("error", msg))
    right_click_menu._combine_multipage(  # noqa: SLF001
        SimpleNamespace(main_window=SimpleNamespace(toast=toast)))
    return toast.calls


def test_combine_pages_reports_the_document(qapp, tmp_path, monkeypatch):
    pages = []
    for i in range(2):
        page = tmp_path / f"p{i}.png"
        Image.new("RGB", (8, 8)).save(page)
        pages.append(page)
    calls = _combine(monkeypatch, pages, tmp_path / "doc.pdf")
    assert calls == [("success", "Combined 2 pages → doc.pdf")]
    assert (tmp_path / "doc.pdf").stat().st_size > 0


def test_combine_pages_reports_an_image_over_the_pixel_limit(qapp, tmp_path, monkeypatch, caplog):
    """DecompressionBombError is no OSError: it escaped the slot instead of being reported."""
    page = tmp_path / "huge.png"
    Image.new("RGB", (64, 64)).save(page)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with caplog.at_level("WARNING", logger="Imervue"):
        calls = _combine(monkeypatch, [page], tmp_path / "doc.pdf")
    ((kind, _msg),) = calls
    assert kind == "error"
    assert not (tmp_path / "doc.pdf").exists()
    assert any("Combining 1 pages" in r.getMessage() for r in caplog.records)


def test_show_in_explorer_reveals_the_shown_picture(qapp, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMenu
    revealed = []
    monkeypatch.setattr(right_click_menu, "reveal_or_warn", revealed.append)
    path = str(tmp_path / "a.png")
    view = SimpleNamespace(model=SimpleNamespace(images=[path]), deep_zoom=True, current_index=0)
    menu = QMenu()
    try:
        right_click_menu._show_in_explorer_action(view, menu)  # noqa: SLF001
        (action,) = menu.actions()
        action.trigger()
    finally:
        menu.deleteLater()
    assert revealed == [path]


def test_set_as_wallpaper_runs_off_the_gui_thread(qapp, monkeypatch, tmp_path, pump_until):
    """A RAW is developed into a JPEG copy first, which must not freeze the window."""
    import threading

    from PySide6.QtWidgets import QMenu
    calls = []
    monkeypatch.setattr(right_click_menu, "set_desktop_wallpaper",
                        lambda path: calls.append((path, threading.current_thread())))
    path = str(tmp_path / "a.nef")
    view = SimpleNamespace(model=SimpleNamespace(images=[path]), deep_zoom=True, current_index=0)
    menu = QMenu()
    try:
        right_click_menu._set_wallpaper_action(view, menu)  # noqa: SLF001
        (action,) = menu.actions()
        action.trigger()
        assert pump_until(lambda: calls)
    finally:
        menu.deleteLater()
    ((wallpaper_path, thread),) = calls
    assert wallpaper_path == path
    assert thread is not threading.main_thread()
