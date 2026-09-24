"""Tests for the PNG to Icon Converter plugin."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from png_to_icon import plugin_class
from png_to_icon.icon_converter_plugin import (
    OUTPUT_DIR_NAME,
    SIZES,
    IconConverterPlugin,
    icon_output_dir,
    write_icon_set,
)

_MODULE = "png_to_icon.icon_converter_plugin"


def _make_plugin(images: list[str] | None = None) -> IconConverterPlugin:
    main_window = MagicMock()
    viewer = main_window.viewer
    viewer.deep_zoom = bool(images)
    viewer.model.images = images or []
    viewer.current_index = 0
    return IconConverterPlugin(main_window)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_package_exposes_plugin_class():
    assert plugin_class is IconConverterPlugin


def test_icon_output_dir_is_sibling_folder(tmp_path):
    assert icon_output_dir(tmp_path / "a.png") == tmp_path / OUTPUT_DIR_NAME


def test_write_icon_set_writes_png_and_ico_per_size(sample_png):
    written = write_icon_set(sample_png)
    assert len(written) == 2 * len(SIZES)
    for size in SIZES:
        png = icon_output_dir(sample_png) / f"icon_{size}x{size}.png"
        ico = icon_output_dir(sample_png) / f"icon_{size}x{size}.ico"
        assert png in written
        assert ico in written
        with Image.open(png) as image:
            assert image.size == (size, size)
            assert image.mode == "RGBA"
        with Image.open(ico) as icon:
            assert icon.format == "ICO"
            assert icon.size == (size, size)


def test_write_icon_set_single_size_keeps_order(sample_png):
    written = write_icon_set(sample_png, sizes=(1,))
    assert [path.name for path in written] == ["icon_1x1.png", "icon_1x1.ico"]


def test_write_icon_set_accepts_path_and_existing_output_dir(sample_png):
    icon_output_dir(sample_png).mkdir()
    written = write_icon_set(Path(sample_png), sizes=(16,))
    assert all(path.is_file() for path in written)


@pytest.mark.parametrize("sizes", [(), (0,), (16, -1)])
def test_write_icon_set_rejects_bad_sizes(sample_png, sizes):
    with pytest.raises(ValueError, match="positive"):
        write_icon_set(sample_png, sizes=sizes)
    assert not icon_output_dir(sample_png).exists()


def test_write_icon_set_raises_for_unreadable_source(tmp_path):
    bogus = tmp_path / "not_an_image.png"
    bogus.write_bytes(b"not a png")
    with pytest.raises(OSError):
        write_icon_set(bogus)


# ---------------------------------------------------------------------------
# Qt shell
# ---------------------------------------------------------------------------


def test_plugin_menu_gets_submenu_with_two_actions():
    plugin = _make_plugin()
    plugin_menu = MagicMock()
    plugin.on_build_menu_bar(plugin_menu)
    plugin_menu.addMenu.assert_called_once()
    assert plugin_menu.addMenu.return_value.addAction.call_count == 2


def test_context_menu_skipped_without_image():
    plugin = _make_plugin()
    menu = MagicMock()
    plugin.on_build_context_menu(menu, plugin.viewer)
    menu.addAction.assert_not_called()


def test_context_menu_added_with_image(sample_png):
    plugin = _make_plugin([sample_png])
    menu = MagicMock()
    plugin.on_build_context_menu(menu, plugin.viewer)
    menu.addAction.assert_called_once()


def test_convert_current_warns_without_image(monkeypatch):
    box = MagicMock()
    monkeypatch.setattr(f"{_MODULE}.QMessageBox", box)
    _make_plugin()._convert_current()
    box.warning.assert_called_once()
    box.information.assert_not_called()


def test_convert_current_writes_icons(monkeypatch, sample_png):
    box = MagicMock()
    monkeypatch.setattr(f"{_MODULE}.QMessageBox", box)
    _make_plugin([sample_png])._convert_current()
    box.information.assert_called_once()
    assert (icon_output_dir(sample_png) / "icon_256x256.ico").is_file()


def test_convert_reports_failure(monkeypatch, tmp_path):
    box = MagicMock()
    monkeypatch.setattr(f"{_MODULE}.QMessageBox", box)
    bogus = tmp_path / "broken.png"
    bogus.write_bytes(b"broken")
    _make_plugin()._convert_to_icon(str(bogus))
    box.critical.assert_called_once()
    box.information.assert_not_called()


def test_select_and_convert_uses_chosen_file(monkeypatch, sample_png):
    box = MagicMock()
    dialog = MagicMock()
    dialog.getOpenFileName.return_value = (sample_png, "PNG Files (*.png)")
    monkeypatch.setattr(f"{_MODULE}.QMessageBox", box)
    monkeypatch.setattr(f"{_MODULE}.QFileDialog", dialog)
    _make_plugin()._select_and_convert()
    box.information.assert_called_once()


def test_select_and_convert_cancelled_does_nothing(monkeypatch):
    box = MagicMock()
    dialog = MagicMock()
    dialog.getOpenFileName.return_value = ("", "")
    monkeypatch.setattr(f"{_MODULE}.QMessageBox", box)
    monkeypatch.setattr(f"{_MODULE}.QFileDialog", dialog)
    _make_plugin()._select_and_convert()
    box.information.assert_not_called()
    box.critical.assert_not_called()


def test_translations_share_the_english_keys():
    translations = _make_plugin().get_translations()
    english = set(translations["English"])
    for language, words in translations.items():
        assert set(words) == english, language


def test_icon_of_a_tagged_photo_is_upright(tmp_path):
    """The stored left half is red; tag 6 (rotate 90 CW to view) puts it on top."""
    from png_to_icon.icon_converter_plugin import write_icon_set
    exif = Image.Exif()
    exif[0x0112] = 6
    src = tmp_path / "portrait.png"
    img = Image.new("RGB", (40, 20), (0, 0, 255))
    img.paste((255, 0, 0), (0, 0, 20, 20))
    img.save(src, exif=exif)
    png = next(p for p in write_icon_set(src, sizes=(16,)) if p.suffix == ".png")
    with Image.open(png) as icon:
        top, bottom = icon.convert("RGB").getpixel((8, 2)), icon.convert("RGB").getpixel((8, 13))
    assert top[0] > 200 and bottom[2] > 200
