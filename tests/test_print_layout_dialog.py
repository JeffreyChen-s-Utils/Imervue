"""Tests for the Print Layout dialog."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QDialog

from Imervue.gui import print_layout_dialog as mod
from Imervue.gui.print_layout_dialog import PrintLayoutDialog
from Imervue.image.print_layout import PT_PER_MM


@pytest.fixture
def exports(monkeypatch):
    """Run the worker inline and record every (layout, output) handed to the PDF writer."""
    written = []
    monkeypatch.setattr(mod, "export_print_pdf", lambda layout, out: written.append((layout, out)))
    monkeypatch.setattr(mod._Worker, "start", mod._Worker.run)  # noqa: SLF001
    return written


@pytest.fixture
def messages(monkeypatch):
    """Record the message boxes instead of showing them."""
    shown = []
    for kind in ("information", "warning"):
        monkeypatch.setattr(mod.QMessageBox, kind,
                            staticmethod(lambda _p, _t, text, kind=kind: shown.append((kind, text))))
    return shown


@pytest.fixture
def dialog(qapp, tmp_path):
    dlg = PrintLayoutDialog(None)
    dlg._out_edit.setText(str(tmp_path / "sheet.pdf"))  # noqa: SLF001
    dlg._files.addItem("a.png")  # noqa: SLF001
    yield dlg
    dlg.deleteLater()


def test_margin_and_gutter_start_at_the_layout_defaults(dialog):
    """The PDF writer always had a 0.5 in margin and a 12 pt gutter; now they show."""
    assert dialog._margin.value() == pytest.approx(12.7)  # noqa: SLF001
    assert dialog._gutter.value() == pytest.approx(4.2)  # noqa: SLF001
    assert dialog._margin.suffix() == " mm"  # noqa: SLF001


def test_the_spacing_reaches_the_pdf_in_points(dialog, exports, messages):
    dialog._margin.setValue(10.0)  # noqa: SLF001
    dialog._gutter.setValue(5.0)  # noqa: SLF001
    dialog._run()  # noqa: SLF001
    ((layout, out),) = exports
    assert layout.margin_pt == pytest.approx(10.0 * PT_PER_MM)
    assert layout.gutter_pt == pytest.approx(5.0 * PT_PER_MM)
    assert layout.image_paths == ["a.png"]
    assert out.endswith("sheet.pdf")
    assert messages == []
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_an_empty_list_is_refused_instead_of_printing_a_blank_page(dialog, exports, messages):
    dialog._files.clear()  # noqa: SLF001
    dialog._run()  # noqa: SLF001
    assert exports == []
    assert messages == [("information", "Add at least one picture to print.")]


def test_spacing_that_leaves_no_room_is_refused(dialog, exports, messages):
    # Nine 30 mm gutters are wider than an A4 page.
    dialog._cols.setValue(10)  # noqa: SLF001
    dialog._gutter.setValue(30.0)  # noqa: SLF001
    dialog._run()  # noqa: SLF001
    assert exports == []
    assert [kind for kind, _text in messages] == ["information"]
    assert "no room" in messages[0][1]


def test_a_failed_export_says_why(dialog, monkeypatch, messages):
    """A failure used to hide the progress bar and nothing else."""
    def fail(_layout, _out):
        raise OSError("disk full")

    monkeypatch.setattr(mod, "export_print_pdf", fail)
    monkeypatch.setattr(mod._Worker, "start", mod._Worker.run)  # noqa: SLF001
    dialog._run()  # noqa: SLF001
    assert messages == [("warning", "Export failed: disk full")]
    assert dialog._run_btn.isEnabled()  # noqa: SLF001
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_a_written_sheet_is_announced(dialog, exports):
    toasts = []
    dialog._ui = SimpleNamespace(toast=SimpleNamespace(info=toasts.append))  # noqa: SLF001
    dialog._run()  # noqa: SLF001
    assert toasts == ["Print layout written: sheet.pdf"]


def test_the_list_starts_with_the_selection_in_view_order(qapp):
    viewer = SimpleNamespace(model=SimpleNamespace(images=["a.png", "b.png", "c.png"]),
                             selected_tiles={"c.png", "a.png"})
    dlg = PrintLayoutDialog(None)
    try:
        dlg._ui = SimpleNamespace(viewer=viewer)  # noqa: SLF001
        dlg._files.clear()  # noqa: SLF001
        dlg._populate_from_viewer()  # noqa: SLF001
        assert [dlg._files.item(i).text() for i in range(dlg._files.count())] == ["a.png", "c.png"]  # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_without_a_selection_every_picture_is_listed(qapp):
    """The list used to stop at the first 64 pictures of the folder."""
    names = [f"{i}.png" for i in range(70)]
    dlg = PrintLayoutDialog(None)
    try:
        dlg._ui = SimpleNamespace(viewer=SimpleNamespace(model=SimpleNamespace(images=names),  # noqa: SLF001
                                                         selected_tiles=set()))
        dlg._populate_from_viewer()  # noqa: SLF001
        assert dlg._files.count() == 70  # noqa: SLF001
    finally:
        dlg.deleteLater()
