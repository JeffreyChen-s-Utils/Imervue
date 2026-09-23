"""Tests for the Help menu's report and cheat-sheet commands in ``tip_menu``."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QFileDialog

from Imervue.menu import tip_menu


class _Toast:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def info(self, text):
        self.calls.append(("info", text))

    def error(self, text):
        self.calls.append(("error", text))


@pytest.fixture
def ui():
    return SimpleNamespace(toast=_Toast())


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(tip_menu.language_wrapper, "language_word_dict", {})


def _save_to(monkeypatch, path):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a, **_k: (str(path), ""))


def test_cheat_sheet_saved(qapp, ui, monkeypatch, tmp_path):
    out = tmp_path / "keys.pdf"
    _save_to(monkeypatch, out)
    tip_menu._export_cheat_sheet(ui)  # noqa: SLF001
    assert ui.toast.calls == [("info", f"Cheat sheet saved to {out}")]
    assert out.read_bytes().startswith(b"%PDF-")


def test_cheat_sheet_unwritable_target_reports_failure(qapp, ui, monkeypatch, tmp_path):
    out = tmp_path / "missing_dir" / "keys.pdf"
    _save_to(monkeypatch, out)
    tip_menu._export_cheat_sheet(ui)  # noqa: SLF001
    ((kind, text),) = ui.toast.calls
    assert kind == "error" and text.startswith("Export failed: ") and "missing_dir" in text


def test_cheat_sheet_cancelled_does_nothing(qapp, ui, monkeypatch):
    _save_to(monkeypatch, "")
    tip_menu._export_cheat_sheet(ui)  # noqa: SLF001
    assert ui.toast.calls == []
