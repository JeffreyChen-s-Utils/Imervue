"""Tests for the contact-sheet dialog's render worker: what it reports back."""
from __future__ import annotations

from PIL import Image

from Imervue.export.contact_sheet import ContactSheetOptions
from Imervue.gui.contact_sheet_dialog import _RenderWorker

_OPTS = ContactSheetOptions(rows=1, cols=1, dpi=72)


def _run(images, out):
    reports: list[tuple[str, str]] = []
    worker = _RenderWorker(images, str(out), _OPTS)
    worker.signals.done.connect(lambda path, err: reports.append((path, err)))
    worker.run()
    return reports


def _image(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGB", (8, 8), "blue").save(path)
    return str(path)


def test_success_reports_no_error(qapp, tmp_path):
    out = tmp_path / "sheet.pdf"
    assert _run([_image(tmp_path)], out) == [(str(out), "")]
    assert out.exists()


def test_unwritable_target_reports_the_error(qapp, tmp_path):
    out = tmp_path / "taken.pdf"
    out.mkdir()
    ((path, err),) = _run([_image(tmp_path)], out)
    assert path == str(out) and "taken.pdf" in err


def test_no_images_reports_the_error(qapp, tmp_path):
    ((_path, err),) = _run([], tmp_path / "sheet.pdf")
    assert "at least one image" in err


# ---------------------------------------------------------------------------
# Layout characterisation
# ---------------------------------------------------------------------------

def _items(layout):
    return [layout.itemAt(i).widget() or layout.itemAt(i).layout() for i in range(layout.count())]


def _dialog(monkeypatch):
    from Imervue.gui import contact_sheet_dialog as mod
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})
    return mod.ContactSheetDialog(None)


def test_layout_and_settings_form(qapp, monkeypatch):
    from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLineEdit, QSpinBox

    from Imervue.export.contact_sheet import PAGE_SIZES
    dlg = _dialog(monkeypatch)
    try:
        label, form, buttons = _items(dlg.layout())
        assert label.text() == "0 image(s) will be included."
        assert dlg.windowTitle() == "Contact Sheet PDF"
        assert (dlg.minimumWidth(), dlg.minimumHeight()) == (420, 300)
        assert isinstance(form, QFormLayout) and form.rowCount() == 7
        label_of = [form.itemAt(r, QFormLayout.ItemRole.LabelRole) for r in range(7)]
        field_of = [form.itemAt(r, QFormLayout.ItemRole.FieldRole).widget() for r in range(7)]
        assert [i.widget().text() if i else "" for i in label_of] == [
            "Layout", "Rows", "Columns", "Page Size", "Margin", "", "Title"]
        layout_box, rows, cols, page, margin, caption, title = field_of
        assert layout_box is dlg._layout_combo  # noqa: SLF001
        assert layout_box.currentData() == "default"
        assert rows is dlg._rows_spin and cols is dlg._cols_spin  # noqa: SLF001
        for spin, rng, value, suffix, tip in (
            (rows, (1, 20), 5, "", "Number of image rows per page"),
            (cols, (1, 20), 4, "", "Number of image columns per page"),
            (margin, (0, 50), 10, " mm", "Page margin in millimetres on every side"),
        ):
            assert isinstance(spin, QSpinBox)
            assert ((spin.minimum(), spin.maximum()), spin.value()) == (rng, value)
            assert (spin.suffix(), spin.toolTip()) == (suffix, tip)
        assert margin is dlg._margin_spin  # noqa: SLF001
        assert isinstance(page, QComboBox) and page is dlg._page_combo  # noqa: SLF001
        assert [page.itemText(i) for i in range(page.count())] == list(PAGE_SIZES)
        assert page.toolTip() == "Page format used for the output PDF"
        assert isinstance(caption, QCheckBox) and caption is dlg._caption_check  # noqa: SLF001
        assert caption.text() == "Show filename under each image" and caption.isChecked()
        assert caption.toolTip() == ("Print the filename under each thumbnail — useful for "
                                     "client deliverables, off for clean print proofs")
        assert isinstance(title, QLineEdit) and title is dlg._title_edit  # noqa: SLF001
        assert title.placeholderText() == "Optional title"
        stretch, export, close = _items(buttons)
        assert stretch is None and export is dlg._export_btn  # noqa: SLF001
        assert (export.text(), close.text()) == ("Export PDF…", "Close")
    finally:
        dlg.deleteLater()


