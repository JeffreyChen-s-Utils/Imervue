"""Characterisation tests for the manga menu's three config dialogs.

Pins each dialog's form rows (labels, widget types, ranges, decimals, steps,
defaults), the auto-centre toggle driving the centre spin boxes, the OK /
Cancel box, and the options / values each dialog returns, so sharing their
construction helpers cannot change a control or a returned value.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QPushButton,
)

from Imervue.paint import manga_menu as mod
from Imervue.paint.manga_menu import FlashConfigDialog, PanelCutterDialog, SpeedlineConfigDialog


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


def _rows(dialog):
    form = dialog.layout()
    assert isinstance(form, QFormLayout)
    rows = []
    for r in range(form.rowCount()):
        label = form.itemAt(r, QFormLayout.ItemRole.LabelRole)
        field = form.itemAt(r, QFormLayout.ItemRole.FieldRole)
        span = form.itemAt(r, QFormLayout.ItemRole.SpanningRole)
        text = label.widget().text() if label is not None else None
        item = field if field is not None else span
        rows.append((text, item.widget() or item.layout()))
    return rows


def _assert_spin(spin, kind, *numbers):
    """``kind`` name, then (min, max, value) — plus (decimals, step) for a double spin."""
    assert type(spin).__name__ == kind
    shape = (spin.minimum(), spin.maximum(), spin.value())
    if isinstance(spin, QDoubleSpinBox):
        shape += (spin.decimals(), spin.singleStep())
    assert shape == pytest.approx(numbers)


def _ok_cancel(dialog, rows):
    box = rows[-1][1]
    assert isinstance(box, QDialogButtonBox)
    assert box.standardButtons() == (QDialogButtonBox.StandardButton.Ok
                                     | QDialogButtonBox.StandardButton.Cancel)
    return box


def test_panel_cutter(qapp):
    dlg = PanelCutterDialog()
    try:
        rows = _rows(dlg)
        assert [t for t, _ in rows[:-1]] == ["Rows", "Columns", "Gutter", "Border", "Margin"]
        expected = [(1, 12, mod.PANEL_ROWS_DEFAULT), (1, 12, mod.PANEL_COLS_DEFAULT),
                    (0, 200, mod.PANEL_GUTTER_DEFAULT), (0, 20, mod.PANEL_BORDER_DEFAULT),
                    (0, 200, mod.PANEL_MARGIN_DEFAULT)]
        for (_label, spin), numbers in zip(rows[:-1], expected, strict=True):
            _assert_spin(spin, "QSpinBox", *numbers)
        _ok_cancel(dlg, rows)
        rows[0][1].setValue(3)
        assert dlg.values() == {
            "rows": 3, "cols": mod.PANEL_COLS_DEFAULT, "gutter": mod.PANEL_GUTTER_DEFAULT,
            "border": mod.PANEL_BORDER_DEFAULT, "margin": mod.PANEL_MARGIN_DEFAULT}
        assert dlg.windowTitle() == "Panel Cutter…"
    finally:
        dlg.deleteLater()


def _center_row(rows, dialog):
    checkbox_row = next(i for i, (_t, w) in enumerate(rows) if isinstance(w, QCheckBox))
    assert rows[checkbox_row][1] is dialog._auto_center  # noqa: SLF001
    text, layout = rows[checkbox_row + 1]
    assert text == "Centre (x, y)" and isinstance(layout, QHBoxLayout)
    cx, cy = (layout.itemAt(i).widget() for i in range(2))
    assert (cx, cy) == (dialog._center_x, dialog._center_y)  # noqa: SLF001
    return checkbox_row, cx, cy


@pytest.mark.parametrize("factory", [
    lambda: SpeedlineConfigDialog("burst", (60, 100)),
    lambda: FlashConfigDialog((60, 100)),
])
def test_centre_controls(qapp, factory):
    dlg = factory()
    try:
        rows = _rows(dlg)
        _i, cx, cy = _center_row(rows, dlg)
        assert dlg._auto_center.isChecked()  # noqa: SLF001
        assert (cx.minimum(), cx.maximum(), cx.value()) == (0, 99, 50)
        assert (cy.minimum(), cy.maximum(), cy.value()) == (0, 59, 30)
        assert not cx.isEnabled() and not cy.isEnabled()
        assert dlg.options().center is None
        dlg._auto_center.setChecked(False)  # noqa: SLF001
        assert cx.isEnabled() and cy.isEnabled()
        cx.setValue(7)
        cy.setValue(9)
        assert dlg.options().center == (7, 9)
        dlg._auto_center.setChecked(True)  # noqa: SLF001
        assert not cx.isEnabled()
        _ok_cancel(dlg, rows)
    finally:
        dlg.deleteLater()


def test_centre_controls_on_a_one_pixel_canvas(qapp):
    dlg = FlashConfigDialog((1, 1))
    try:
        assert (dlg._center_x.maximum(), dlg._center_x.value()) == (1, 0)  # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_speedline_dialog(qapp):
    from Imervue.paint import speedlines as sl
    dlg = SpeedlineConfigDialog("not-a-kind", (60, 100))
    try:
        rows = _rows(dlg)
        assert [t for t, _ in rows] == [
            "Kind", "Count", "Thickness", None, "Centre (x, y)", "Angle (°, parallel)",
            "Inner radius (burst)", "Jitter", "Colour", "Seed", None]
        kind = rows[0][1]
        assert isinstance(kind, QComboBox)
        assert [kind.itemText(i) for i in range(kind.count())] == list(sl.SPEEDLINE_KINDS)
        assert kind.currentText() == sl.SPEEDLINE_KINDS[0]
        _assert_spin(rows[1][1], "QSpinBox", sl.LINE_COUNT_MIN, sl.LINE_COUNT_MAX, sl.DEFAULT_LINE_COUNT)
        _assert_spin(rows[2][1], "QSpinBox", sl.LINE_THICKNESS_MIN, sl.LINE_THICKNESS_MAX, sl.DEFAULT_LINE_THICKNESS)
        _assert_spin(rows[5][1], "QDoubleSpinBox", -180.0, 180.0, 0.0, 1, 1.0)
        _assert_spin(rows[6][1], "QDoubleSpinBox", 0.0, 0.95, sl.DEFAULT_BURST_RADIUS_RATIO, 2, 0.05)
        _assert_spin(rows[7][1], "QDoubleSpinBox", 0.0, 1.0, 0.4, 2, 0.05)
        assert isinstance(rows[8][1], QPushButton)
        assert rows[8][1].property("rgba") == (0, 0, 0, 255)
        _assert_spin(rows[9][1], "QSpinBox", 0, 1_000_000, 0)
        opts = dlg.options()
        assert (opts.kind, opts.count, opts.thickness, opts.color, opts.seed) == (
            sl.SPEEDLINE_KINDS[0], sl.DEFAULT_LINE_COUNT, sl.DEFAULT_LINE_THICKNESS,
            (0, 0, 0, 255), 0)
        assert (opts.angle_deg, opts.jitter) == pytest.approx((0.0, 0.4))
        assert opts.inner_radius_ratio == pytest.approx(sl.DEFAULT_BURST_RADIUS_RATIO)
    finally:
        dlg.deleteLater()


def test_speedline_dialog_keeps_a_known_kind(qapp):
    from Imervue.paint import speedlines as sl
    kind = sl.SPEEDLINE_KINDS[-1]
    dlg = SpeedlineConfigDialog(kind, (10, 10))
    try:
        assert dlg.options().kind == kind
    finally:
        dlg.deleteLater()


def test_flash_dialog(qapp):
    from Imervue.paint import flash_effect as fe
    dlg = FlashConfigDialog((60, 100))
    try:
        rows = _rows(dlg)
        assert [t for t, _ in rows] == [
            "Spikes", "Outer radius", "Inner radius", "Halo radius", "Halo opacity", None,
            "Centre (x, y)", "Rotation (°)", "Colour", None]
        _assert_spin(rows[0][1], "QSpinBox", fe.FLASH_SPIKES_MIN, fe.FLASH_SPIKES_MAX, fe.DEFAULT_FLASH_SPIKES)
        _assert_spin(rows[1][1], "QDoubleSpinBox", 0.06, 1.5, fe.DEFAULT_OUTER_RADIUS_RATIO, 2, 0.05)
        _assert_spin(rows[2][1], "QDoubleSpinBox", 0.0, 1.4, fe.DEFAULT_INNER_RADIUS_RATIO, 2, 0.05)
        _assert_spin(rows[3][1], "QDoubleSpinBox", 0.0, 2.0, fe.DEFAULT_HALO_RADIUS_RATIO, 2, 0.05)
        _assert_spin(rows[4][1], "QDoubleSpinBox", 0.0, 1.0, fe.DEFAULT_HALO_OPACITY, 2, 0.05)
        _assert_spin(rows[7][1], "QDoubleSpinBox", -180.0, 180.0, 0.0, 1, 1.0)
        assert rows[8][1].property("rgba") == (255, 230, 80, 255)
        opts = dlg.options()
        assert opts.color == (255, 230, 80)
        assert opts.spikes == fe.DEFAULT_FLASH_SPIKES
        assert opts.rotation_deg == pytest.approx(0.0)
    finally:
        dlg.deleteLater()


def test_ok_and_cancel_close_the_dialogs(qapp):
    for dlg in (PanelCutterDialog(), SpeedlineConfigDialog("burst", (8, 8)),
                FlashConfigDialog((8, 8))):
        try:
            box = _ok_cancel(dlg, _rows(dlg))
            results = []
            dlg.finished.connect(results.append)
            dlg.open()
            box.button(QDialogButtonBox.StandardButton.Ok).click()
            dlg.open()
            box.button(QDialogButtonBox.StandardButton.Cancel).click()
            assert results == [1, 0]
        finally:
            dlg.deleteLater()
