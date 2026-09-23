"""A slider and a spin box that edit the same integer.

Several panels pair a ``QSlider`` with a ``QSpinBox`` and keep the two in
step by hand. :func:`link_slider_spin` does that once: moving either widget
updates the other with its signals blocked (so the change is not echoed
back) and calls ``on_change`` exactly once per user edit.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSlider, QSpinBox, QWidget

_SPIN_WIDTH = 70
_ROW_SPACING = 6
# Narrow side panels (Develop / Modify) use a tighter row.
_COMPACT_SPIN_WIDTH = 60
_COMPACT_ROW_SPACING = 4


def link_slider_spin(
    slider: QSlider,
    spin: QSpinBox,
    on_change: Callable[[int], None] | None = None,
) -> None:
    """Keep *slider* and *spin* showing the same value; report edits to *on_change*."""

    def _follow(source_value: int, partner: QSlider | QSpinBox) -> None:
        partner.blockSignals(True)
        partner.setValue(source_value)
        partner.blockSignals(False)
        if on_change is not None:
            on_change(source_value)

    slider.valueChanged.connect(lambda v: _follow(v, spin))
    spin.valueChanged.connect(lambda v: _follow(v, slider))


def make_slider_spin(
    parent: QWidget | None,
    minimum: int,
    maximum: int,
    value: int,
    *,
    on_change: Callable[[int], None] | None = None,
    suffix: str = "",
    compact: bool = False,
) -> tuple[QSlider, QSpinBox, QHBoxLayout]:
    """Build a linked horizontal slider + spin box row for ``[minimum, maximum]``.

    Returns the slider, the spin box and the row layout holding them; the
    slider takes the spare width. ``compact`` narrows the spin box and the
    gap for tight side panels.
    """
    spin_width = _COMPACT_SPIN_WIDTH if compact else _SPIN_WIDTH
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(_COMPACT_ROW_SPACING if compact else _ROW_SPACING)

    slider = QSlider(Qt.Orientation.Horizontal, parent)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    row.addWidget(slider, 1)

    spin = QSpinBox(parent)
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    if suffix:
        spin.setSuffix(suffix)
    spin.setFixedWidth(spin_width)
    row.addWidget(spin)

    link_slider_spin(slider, spin, on_change)
    return slider, spin, row