def test_buttons_wiring(qapp, monkeypatch):
    from Imervue.gui import contact_sheet_dialog as mod
    calls = []
    monkeypatch.setattr(mod.ContactSheetDialog, "_export", lambda self, images: calls.append(images))
    monkeypatch.setattr(mod.ContactSheetDialog, "_resolve_images", lambda self: ["a.png"])
    dlg = _dialog(monkeypatch)
    try:
        label, _form, buttons = _items(dlg.layout())
        assert label.text() == "1 image(s) will be included."
        _stretch, export, close = _items(buttons)
        export.click()
        assert calls == [["a.png"]]
        dlg.show()
        close.click()
        assert not dlg.isVisible()
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Layout presets (contact_sheet_layouts)
# ---------------------------------------------------------------------------

def test_the_layout_box_lists_custom_then_every_preset(qapp, monkeypatch):
    from Imervue.export.contact_sheet_layouts import LAYOUT_NAMES
    dlg = _dialog(monkeypatch)
    try:
        box = dlg._layout_combo  # noqa: SLF001
        assert [box.itemData(i) for i in range(box.count())] == ["", *LAYOUT_NAMES]
        assert box.itemText(0) == "Custom"
        assert box.itemText(box.findData("compact")) == "Compact — 6 × 8 (48 per page)"
    finally:
        dlg.deleteLater()


def test_picking_a_preset_fills_grid_margin_and_caption(qapp, monkeypatch):
    dlg = _dialog(monkeypatch)
    try:
        box = dlg._layout_combo  # noqa: SLF001
        box.setCurrentIndex(box.findData("editorial"))
        assert (dlg._rows_spin.value(), dlg._cols_spin.value()) == (3, 2)  # noqa: SLF001
        assert dlg._margin_spin.value() == 18  # noqa: SLF001
        assert dlg._caption_check.isChecked()  # noqa: SLF001
        box.setCurrentIndex(box.findData("index"))
        assert (dlg._rows_spin.value(), dlg._cols_spin.value()) == (10, 8)  # noqa: SLF001
        assert not dlg._caption_check.isChecked()  # noqa: SLF001
        assert box.currentData() == "index"                    # filling didn't flip it to Custom
    finally:
        dlg.deleteLater()


def test_editing_a_field_by_hand_makes_the_layout_custom(qapp, monkeypatch):
    dlg = _dialog(monkeypatch)
    try:
        box = dlg._layout_combo  # noqa: SLF001
        box.setCurrentIndex(box.findData("proof"))
        dlg._margin_spin.setValue(11)  # noqa: SLF001
        assert box.currentIndex() == 0
        assert (dlg._rows_spin.value(), dlg._cols_spin.value()) == (6, 5)  # noqa: SLF001
        box.setCurrentIndex(box.findData("compact"))
        dlg._caption_check.setChecked(True)  # noqa: SLF001
        assert box.currentIndex() == 0
        box.setCurrentIndex(0)                                  # picking Custom keeps the values
        assert dlg._rows_spin.value() == 8  # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_layout_labels_are_translated(qapp, monkeypatch):
    from Imervue.gui import contact_sheet_dialog as mod
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {
        "contact_sheet_layout_proof": "校樣", "contact_sheet_layout_entry": "{name} {cols}x{rows}={count}"})
    assert mod.layout_label("proof") == "校樣 5x6=30"
