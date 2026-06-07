"""Brush and fill docks."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFormLayout,
    QPushButton,
    QSpinBox,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState

from Imervue.paint.docks._helpers import (
    _slider,
)


class BrushDock(QDockWidget):
    """Brush kind, size, opacity, hardness, density, blend mode."""

    def __init__(self, state: ToolState, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_brush", "Brush"), parent)
        self._state = state
        self._suspend = False

        body = QWidget()
        form = QFormLayout(body)

        self._kind = QComboBox()
        # Tall enough to host the brush-kind preview thumbnail; the
        # combo's icon size has to be set before the items go in or
        # the icons render at QStyle's default ~16px.
        from PySide6.QtCore import QSize
        from Imervue.paint.brush_kind_preview import (
            DEFAULT_THUMBNAIL_H,
            DEFAULT_THUMBNAIL_W,
            render_brush_kind_pixmap,
        )
        self._kind.setIconSize(QSize(DEFAULT_THUMBNAIL_W, DEFAULT_THUMBNAIL_H))
        for kind in ts.BRUSH_KINDS:
            try:
                icon = QIcon(render_brush_kind_pixmap(kind))
            except (RuntimeError, ValueError):
                icon = QIcon()
            self._kind.addItem(
                icon,
                lang.get(f"paint_brush_kind_{kind}", kind.capitalize()),
                userData=kind,
            )
        self._kind.currentIndexChanged.connect(self._on_kind_changed)
        self._kind.setToolTip(lang.get(
            "paint_brush_kind_tooltip",
            "Brush family — pen / pencil / marker / airbrush / watercolor",
        ))

        self._size = QSpinBox()
        self._size.setRange(ts.BRUSH_SIZE_MIN, ts.BRUSH_SIZE_MAX)
        self._size.valueChanged.connect(self._on_size_changed)
        self._size.setToolTip(lang.get(
            "paint_brush_size_tooltip",
            "Brush diameter in canvas pixels — [ smaller, ] larger",
        ))

        self._opacity = _slider(0, 100, 100)
        self._opacity.valueChanged.connect(self._on_opacity_changed)
        self._opacity.setToolTip(lang.get(
            "paint_brush_opacity_tooltip",
            "Per-dab paint coverage (0–100%)",
        ))

        self._hardness = _slider(0, 100, 80)
        self._hardness.valueChanged.connect(self._on_hardness_changed)
        self._hardness.setToolTip(lang.get(
            "paint_brush_hardness_tooltip",
            "Edge falloff — 0% soft, 100% hard disc",
        ))

        self._density = _slider(0, 100, 100)
        self._density.valueChanged.connect(self._on_density_changed)
        self._density.setToolTip(lang.get(
            "paint_brush_density_tooltip",
            "Per-dab opacity multiplier — lower deposits less ink per stamp",
        ))

        # Stabilizer / scatter / colour-jitter / follow-tilt — engine
        # already supports these via brush_dynamics + brush_random;
        # surfacing them as live controls here matches raster paint apps's
        # brush-options panel.
        self._stabilizer = _slider(0, 100, 0)
        self._stabilizer.valueChanged.connect(self._on_stabilizer_changed)
        self._stabilizer.setToolTip(lang.get(
            "paint_brush_stabilizer_tooltip",
            "Smooth jittery input — 0 off, 100 maximum lag for a clean line",
        ))

        self._scatter = _slider(0, 100, 0)
        self._scatter.valueChanged.connect(self._on_scatter_changed)
        self._scatter.setToolTip(lang.get(
            "paint_brush_scatter_tooltip",
            "Random per-dab offset, as a fraction of brush size",
        ))

        self._color_jitter = _slider(0, 100, 0)
        self._color_jitter.valueChanged.connect(self._on_color_jitter_changed)
        self._color_jitter.setToolTip(lang.get(
            "paint_brush_color_jitter_tooltip",
            "Random hue / luma drift along the stroke",
        ))

        from PySide6.QtWidgets import QCheckBox
        self._follow_tilt = QCheckBox(
            lang.get("paint_brush_follow_tilt", "Follow pen tilt"),
        )
        self._follow_tilt.toggled.connect(self._on_follow_tilt_changed)
        self._follow_tilt.setToolTip(lang.get(
            "paint_brush_follow_tilt_tooltip",
            "Stretch the brush kernel along the tablet pen tilt direction",
        ))

        self._blend = QComboBox()
        for mode in ts.BLEND_MODES:
            self._blend.addItem(
                lang.get(f"paint_blend_{mode}", mode.replace("_", " ").title()),
                userData=mode,
            )
        self._blend.currentIndexChanged.connect(self._on_blend_changed)
        self._blend.setToolTip(lang.get(
            "paint_brush_blend_tooltip",
            "Compositing mode applied at every dab — Normal is alpha-over",
        ))

        form.addRow(lang.get("paint_brush_kind", "Kind:"), self._kind)
        form.addRow(lang.get("paint_brush_size", "Size:"), self._size)
        form.addRow(lang.get("paint_brush_opacity", "Opacity:"), self._opacity)
        form.addRow(lang.get("paint_brush_hardness", "Hardness:"), self._hardness)
        form.addRow(lang.get("paint_brush_density", "Density:"), self._density)
        form.addRow(
            lang.get("paint_brush_stabilizer", "Stabilizer:"),
            self._stabilizer,
        )
        form.addRow(
            lang.get("paint_brush_scatter", "Scatter:"), self._scatter,
        )
        form.addRow(
            lang.get("paint_brush_color_jitter", "Colour jitter:"),
            self._color_jitter,
        )
        form.addRow("", self._follow_tilt)
        form.addRow(lang.get("paint_brush_blend", "Blend:"), self._blend)

        # full-featured sub-tool / preset manager. The button opens a
        # modal dialog that drives ``state.add_sub_tool`` /
        # ``apply_sub_tool`` / ``remove_sub_tool`` for the active main
        # tool, so brush + fill snapshots round-trip through the
        # existing persistence path.
        self._presets_btn = QPushButton(
            lang.get("paint_brush_presets_open", "Presets…"),
        )
        self._presets_btn.clicked.connect(self._on_presets_clicked)
        form.addRow("", self._presets_btn)

        self.setWidget(body)
        self._refresh_from_state()
        self._unsubscribe = state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())

    def _on_presets_clicked(self) -> None:
        from Imervue.paint.brush_preset_dialog import open_brush_preset_dialog
        open_brush_preset_dialog(self._state, parent=self)

    def _on_state_event(self, channel: str) -> None:
        if channel == ts.EVENT_BRUSH:
            self._refresh_from_state()

    def _refresh_from_state(self) -> None:
        self._suspend = True
        try:
            self._kind.setCurrentIndex(self._kind.findData(self._state.brush.kind))
            self._size.setValue(self._state.brush.size)
            self._opacity.setValue(int(round(self._state.brush.opacity * 100)))
            self._hardness.setValue(int(round(self._state.brush.hardness * 100)))
            self._density.setValue(int(round(self._state.brush.density * 100)))
            self._stabilizer.setValue(
                int(round(self._state.brush.stabilizer * 100)),
            )
            self._scatter.setValue(
                int(round(self._state.brush.scatter * 100)),
            )
            self._color_jitter.setValue(
                int(round(self._state.brush.color_jitter * 100)),
            )
            self._follow_tilt.setChecked(
                bool(self._state.brush.follow_tilt),
            )
            self._blend.setCurrentIndex(self._blend.findData(self._state.brush.blend_mode))
        finally:
            self._suspend = False

    def _on_kind_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(kind=self._kind.currentData())

    def _on_size_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(size=int(self._size.value()))

    def _on_opacity_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(opacity=self._opacity.value() / 100.0)

    def _on_hardness_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(hardness=self._hardness.value() / 100.0)

    def _on_density_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(density=self._density.value() / 100.0)

    def _on_stabilizer_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(stabilizer=self._stabilizer.value() / 100.0)

    def _on_scatter_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(scatter=self._scatter.value() / 100.0)

    def _on_color_jitter_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(
            color_jitter=self._color_jitter.value() / 100.0,
        )

    def _on_follow_tilt_changed(self, checked: bool) -> None:
        if self._suspend:
            return
        self._state.set_brush(follow_tilt=bool(checked))

    def _on_blend_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_brush(blend_mode=self._blend.currentData())


# ---------------------------------------------------------------------------
# Fill bucket options dock
# ---------------------------------------------------------------------------


class FillDock(QDockWidget):
    """Surfaces every :class:`FillSettings` knob for the bucket tool.

    Tabified next to BrushDock so the user flips between brush and
    bucket option panels the way raster paint apps Pro does. Updates
    flow both ways: state-event subscription mirrors the singleton
    when the user changes settings via shortcut or another panel,
    and edits here go through ``state.set_fill(...)`` so persistence
    + redraw fire on a single code path.
    """

    def __init__(self, state: ToolState, parent=None):
        from PySide6.QtWidgets import QCheckBox
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_fill", "Bucket"), parent)
        self._state = state
        self._suspend = False

        body = QWidget()
        form = QFormLayout(body)

        self._tolerance = _slider(0, 255, 32)
        self._tolerance.valueChanged.connect(self._on_tolerance_changed)
        self._tolerance.setToolTip(lang.get(
            "paint_fill_tolerance_tooltip",
            "Per-channel colour distance accepted as the same region "
            "(0 exact, 255 anything)",
        ))

        self._contiguous = QCheckBox(
            lang.get("paint_fill_contiguous", "Contiguous (only adjacent pixels)"),
        )
        self._contiguous.toggled.connect(self._on_contiguous_changed)
        self._contiguous.setToolTip(lang.get(
            "paint_fill_contiguous_tooltip",
            "On: only pixels reachable from the click. Off: every "
            "matching pixel canvas-wide.",
        ))

        self._sample_all = QCheckBox(
            lang.get("paint_fill_sample_all", "Sample all layers"),
        )
        self._sample_all.toggled.connect(self._on_sample_all_changed)
        self._sample_all.setToolTip(lang.get(
            "paint_fill_sample_all_tooltip",
            "Match colours against the visible composite instead of "
            "just the active layer",
        ))

        self._use_reference = QCheckBox(
            lang.get(
                "paint_fill_use_reference",
                "Use reference layer for boundaries",
            ),
        )
        self._use_reference.toggled.connect(self._on_use_reference_changed)
        self._use_reference.setToolTip(lang.get(
            "paint_fill_use_reference_tooltip",
            "Read connectivity from the document's pinned reference "
            "layer (e.g. line art) so fill stops at ink boundaries "
            "regardless of the active layer's colour",
        ))

        self._expand = _slider(ts.FILL_EXPAND_MIN, ts.FILL_EXPAND_MAX, 0)
        self._expand.valueChanged.connect(self._on_expand_changed)
        self._expand.setToolTip(lang.get(
            "paint_fill_expand_tooltip",
            "Dilate the fill by N pixels after computing it — bridges "
            "the anti-aliased halo around lineart",
        ))

        self._gap_close = _slider(
            ts.FILL_GAP_CLOSE_MIN, ts.FILL_GAP_CLOSE_MAX, 0,
        )
        self._gap_close.valueChanged.connect(self._on_gap_close_changed)
        self._gap_close.setToolTip(lang.get(
            "paint_fill_gap_close_tooltip",
            "Bridge gaps in the lineart up to N pixels wide so fill "
            "doesn't leak through broken pen strokes",
        ))

        form.addRow(
            lang.get("paint_fill_tolerance", "Tolerance:"), self._tolerance,
        )
        form.addRow("", self._contiguous)
        form.addRow("", self._sample_all)
        form.addRow("", self._use_reference)
        form.addRow(
            lang.get("paint_fill_expand", "Expand (px):"), self._expand,
        )
        form.addRow(
            lang.get("paint_fill_gap_close", "Close gap (px):"),
            self._gap_close,
        )

        # full-featured "fill every closed region in one click". Goes
        # to a workspace-level action so it can read the active layer
        # + the reference layer through the document API. The button
        # surfaces a no-op + status message when no callback is wired.
        self._auto_fill_btn = QPushButton(
            lang.get("paint_fill_auto_regions", "Auto-fill closed regions"),
        )
        self._auto_fill_btn.clicked.connect(self._on_auto_fill_clicked)
        form.addRow("", self._auto_fill_btn)
        self._auto_fill_callback = None

        self.setWidget(body)
        self._refresh_from_state()
        self._unsubscribe = state.subscribe(self._on_state_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())

    def set_auto_fill_callback(self, callback) -> None:
        """Wire the workspace's auto-fill verb to the dock's button."""
        self._auto_fill_callback = callback

    def _on_auto_fill_clicked(self) -> None:
        if self._auto_fill_callback is None:
            return
        self._auto_fill_callback()

    def _on_state_event(self, channel: str) -> None:
        if channel == ts.EVENT_FILL:
            self._refresh_from_state()

    def _refresh_from_state(self) -> None:
        self._suspend = True
        try:
            fill = self._state.fill
            self._tolerance.setValue(int(fill.tolerance))
            self._contiguous.setChecked(bool(fill.contiguous))
            self._sample_all.setChecked(bool(fill.sample_all_layers))
            self._use_reference.setChecked(bool(fill.use_reference_layer))
            self._expand.setValue(int(fill.expand_px))
            self._gap_close.setValue(int(fill.gap_close_px))
        finally:
            self._suspend = False

    def _on_tolerance_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_fill(tolerance=int(self._tolerance.value()))

    def _on_contiguous_changed(self, checked: bool) -> None:
        if self._suspend:
            return
        self._state.set_fill(contiguous=bool(checked))

    def _on_sample_all_changed(self, checked: bool) -> None:
        if self._suspend:
            return
        self._state.set_fill(sample_all_layers=bool(checked))

    def _on_use_reference_changed(self, checked: bool) -> None:
        if self._suspend:
            return
        self._state.set_fill(use_reference_layer=bool(checked))

    def _on_expand_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_fill(expand_px=int(self._expand.value()))

    def _on_gap_close_changed(self) -> None:
        if self._suspend:
            return
        self._state.set_fill(gap_close_px=int(self._gap_close.value()))


# ---------------------------------------------------------------------------
# Layer dock — placeholder backed by the existing layers system
# ---------------------------------------------------------------------------


