"""Tests for pasting a clipboard bitmap into the current folder."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtGui import QColor, QImage

from Imervue.gpu_image_view import clipboard_paste as mod
from Imervue.gpu_image_view.images import image_loader


class _Toast:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def info(self, text):
        self.calls.append(("info", text))

    def error(self, text):
        self.calls.append(("error", text))


@pytest.fixture
def view(tmp_path, monkeypatch, fake_clipboard):
    existing = tmp_path / "a.png"
    QImage(4, 4, QImage.Format.Format_RGB32).save(str(existing))
    opened: list[str] = []
    monkeypatch.setattr(image_loader, "open_path", lambda main_gui, path: opened.append(path))
    monkeypatch.setattr(mod.time, "time", lambda: 1_700_000_000.5)
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(QColor("red"))
    fake_clipboard.setImage(img)
    return SimpleNamespace(model=SimpleNamespace(images=[str(existing)]),
                           main_window=SimpleNamespace(toast=_Toast()), opened=opened)


def test_paste_saves_opens_and_lists_the_image(view, tmp_path):
    mod.paste_image_from_clipboard(view)
    saved = tmp_path / "pasted_1700000000.png"
    assert saved.is_file()
    assert view.opened == [str(saved)]
    assert str(saved) in view.model.images
    assert view.main_window.toast.calls == [("info", "Pasted: pasted_1700000000.png")]


def test_two_pastes_in_one_second_keep_both_files(view, tmp_path):
    mod.paste_image_from_clipboard(view)
    mod.paste_image_from_clipboard(view)
    first, second = tmp_path / "pasted_1700000000.png", tmp_path / "pasted_1700000000-1.png"
    assert first.is_file() and second.is_file()
    assert view.opened == [str(first), str(second)]


def test_failed_save_reports_and_opens_nothing(view, tmp_path, monkeypatch):
    monkeypatch.setattr(QImage, "save", lambda *_a, **_k: False)
    before = list(view.model.images)
    mod.paste_image_from_clipboard(view)
    assert view.opened == []
    assert view.model.images == before
    ((kind, text),) = view.main_window.toast.calls
    assert kind == "error" and str(tmp_path) in text


def test_an_empty_clipboard_says_so(view, fake_clipboard):
    fake_clipboard.clear()
    mod.paste_image_from_clipboard(view)
    assert view.opened == []
    assert view.main_window.toast.calls == [("info", "Clipboard does not contain an image")]


def test_no_folder_to_save_into_says_so(view, monkeypatch):
    view.model.images = []
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    monkeypatch.setitem(user_setting_dict, "user_last_folder", "")
    mod.paste_image_from_clipboard(view)
    assert view.opened == []
    assert view.main_window.toast.calls == [
        ("info", "Open a folder first: a pasted image is saved into it")]


def test_the_toast_speaks_the_current_language(view, monkeypatch):
    from Imervue.multi_language.traditional_chinese import traditional_chinese_word_dict
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", traditional_chinese_word_dict)
    mod.paste_image_from_clipboard(view)
    assert view.main_window.toast.calls == [("info", "已貼上：pasted_1700000000.png")]
