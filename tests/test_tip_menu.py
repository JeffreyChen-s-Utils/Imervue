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


def test_cheat_sheet_unexpected_error_propagates(qapp, ui, monkeypatch, tmp_path):
    from Imervue.export import cheat_sheet

    def boom(*_a):
        raise RuntimeError("bug")

    _save_to(monkeypatch, tmp_path / "keys.pdf")
    monkeypatch.setattr(cheat_sheet, "generate_cheat_sheet", boom)
    with pytest.raises(RuntimeError):
        tip_menu._export_cheat_sheet(ui)  # noqa: SLF001
    assert ui.toast.calls == []


def _report_outcome(monkeypatch, outcome):
    from Imervue.system import error_report

    def fake_build():
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(error_report, "build_report", fake_build)


def test_error_report_saved(ui, monkeypatch):
    _report_outcome(monkeypatch, "C:/reports/r.zip")
    tip_menu._generate_error_report(ui)  # noqa: SLF001
    assert ui.toast.calls == [("info", "Support bundle saved to C:/reports/r.zip")]


@pytest.mark.parametrize("exc", [OSError("disk full"), ValueError("bad settings")])
def test_error_report_failure_is_toasted(ui, monkeypatch, exc):
    _report_outcome(monkeypatch, exc)
    tip_menu._generate_error_report(ui)  # noqa: SLF001
    assert ui.toast.calls == [("error", f"Report failed: {exc}")]


def test_error_report_unexpected_error_propagates(ui, monkeypatch):
    _report_outcome(monkeypatch, RuntimeError("bug"))
    with pytest.raises(RuntimeError):
        tip_menu._generate_error_report(ui)  # noqa: SLF001
