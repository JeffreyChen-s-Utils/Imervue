"""Manga-menu actions for the Paint workspace.

Hosts the comic / manga workflow tools that aren't a per-event
brush — currently the **Panel Cutter** dialog, which slices the
canvas into a regular ``rows × cols`` grid of cells, draws the
gutters into a fresh layer, and lets the user resume painting
inside each cell.

The dialog is intentionally minimal — rows / cols spinners + gutter
+ border slider — so a first-time user can produce a usable manga
template without learning a new vocabulary. Power users can call
:func:`Imervue.paint.manga_panels.panel_grid` directly for
non-uniform layouts.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


PANEL_ROWS_DEFAULT = 4
PANEL_COLS_DEFAULT = 1
PANEL_GUTTER_DEFAULT = 24
PANEL_BORDER_DEFAULT = 4
PANEL_MARGIN_DEFAULT = 32


def populate_manga_menu(workspace: PaintWorkspace) -> None:
    """Attach the Manga-menu actions to ``workspace``."""
    bridge = _MangaMenuBridge(workspace)
    workspace._manga_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "manga")
    lang = language_wrapper.language_word_dict
    action = menu.addAction(
        lang.get("paint_manga_panel_cutter", "Panel Cutter…"),
    )
    action.setShortcut(QKeySequence("Ctrl+Shift+P"))
    action.triggered.connect(bridge.open_panel_cutter)
    menu.addSeparator()
    tone_action = menu.addAction(
        lang.get("paint_manga_toggle_tone_layer", "Toggle Tone Layer"),
    )
    tone_action.triggered.connect(bridge.toggle_tone_layer)
    page_numbers_action = menu.addAction(
        lang.get("paint_manga_stamp_page_numbers", "Stamp Page Numbers"),
    )
    page_numbers_action.triggered.connect(bridge.stamp_page_numbers)
    menu.addSeparator()
    for kind, label_key, fallback in (
        ("radial", "paint_manga_speedlines_radial", "Speedlines: Radial"),
        ("parallel", "paint_manga_speedlines_parallel", "Speedlines: Parallel"),
        ("burst", "paint_manga_speedlines_burst", "Speedlines: Burst"),
    ):
        action = menu.addAction(lang.get(label_key, fallback))
        action.triggered.connect(
            lambda _checked=False, k=kind: bridge.add_speedlines(k),
        )
    flash_action = menu.addAction(
        lang.get("paint_manga_flash", "Action Flash"),
    )
    flash_action.triggered.connect(bridge.add_flash)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _MangaMenuBridge:
    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace

    def open_panel_cutter(self) -> None:  # pragma: no cover - Qt UI
        document = self._workspace.canvas().document()
        if document.shape is None:
            return
        dialog = PanelCutterDialog(parent=self._workspace)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        params = dialog.values()
        commit_panel_layout(self._workspace, params)

    def add_flash(self) -> None:  # pragma: no cover - Qt UI
        """Pop a config dialog, then insert a starburst flash layer.

        The dialog lets the user place the flash off-centre, adjust
        the spike count / radii / colour, or cancel out without
        spawning any layer — matching raster paint apps's "every effect is
        configurable before commit" UX.
        """
        document = self._workspace.canvas().document()
        if document.shape is None:
            return
        h, w = document.shape
        dialog = FlashConfigDialog((h, w), parent=self._workspace)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        commit_flash_layer(self._workspace, dialog.options())

    def add_speedlines(self, kind: str) -> None:  # pragma: no cover - Qt UI
        """Pop a config dialog, then insert a speedline layer.

        The dialog seeds with kind-aware defaults (parallel exposes
        an angle slider, burst exposes the inner-radius ratio); the
        user can move the focus point, adjust count / thickness /
        jitter / colour, or cancel out without spawning a layer.
        """
        document = self._workspace.canvas().document()
        if document.shape is None:
            return
        h, w = document.shape
        dialog = SpeedlineConfigDialog(str(kind), (h, w), parent=self._workspace)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        commit_speedlines_layer(self._workspace, dialog.options())

    def stamp_page_numbers(self) -> None:
        """Drop a "Page N" layer on every page in the active project.

        Silently no-ops when the workspace has no project loaded — a
        single-document edit doesn't need page numbering. The default
        corner / size / margin are used; a follow-up dialog can make
        these tunable.
        """
        from Imervue.paint.page_numbering import stamp_page_numbers as stamp_fn
        project = getattr(self._workspace, "_paint_project", None)
        if project is None or project.page_count == 0:
            return
        stamp_fn(project)
        self._workspace.canvas().update()

    def toggle_tone_layer(self) -> None:
        """Flip the active layer between plain raster and tone-render.

        On → installs default :class:`ToneSettings` so the compositor
        starts producing the dot pattern. Off → drops the tone hint
        and the original soft greys reappear. Re-running the action
        toggles back; the layer pixels are never destructively
        rewritten.
        """
        from Imervue.paint.halftone import ToneSettings
        document = self._workspace.canvas().document()
        layer = document.active_layer()
        if layer is None:
            return
        new_tone = None if layer.tone is not None else ToneSettings()
        if document.set_layer_tone(tone=new_tone):
            self._workspace.canvas().update()


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class PanelCutterDialog(QDialog):
    """Modal dialog collecting rows / cols / gutter / border / margin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            lang.get("paint_manga_panel_cutter", "Panel Cutter…"),
        )
        self.setMinimumWidth(360)

        form = QFormLayout(self)
        self._rows = self._spin(1, 12, PANEL_ROWS_DEFAULT)
        self._cols = self._spin(1, 12, PANEL_COLS_DEFAULT)
        self._gutter = self._spin(0, 200, PANEL_GUTTER_DEFAULT)
        self._border = self._spin(0, 20, PANEL_BORDER_DEFAULT)
        self._margin = self._spin(0, 200, PANEL_MARGIN_DEFAULT)
        form.addRow(lang.get("paint_manga_rows", "Rows"), self._rows)
        form.addRow(lang.get("paint_manga_cols", "Columns"), self._cols)
        form.addRow(lang.get("paint_manga_gutter", "Gutter"), self._gutter)
        form.addRow(lang.get("paint_manga_border", "Border"), self._border)
        form.addRow(lang.get("paint_manga_margin", "Margin"), self._margin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @staticmethod
    def _spin(lo: int, hi: int, default: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(default)
        return s

    def values(self) -> dict[str, int]:
        return {
            "rows": self._rows.value(),
            "cols": self._cols.value(),
            "gutter": self._gutter.value(),
            "border": self._border.value(),
            "margin": self._margin.value(),
        }


# ---------------------------------------------------------------------------
# Commit — pure logic, callable from tests without a dialog
# ---------------------------------------------------------------------------


def commit_speedlines_layer(workspace: PaintWorkspace, options) -> bool:
    """Render ``options`` into a fresh layer on the active document.

    Pure-logic helper — the dialog is the only thing that depends on
    a Qt event loop, so tests can call this directly with a
    :class:`SpeedlineOptions` instance and assert the document state.
    """
    import numpy as np

    from Imervue.paint.speedlines import render_speedlines
    document = workspace.canvas().document()
    if document.shape is None:
        return False
    h, w = document.shape
    rendered = render_speedlines((h, w), options)
    layer = document.add_layer(name=f"Speedlines ({options.kind})")
    np.copyto(layer.image, rendered)
    document.invalidate_composite()
    workspace.canvas().update()
    return True


def commit_flash_layer(workspace: PaintWorkspace, options) -> bool:
    """Render a flash layer from ``options`` onto the active document."""
    import numpy as np

    from Imervue.paint.flash_effect import render_flash
    document = workspace.canvas().document()
    if document.shape is None:
        return False
    h, w = document.shape
    rendered = render_flash((h, w), options)
    layer = document.add_layer(name="Flash")
    np.copyto(layer.image, rendered)
    document.invalidate_composite()
    workspace.canvas().update()
    return True


# ---------------------------------------------------------------------------
# Speedline / Flash config dialogs
# ---------------------------------------------------------------------------


def _color_button(initial: tuple[int, int, int, int]) -> QPushButton:
    """Return a swatch button that pops a colour picker on click.

    The current RGBA tuple is stored on the button via
    :py:meth:`QObject.setProperty` so the dialog can read it back at
    accept-time without juggling a separate attribute.
    """
    btn = QPushButton()
    btn.setFixedHeight(24)
    btn.setProperty("rgba", tuple(int(c) for c in initial))
    _refresh_color_button(btn)
    btn.clicked.connect(lambda: _pick_color(btn))
    return btn


def _refresh_color_button(btn: QPushButton) -> None:
    rgba = btn.property("rgba") or (0, 0, 0, 255)
    r, g, b, _ = (int(c) for c in rgba)
    btn.setStyleSheet(
        f"background:rgb({r},{g},{b}); border:1px solid #444; border-radius:3px;",
    )


def _pick_color(btn: QPushButton) -> None:  # pragma: no cover - Qt UI
    rgba = btn.property("rgba") or (0, 0, 0, 255)
    initial = QColor(int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))
    chosen = QColorDialog.getColor(
        initial, btn, options=QColorDialog.ColorDialogOption.ShowAlphaChannel,
    )
    if not chosen.isValid():
        return
    btn.setProperty(
        "rgba",
        (chosen.red(), chosen.green(), chosen.blue(), chosen.alpha()),
    )
    _refresh_color_button(btn)


class SpeedlineConfigDialog(QDialog):
    """Configure a :class:`SpeedlineOptions` before render.

    Mirrors raster paint apps's effect-property dialog: every parameter is
    exposed, the user can re-centre the focus point, kind-specific
    fields show conditionally, and Cancel walks away without a layer.
    """

    def __init__(self, kind: str, canvas_shape: tuple[int, int], parent=None):
        super().__init__(parent)
        from Imervue.paint.speedlines import (
            DEFAULT_BURST_RADIUS_RATIO,
            DEFAULT_LINE_COUNT,
            DEFAULT_LINE_THICKNESS,
            LINE_COUNT_MAX,
            LINE_COUNT_MIN,
            LINE_THICKNESS_MAX,
            LINE_THICKNESS_MIN,
            SPEEDLINE_KINDS,
        )
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            lang.get("paint_manga_speedlines_title", "Speedlines"),
        )
        self.setMinimumWidth(360)
        h, w = canvas_shape
        self._canvas_shape = canvas_shape

        form = QFormLayout(self)

        self._kind = QComboBox()
        for k in SPEEDLINE_KINDS:
            self._kind.addItem(k)
        self._kind.setCurrentText(
            kind if kind in SPEEDLINE_KINDS else SPEEDLINE_KINDS[0],
        )
        form.addRow(lang.get("paint_manga_speedlines_kind", "Kind"), self._kind)

        self._count = QSpinBox()
        self._count.setRange(LINE_COUNT_MIN, LINE_COUNT_MAX)
        self._count.setValue(DEFAULT_LINE_COUNT)
        form.addRow(lang.get("paint_manga_speedlines_count", "Count"), self._count)

        self._thickness = QSpinBox()
        self._thickness.setRange(LINE_THICKNESS_MIN, LINE_THICKNESS_MAX)
        self._thickness.setValue(DEFAULT_LINE_THICKNESS)
        form.addRow(
            lang.get("paint_manga_speedlines_thickness", "Thickness"),
            self._thickness,
        )

        self._auto_center = QCheckBox(
            lang.get("paint_manga_auto_center", "Auto-centre"),
        )
        self._auto_center.setChecked(True)
        form.addRow(self._auto_center)

        center_row = QHBoxLayout()
        self._center_x = QSpinBox()
        self._center_x.setRange(0, max(1, w - 1))
        self._center_x.setValue(w // 2)
        self._center_y = QSpinBox()
        self._center_y.setRange(0, max(1, h - 1))
        self._center_y.setValue(h // 2)
        center_row.addWidget(self._center_x)
        center_row.addWidget(self._center_y)
        form.addRow(
            lang.get("paint_manga_center", "Centre (x, y)"), center_row,
        )
        self._auto_center.toggled.connect(self._center_x.setDisabled)
        self._auto_center.toggled.connect(self._center_y.setDisabled)
        self._center_x.setDisabled(True)
        self._center_y.setDisabled(True)

        self._angle = QDoubleSpinBox()
        self._angle.setRange(-180.0, 180.0)
        self._angle.setDecimals(1)
        self._angle.setValue(0.0)
        form.addRow(
            lang.get("paint_manga_speedlines_angle", "Angle (°, parallel)"),
            self._angle,
        )

        self._inner_radius = QDoubleSpinBox()
        self._inner_radius.setRange(0.0, 0.95)
        self._inner_radius.setDecimals(2)
        self._inner_radius.setSingleStep(0.05)
        self._inner_radius.setValue(DEFAULT_BURST_RADIUS_RATIO)
        form.addRow(
            lang.get("paint_manga_speedlines_inner", "Inner radius (burst)"),
            self._inner_radius,
        )

        self._jitter = QDoubleSpinBox()
        self._jitter.setRange(0.0, 1.0)
        self._jitter.setDecimals(2)
        self._jitter.setSingleStep(0.05)
        self._jitter.setValue(0.4)
        form.addRow(
            lang.get("paint_manga_speedlines_jitter", "Jitter"), self._jitter,
        )

        self._color = _color_button((0, 0, 0, 255))
        form.addRow(
            lang.get("paint_manga_speedlines_color", "Colour"), self._color,
        )

        self._seed = QSpinBox()
        self._seed.setRange(0, 1_000_000)
        self._seed.setValue(0)
        form.addRow(lang.get("paint_manga_seed", "Seed"), self._seed)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def options(self):
        from Imervue.paint.speedlines import SpeedlineOptions
        rgba = self._color.property("rgba") or (0, 0, 0, 255)
        center = (
            None if self._auto_center.isChecked()
            else (int(self._center_x.value()), int(self._center_y.value()))
        )
        return SpeedlineOptions(
            kind=self._kind.currentText(),
            count=int(self._count.value()),
            thickness=int(self._thickness.value()),
            color=tuple(int(c) for c in rgba),
            center=center,
            angle_deg=float(self._angle.value()),
            inner_radius_ratio=float(self._inner_radius.value()),
            jitter=float(self._jitter.value()),
            seed=int(self._seed.value()),
        )


class FlashConfigDialog(QDialog):
    """Configure a :class:`FlashOptions` before render."""

    def __init__(self, canvas_shape: tuple[int, int], parent=None):
        super().__init__(parent)
        from Imervue.paint.flash_effect import (
            DEFAULT_FLASH_SPIKES,
            DEFAULT_HALO_OPACITY,
            DEFAULT_HALO_RADIUS_RATIO,
            DEFAULT_INNER_RADIUS_RATIO,
            DEFAULT_OUTER_RADIUS_RATIO,
            FLASH_SPIKES_MAX,
            FLASH_SPIKES_MIN,
        )
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("paint_manga_flash_title", "Action Flash"))
        self.setMinimumWidth(360)
        h, w = canvas_shape

        form = QFormLayout(self)

        self._spikes = QSpinBox()
        self._spikes.setRange(FLASH_SPIKES_MIN, FLASH_SPIKES_MAX)
        self._spikes.setValue(DEFAULT_FLASH_SPIKES)
        form.addRow(
            lang.get("paint_manga_flash_spikes", "Spikes"), self._spikes,
        )

        self._outer = QDoubleSpinBox()
        self._outer.setRange(0.06, 1.5)
        self._outer.setDecimals(2)
        self._outer.setSingleStep(0.05)
        self._outer.setValue(DEFAULT_OUTER_RADIUS_RATIO)
        form.addRow(
            lang.get("paint_manga_flash_outer", "Outer radius"), self._outer,
        )

        self._inner = QDoubleSpinBox()
        self._inner.setRange(0.0, 1.4)
        self._inner.setDecimals(2)
        self._inner.setSingleStep(0.05)
        self._inner.setValue(DEFAULT_INNER_RADIUS_RATIO)
        form.addRow(
            lang.get("paint_manga_flash_inner", "Inner radius"), self._inner,
        )

        self._halo_radius = QDoubleSpinBox()
        self._halo_radius.setRange(0.0, 2.0)
        self._halo_radius.setDecimals(2)
        self._halo_radius.setSingleStep(0.05)
        self._halo_radius.setValue(DEFAULT_HALO_RADIUS_RATIO)
        form.addRow(
            lang.get("paint_manga_flash_halo_radius", "Halo radius"),
            self._halo_radius,
        )

        self._halo_opacity = QDoubleSpinBox()
        self._halo_opacity.setRange(0.0, 1.0)
        self._halo_opacity.setDecimals(2)
        self._halo_opacity.setSingleStep(0.05)
        self._halo_opacity.setValue(DEFAULT_HALO_OPACITY)
        form.addRow(
            lang.get("paint_manga_flash_halo_opacity", "Halo opacity"),
            self._halo_opacity,
        )

        self._auto_center = QCheckBox(
            lang.get("paint_manga_auto_center", "Auto-centre"),
        )
        self._auto_center.setChecked(True)
        form.addRow(self._auto_center)

        center_row = QHBoxLayout()
        self._center_x = QSpinBox()
        self._center_x.setRange(0, max(1, w - 1))
        self._center_x.setValue(w // 2)
        self._center_y = QSpinBox()
        self._center_y.setRange(0, max(1, h - 1))
        self._center_y.setValue(h // 2)
        center_row.addWidget(self._center_x)
        center_row.addWidget(self._center_y)
        form.addRow(
            lang.get("paint_manga_center", "Centre (x, y)"), center_row,
        )
        self._auto_center.toggled.connect(self._center_x.setDisabled)
        self._auto_center.toggled.connect(self._center_y.setDisabled)
        self._center_x.setDisabled(True)
        self._center_y.setDisabled(True)

        self._rotation = QDoubleSpinBox()
        self._rotation.setRange(-180.0, 180.0)
        self._rotation.setDecimals(1)
        self._rotation.setValue(0.0)
        form.addRow(
            lang.get("paint_manga_flash_rotation", "Rotation (°)"),
            self._rotation,
        )

        self._color = _color_button((255, 230, 80, 255))
        form.addRow(
            lang.get("paint_manga_flash_color", "Colour"), self._color,
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def options(self):
        from Imervue.paint.flash_effect import FlashOptions
        rgba = self._color.property("rgba") or (255, 230, 80, 255)
        # FlashOptions takes RGB only — strip the alpha but keep the
        # picker's full-RGBA contract for symmetry with speedlines.
        color_rgb = tuple(int(c) for c in rgba[:3])
        center = (
            None if self._auto_center.isChecked()
            else (int(self._center_x.value()), int(self._center_y.value()))
        )
        return FlashOptions(
            spikes=int(self._spikes.value()),
            outer_radius_ratio=float(self._outer.value()),
            inner_radius_ratio=float(self._inner.value()),
            halo_radius_ratio=float(self._halo_radius.value()),
            halo_opacity=float(self._halo_opacity.value()),
            color=color_rgb,
            center=center,
            rotation_deg=float(self._rotation.value()),
        )


def commit_panel_layout(
    workspace: PaintWorkspace, params: dict[str, int],
) -> bool:
    """Add a Panels layer that draws the requested grid.

    Returns ``True`` if a layer was added (parameters were valid for
    the canvas size), ``False`` otherwise. Pure-numpy logic so the
    test suite can exercise both branches without a Qt dialog.
    """
    import numpy as np

    from Imervue.paint.manga_panels import draw_panel_borders, panel_grid

    document = workspace.canvas().document()
    if document.shape is None:
        return False
    h, w = document.shape
    try:
        layout = panel_grid(
            width=w, height=h,
            rows=int(params["rows"]),
            cols=int(params["cols"]),
            gutter=int(params["gutter"]),
            border_width=int(params["border"]),
            margin=int(params["margin"]),
        )
    except (KeyError, ValueError):
        return False
    layer_canvas = np.zeros((h, w, 4), dtype=np.uint8)
    draw_panel_borders(layer_canvas, layout)
    layer = document.add_layer(name="Panels")
    np.copyto(layer.image, layer_canvas)
    document.invalidate_composite()
    workspace.canvas().update()
    return True
