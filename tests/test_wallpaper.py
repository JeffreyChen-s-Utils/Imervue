"""Tests for ``system/wallpaper``: the commands it runs, the copy it hands over, how it reports failure."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from Imervue.system import wallpaper


def test_macos_passes_the_path_as_an_argument_not_as_script_text(tmp_path):
    hostile = str(tmp_path / 'x" & do shell script "rm -rf ~" & ".png')
    (command,) = wallpaper.wallpaper_commands(hostile, "darwin")
    assert command[0] == "osascript"
    assert command[-1] == os.path.abspath(hostile)
    script = [arg for flag, arg in zip(command[1:-1:2], command[2:-1:2], strict=True) if flag == "-e"]
    assert len(script) == 3
    assert all("rm -rf" not in line for line in script)
    assert "item 1 of argv" in script[1]


def test_gnome_sets_both_light_and_dark_wallpapers_as_file_uris(tmp_path):
    path = tmp_path / "my photo #1.png"
    commands = wallpaper.wallpaper_commands(str(path), "linux")
    uri = Path(os.path.abspath(path)).as_uri()
    assert commands == [
        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
    ]
    assert " " not in uri and "#" not in uri   # percent-encoded, not a broken URI


def test_relative_path_is_made_absolute_so_it_cannot_look_like_an_option():
    (command,) = wallpaper.wallpaper_commands("-rf.png", "darwin")
    assert command[-1] == os.path.abspath("-rf.png")
    assert not command[-1].startswith("-")


@pytest.fixture
def popen_log(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: calls.append(cmd))
    return calls


def test_non_windows_runs_every_command(monkeypatch, popen_log):
    monkeypatch.setattr(sys, "platform", "linux")
    wallpaper.set_desktop_wallpaper("/pics/a.png")
    assert [cmd[3] for cmd in popen_log] == ["picture-uri", "picture-uri-dark"]


def test_missing_helper_is_logged_and_stops(monkeypatch, caplog):
    calls: list = []

    def missing(cmd):
        calls.append(cmd)
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "Popen", missing)
    with caplog.at_level("DEBUG", logger="Imervue"):
        wallpaper.set_desktop_wallpaper("/pics/a.png")
    assert len(calls) == 1
    (record,) = caplog.records
    assert "gsettings" in record.getMessage()
    assert record.exc_info[0] is FileNotFoundError


def test_unexpected_popen_error_propagates(monkeypatch):
    def broken(_cmd):
        raise TypeError("bad argv")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "Popen", broken)
    with pytest.raises(TypeError):
        wallpaper.set_desktop_wallpaper("/pics/a.png")


def _fake_windll(monkeypatch, result):
    import ctypes
    calls: list[tuple] = []

    def spi(*args):
        calls.append(args)
        return result

    monkeypatch.setattr(ctypes, "windll",
                        SimpleNamespace(user32=SimpleNamespace(SystemParametersInfoW=spi)),
                        raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    return calls


def test_windows_calls_system_parameters_info(monkeypatch, caplog, popen_log):
    calls = _fake_windll(monkeypatch, 1)
    with caplog.at_level("DEBUG", logger="Imervue"):
        wallpaper.set_desktop_wallpaper("a.png")
    assert calls == [(0x0014, 0, os.path.abspath("a.png"), 0x03)]
    assert popen_log == []
    assert caplog.records == []


def test_windows_refusal_is_logged(monkeypatch, caplog):
    _fake_windll(monkeypatch, 0)
    with caplog.at_level("DEBUG", logger="Imervue"):
        wallpaper.set_desktop_wallpaper("a.png")
    (record,) = caplog.records
    assert "refused" in record.getMessage()


# --- The copy handed to the desktop ------------------------------------------------------


@pytest.fixture
def copies(tmp_path, monkeypatch):
    folder = tmp_path / "copies"
    monkeypatch.setattr(wallpaper, "_copy_dir", lambda: folder)
    return folder


def _saved(path: Path, colour=(200, 30, 30), mode="RGB", size=(40, 20), **params) -> str:
    Image.new(mode, size, colour).save(path, **params)
    return str(path)


@pytest.mark.parametrize("name", ["a.jpg", "a.JPEG", "a.jfif", "a.png", "a.bmp"])
def test_a_jpeg_png_or_bmp_goes_over_as_it_is(tmp_path, copies, name):
    path = _saved(tmp_path / name)
    assert wallpaper.wallpaper_file(path) == path
    assert not copies.exists()


@pytest.mark.parametrize("name", ["a.tga", "a.qoi", "a.ppm", "a.pcx", "a.webp", "a.tif"])
def test_a_format_the_desktop_may_not_decode_goes_over_as_a_jpeg_copy(tmp_path, copies, name):
    """Windows turned the desktop black for a file it could not decode, and reported success."""
    path = _saved(tmp_path / name)
    copy = Path(wallpaper.wallpaper_file(path))
    assert copy.parent == copies and copy.suffix == ".jpg"
    with Image.open(copy) as img:
        assert (img.format, img.mode, img.size) == ("JPEG", "RGB", (40, 20))
        red, green, blue = img.getpixel((5, 5))
    assert abs(red - 200) <= 6 and green <= 40 and blue <= 40
    assert Path(path).is_file()   # the picture itself is untouched


def test_a_photo_with_an_exif_orientation_goes_over_upright(tmp_path, copies):
    exif = Image.Exif()
    exif[0x0112] = 6
    path = _saved(tmp_path / "phone.jpg", exif=exif)
    copy = wallpaper.wallpaper_file(path)
    assert copy != path
    with Image.open(copy) as img:
        assert img.size == (20, 40)
        assert img.getexif().get(0x0112) is None


def test_transparency_is_laid_on_black(tmp_path, copies):
    path = _saved(tmp_path / "logo.tga", colour=(0, 255, 0, 0), mode="RGBA")
    with Image.open(wallpaper.wallpaper_file(path)) as img:
        assert max(img.getpixel((5, 5))) <= 8


def test_a_sixteen_bit_grey_tiff_keeps_its_brightness(tmp_path, copies):
    path = _saved(tmp_path / "scan.tif", colour=32896, mode="I;16")   # 128 in 8 bits
    with Image.open(wallpaper.wallpaper_file(path)) as img:
        assert abs(img.getpixel((5, 5))[0] - 128) <= 3


def test_the_same_picture_reuses_its_copy(tmp_path, copies, monkeypatch):
    path = _saved(tmp_path / "a.tga")
    first = wallpaper.wallpaper_file(path)
    writes: list = []
    monkeypatch.setattr(wallpaper, "_write_copy", lambda *args: writes.append(args))
    assert wallpaper.wallpaper_file(path) == first
    assert writes == []


def test_only_the_newest_copy_is_kept(tmp_path, copies):
    older = wallpaper.wallpaper_file(_saved(tmp_path / "a.tga"))
    newer = wallpaper.wallpaper_file(_saved(tmp_path / "b.tga"))
    assert [p.name for p in copies.iterdir()] == [Path(newer).name]
    assert not Path(older).exists()


def test_a_picture_saved_again_gets_a_new_copy(tmp_path, copies):
    """A desktop that caches by path would otherwise keep showing the old version."""
    path = tmp_path / "a.tga"
    first = wallpaper.wallpaper_file(_saved(path))
    later = path.stat().st_mtime + 2
    _saved(path, colour=(20, 20, 220))
    os.utime(path, (later, later))
    second = wallpaper.wallpaper_file(str(path))
    assert second != first
    with Image.open(second) as img:
        assert img.getpixel((5, 5))[2] > 180


def test_an_old_copy_still_in_use_is_left_for_next_time(tmp_path, copies, monkeypatch, caplog):
    older = wallpaper.wallpaper_file(_saved(tmp_path / "a.tga"))

    def locked(self, *_args, **_kwargs):
        raise PermissionError(str(self))

    monkeypatch.setattr(Path, "unlink", locked)
    with caplog.at_level("DEBUG", logger="Imervue"):
        newer = wallpaper.wallpaper_file(_saved(tmp_path / "b.tga"))
    assert Path(newer).is_file() and Path(older).is_file()
    assert "old wallpaper copy" in caplog.text


def test_an_unreadable_picture_is_handed_over_as_it_is(tmp_path, copies, caplog):
    path = tmp_path / "broken.tga"
    path.write_bytes(b"not a picture")
    with caplog.at_level("DEBUG", logger="Imervue"):
        assert wallpaper.wallpaper_file(str(path)) == str(path)
    (record,) = [r for r in caplog.records if r.levelname == "WARNING"]
    assert "wallpaper copy" in record.getMessage()
    assert not any(copies.glob("*.part"))


def test_a_copy_folder_that_cant_be_written_hands_over_the_picture(tmp_path, monkeypatch, caplog):
    blocker = tmp_path / "copies"
    blocker.write_bytes(b"a file where the folder should be")
    monkeypatch.setattr(wallpaper, "_copy_dir", lambda: blocker)
    path = _saved(tmp_path / "a.tga")
    with caplog.at_level("DEBUG", logger="Imervue"):
        assert wallpaper.wallpaper_file(path) == path
    assert "wallpaper copy" in caplog.text


def test_windows_is_handed_the_copy(tmp_path, copies, monkeypatch):
    calls = _fake_windll(monkeypatch, 1)
    wallpaper.set_desktop_wallpaper(_saved(tmp_path / "a.tga"))
    ((_, _, handed, _),) = calls
    assert Path(handed).parent == copies and handed.endswith(".jpg")


def test_gnome_is_handed_the_copy(tmp_path, copies, monkeypatch, popen_log):
    monkeypatch.setattr(sys, "platform", "linux")
    wallpaper.set_desktop_wallpaper(_saved(tmp_path / "a.qoi"))
    uris = {cmd[4] for cmd in popen_log}
    (uri,) = uris
    assert uri.startswith(copies.as_uri()) and uri.endswith(".jpg")
