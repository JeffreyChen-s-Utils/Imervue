"""Parameter slider dock for the Puppet workspace.

One row per parameter: label + horizontal QSlider + numeric label.
Slider drag pushes a float into the bound canvas via
``set_parameter_value``. The dock listens to the canvas's
``parameters_changed`` signal so the next document load (or a
``reset_parameters`` call) repopulates / re-syncs the sliders without
the workspace having to wire that up.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from puppet.canvas import PuppetCanvas
    from puppet.document import Parameter


# How many integer steps each slider holds — finer than the slider's
# default 100 so warps and rotations feel smooth.
_SLIDER_STEPS: int = 1000


class ParameterDock(QDockWidget):
    """Right-dockable panel with one slider per parameter."""

    value_changed = Signal(str, float)
    """Emitted when the user moves a slider — ``(param_id, value)``.

    The dock also pushes into the bound canvas directly so consumers
    who only care about the rendered output don't need to subscribe.
    """

    def __init__(self, canvas: PuppetCanvas, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("puppet_parameters_dock", "Parameters"), parent)
        self._canvas = canvas
        self._sliders: dict[str, QSlider] = {}
        self._value_labels: dict[str, QLabel] = {}
        self._inner = QWidget()
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)
        scroll = QScrollArea()
        scroll.setWidget(self._inner)
        scroll.setWidgetResizable(True)
        self.setWidget(scroll)

        canvas.parameters_changed.connect(self._rebuild_from_canvas)
        canvas.document_loaded.connect(self._rebuild_from_canvas)
        self._rebuild_from_canvas()

    # ---- public ---------------------------------------------------------

    def slider_for(self, param_id: str) -> QSlider | None:
        return self._sliders.get(param_id)

    # ---- rebuild --------------------------------------------------------

    def _rebuild_from_canvas(self) -> None:
        document = self._canvas.document()
        self._clear_rows()
        if document is None or not document.parameters:
            self._layout.addWidget(self._build_empty_state())
            return
        values = self._canvas.parameter_values()
        for param in document.parameters:
            row, slider, value_label = self._build_row(
                param, values.get(param.id, param.default),
            )
            self._sliders[param.id] = slider
            self._value_labels[param.id] = value_label
            self._layout.addWidget(row)
        self._layout.addWidget(self._build_reset_button())
        self._layout.addStretch(1)

    def _clear_rows(self) -> None:
        self._sliders.clear()
        self._value_labels.clear()
        # Walk in reverse so widget removal doesn't shift indices.
        for i in range(self._layout.count() - 1, -1, -1):
            item = self._layout.takeAt(i)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _build_empty_state(self) -> QLabel:
        lang = language_wrapper.language_word_dict
        label = QLabel(
            lang.get(
                "puppet_parameters_empty",
                "No parameters yet — load a puppet with parameters to see sliders here.",
            ),
        )
        label.setWordWrap(True)
        label.setStyleSheet("color: #888; padding: 8px;")
        return label

    def _build_row(
        self, param: Parameter, value: float,
    ) -> tuple[QWidget, QSlider, QLabel]:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        name = QLabel(param.id)
        name.setMinimumWidth(140)
        row_layout.addWidget(name)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, _SLIDER_STEPS)
        slider.setValue(_value_to_step(param, value))
        slider.valueChanged.connect(
            lambda step, p=param: self._on_slider_changed(p, step),
        )
        row_layout.addWidget(slider, stretch=1)

        value_label = QLabel(_format_value(value))
        value_label.setMinimumWidth(60)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(value_label)

        return row, slider, value_label

    def _build_reset_button(self) -> QPushButton:
        lang = language_wrapper.language_word_dict
        btn = QPushButton(lang.get("puppet_parameters_reset", "Reset all"))
        btn.clicked.connect(self._reset_all)
        return btn

    # ---- slots ----------------------------------------------------------

    def _on_slider_changed(self, param: Parameter, step: int) -> None:
        value = _step_to_value(param, step)
        self._value_labels[param.id].setText(_format_value(value))
        self._canvas.set_parameter_value(param.id, value)
        self.value_changed.emit(param.id, value)

    def _reset_all(self) -> None:
        self._canvas.reset_parameters()
        # The canvas emits parameters_changed → rebuild syncs sliders.


def _value_to_step(param: Parameter, value: float) -> int:
    span = param.max - param.min
    if span <= 0:
        return 0
    norm = (float(value) - param.min) / span
    return max(0, min(_SLIDER_STEPS, int(round(norm * _SLIDER_STEPS))))


def _step_to_value(param: Parameter, step: int) -> float:
    if _SLIDER_STEPS == 0:
        return param.min
    norm = step / _SLIDER_STEPS
    return param.min + (param.max - param.min) * norm


def _format_value(value: float) -> str:
    return f"{value:.2f}"
