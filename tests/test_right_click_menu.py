"""Tests for right-click menu actions that write files."""
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
