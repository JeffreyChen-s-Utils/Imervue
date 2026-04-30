"""Filter menu — apply Imervue's image filters to the active paint layer.

Each entry runs the underlying pure-numpy filter from
``Imervue.image.*`` against the active layer's image, then composites
the result back through the active selection so filters respect the
marquee. Filters share a single :class:`FilterParametersDialog` that
renders sliders / checkboxes from a declarative spec — adding a new
filter is one entry in :data:`FILTER_SPECS`.

The menu is built lazily on first show so the heavy filter modules
aren't imported at workspace startup. The Filter menu is added to the
PaintWorkspace's menu bar in
:func:`Imervue.paint.paint_workspace.PaintWorkspace.__init__`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMenu,
    QSlider,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


# ---------------------------------------------------------------------------
# Parameter spec — one entry per slider / checkbox / combo on a filter dialog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParamSpec:
    name: str             # internal key passed to the filter
    label_key: str        # translation key for the form label
    label_fallback: str
    kind: str             # "int_slider" | "float_slider" | "bool" | "choice"
    minimum: float = 0.0
    maximum: float = 1.0
    default: float | int | bool | str = 0
    step: float = 1.0     # only used by float_slider (slider int → /step)
    choices: tuple[tuple[str, str, str], ...] = ()   # (id, label_key, fallback)


@dataclass(frozen=True)
class FilterSpec:
    """A single Filter menu entry."""

    key: str
    label_key: str
    label_fallback: str
    parameters: tuple[ParamSpec, ...]
    apply_fn: Callable[[np.ndarray, dict[str, Any]], np.ndarray]


# ---------------------------------------------------------------------------
# Built-in filter set — adapters around the pure-numpy modules in
# ``Imervue/image/*``. Each adapter takes (arr, params dict) and returns the
# transformed array. Imports are local so heavy modules (numpy + image)
# aren't loaded until the user opens the dialog.
# ---------------------------------------------------------------------------


def _apply_levels(arr: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    from Imervue.image.levels import LevelsOptions, apply_levels
    return apply_levels(arr, LevelsOptions(
        enabled=True,
        black=int(params["black"]),
        white=int(params["white"]),
        gamma=float(params["gamma"]),
    ))


def _apply_posterize(arr: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    from Imervue.image.posterize import PosterizeOptions, apply_posterize
    return apply_posterize(arr, PosterizeOptions(
        enabled=True,
        levels=int(params["levels"]),
    ))


def _apply_threshold(arr: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    from Imervue.image.posterize import ThresholdOptions, apply_threshold
    return apply_threshold(arr, ThresholdOptions(
        enabled=True,
        level=int(params["level"]),
    ))


def _apply_auto_balance(arr: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    from Imervue.image.auto_color_balance import AutoBalanceOptions, auto_balance
    return auto_balance(arr, AutoBalanceOptions(
        method=str(params["method"]),
        intensity=float(params["intensity"]),
    ))


def _apply_film_grain(arr: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    from Imervue.image.film_grain import FilmGrainOptions, apply_film_grain
    return apply_film_grain(arr, FilmGrainOptions(
        enabled=True,
        intensity=float(params["intensity"]),
        size=int(params["size"]),
    ))


FILTER_SPECS: tuple[FilterSpec, ...] = (
    FilterSpec(
        key="levels",
        label_key="paint_filter_levels",
        label_fallback="Levels…",
        parameters=(
            ParamSpec("black", "paint_filter_levels_black", "Black point",
                      "int_slider", 0, 254, 0),
            ParamSpec("white", "paint_filter_levels_white", "White point",
                      "int_slider", 1, 255, 255),
            ParamSpec("gamma", "paint_filter_levels_gamma", "Gamma",
                      "float_slider", 0.1, 5.0, 1.0, step=0.05),
        ),
        apply_fn=_apply_levels,
    ),
    FilterSpec(
        key="posterize",
        label_key="paint_filter_posterize",
        label_fallback="Posterize…",
        parameters=(
            ParamSpec("levels", "paint_filter_posterize_levels", "Levels per channel",
                      "int_slider", 2, 64, 4),
        ),
        apply_fn=_apply_posterize,
    ),
    FilterSpec(
        key="threshold",
        label_key="paint_filter_threshold",
        label_fallback="Threshold…",
        parameters=(
            ParamSpec("level", "paint_filter_threshold_level", "Threshold level",
                      "int_slider", 0, 255, 128),
        ),
        apply_fn=_apply_threshold,
    ),
    FilterSpec(
        key="auto_balance",
        label_key="paint_filter_auto_balance",
        label_fallback="Auto Color Balance…",
        parameters=(
            ParamSpec("method", "paint_filter_auto_balance_method", "Method",
                      "choice", default="percentile_stretch",
                      choices=(
                          ("gray_world", "auto_balance_method_gray_world", "Gray-world"),
                          ("white_patch", "auto_balance_method_white_patch", "White-patch"),
                          ("percentile_stretch",
                           "auto_balance_method_percentile_stretch",
                           "Auto-levels (percentile)"),
                          ("simplified_retinex",
                           "auto_balance_method_simplified_retinex",
                           "Retinex"),
                      )),
            ParamSpec("intensity", "paint_filter_auto_balance_intensity", "Intensity",
                      "float_slider", 0.0, 1.0, 1.0, step=0.05),
        ),
        apply_fn=_apply_auto_balance,
    ),
    FilterSpec(
        key="film_grain",
        label_key="paint_filter_film_grain",
        label_fallback="Film Grain…",
        parameters=(
            ParamSpec("intensity", "paint_filter_film_grain_intensity", "Intensity",
                      "float_slider", 0.0, 1.0, 0.3, step=0.05),
            ParamSpec("size", "paint_filter_film_grain_size", "Grain size",
                      "int_slider", 1, 12, 2),
        ),
        apply_fn=_apply_film_grain,
    ),
)


# ---------------------------------------------------------------------------
# Filter parameters dialog — one widget per ParamSpec
# ---------------------------------------------------------------------------


class FilterParametersDialog(QDialog):
    """Modal dialog that collects parameter values for a FilterSpec."""

    def __init__(self, spec: FilterSpec, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get(spec.label_key, spec.label_fallback))
        self.setMinimumWidth(420)
        self._spec = spec
        self._widgets: dict[str, Any] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()
        for param in spec.parameters:
            widget = self._build_widget(param, lang)
            form.addRow(lang.get(param.label_key, param.label_fallback), widget)
            self._widgets[param.name] = widget
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_widget(self, param: ParamSpec, lang: dict):  # pragma: no cover - Qt UI
        if param.kind == "int_slider":
            slider = _slider(int(param.minimum), int(param.maximum), int(param.default))
            return slider
        if param.kind == "float_slider":
            ratio = max(1, int(round(1.0 / param.step)))
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(int(param.minimum * ratio), int(param.maximum * ratio))
            slider.setValue(int(float(param.default) * ratio))
            slider.setProperty("ratio", ratio)
            return slider
        if param.kind == "bool":
            box = QCheckBox()
            box.setChecked(bool(param.default))
            return box
        if param.kind == "choice":
            combo = QComboBox()
            for choice_id, choice_key, fallback in param.choices:
                combo.addItem(lang.get(choice_key, fallback), userData=choice_id)
            idx = combo.findData(param.default)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            return combo
        raise ValueError(f"unknown param kind {param.kind!r}")

    def values(self) -> dict[str, Any]:  # pragma: no cover - Qt UI
        out: dict[str, Any] = {}
        for param in self._spec.parameters:
            widget = self._widgets[param.name]
            if param.kind == "int_slider":
                out[param.name] = widget.value()
            elif param.kind == "float_slider":
                ratio = widget.property("ratio") or 1
                out[param.name] = widget.value() / ratio
            elif param.kind == "bool":
                out[param.name] = widget.isChecked()
            elif param.kind == "choice":
                out[param.name] = widget.currentData()
        return out


def _slider(lo: int, hi: int, value: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(value)
    return s


# ---------------------------------------------------------------------------
# Selection-aware application
# ---------------------------------------------------------------------------


def apply_filter_to_layer(
    spec: FilterSpec,
    params: dict[str, Any],
    image: np.ndarray,
    selection: np.ndarray | None,
) -> np.ndarray:
    """Run ``spec.apply_fn`` against ``image``; mask the result to ``selection``.

    The filter is always run on the full image so per-pixel filters that
    sample a neighbourhood don't get edge artefacts at the selection
    boundary. The post-filter image is then alpha-blended back through
    the selection mask: pixels outside stay original.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    filtered = spec.apply_fn(image, params)
    if filtered.shape != image.shape or filtered.dtype != np.uint8:
        raise ValueError(
            f"filter {spec.key!r} returned shape {filtered.shape} "
            f"dtype {filtered.dtype}, expected {image.shape} uint8",
        )
    if selection is None:
        return filtered
    if selection.shape != image.shape[:2]:
        raise ValueError(
            f"selection shape {selection.shape} does not match image {image.shape[:2]}",
        )
    out = image.copy()
    out[selection] = filtered[selection]
    return out


# ---------------------------------------------------------------------------
# Menu construction
# ---------------------------------------------------------------------------


def build_filter_menu(workspace: PaintWorkspace) -> QMenu:
    """Return the Filter menu wired to ``workspace``."""
    lang = language_wrapper.language_word_dict
    menu = QMenu(lang.get("paint_filter_menu", "Filter"), workspace)
    for spec in FILTER_SPECS:
        action = menu.addAction(lang.get(spec.label_key, spec.label_fallback))
        action.triggered.connect(
            lambda _checked=False, s=spec: _run_filter(workspace, s),
        )
    return menu


def _run_filter(workspace: PaintWorkspace, spec: FilterSpec) -> None:  # pragma: no cover - Qt UI
    document = workspace.canvas().document()
    layer = document.active_layer()
    if layer is None:
        return
    dialog = FilterParametersDialog(spec, parent=workspace)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    params = dialog.values()
    try:
        layer.image[...] = apply_filter_to_layer(
            spec, params, layer.image, document.selection(),
        )
    except (ValueError, TypeError) as exc:
        import logging
        logging.getLogger("Imervue.paint.filter_menu").warning(
            "filter %r failed: %s", spec.key, exc,
        )
        return
    document.invalidate_composite()
