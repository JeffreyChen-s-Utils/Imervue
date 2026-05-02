"""Layer-menu actions for the Paint workspace.

Wires the existing :class:`PaintDocument` verbs to one-click menu
entries with conventional shortcuts:

* Add raster layer (Ctrl+Shift+N) — :meth:`PaintDocument.add_layer`
* Add vector layer (Ctrl+Shift+V) — :meth:`PaintDocument.add_vector_layer`
* Duplicate layer (Ctrl+J) — :meth:`PaintDocument.duplicate_active_layer`
* Merge down (Ctrl+E) — :meth:`PaintDocument.merge_down`
* Delete layer (Ctrl+Shift+Delete) — :meth:`PaintDocument.remove_active_layer`

The bridge class follows the same pattern as
:mod:`Imervue.paint.file_menu` so the workspace holds one strong
reference (``_layer_menu_bridge``) for every action.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QKeySequence

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.gradient_map_presets import GRADIENT_MAP_PRESETS
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


def populate_layer_menu(workspace: PaintWorkspace) -> None:
    """Attach Layer-menu actions to ``workspace``."""
    bridge = _LayerMenuBridge(workspace)
    workspace._layer_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "layer")
    lang = language_wrapper.language_word_dict
    for key, fallback, slot, shortcut in (
        ("paint_layer_add_raster", "Add Layer",
         bridge.add_raster_layer, "Ctrl+Shift+N"),
        ("paint_layer_add_vector", "Add Vector Layer",
         bridge.add_vector_layer, "Ctrl+Shift+V"),
        ("paint_layer_duplicate", "Duplicate Layer",
         bridge.duplicate_layer, "Ctrl+J"),
        ("paint_layer_merge_down", "Merge Down",
         bridge.merge_down, "Ctrl+E"),
        (None, None, None, None),
        ("paint_layer_add_mask", "Add Mask",
         bridge.add_mask, "Ctrl+Shift+M"),
        ("paint_layer_add_mask_from_selection", "Add Mask From Selection",
         bridge.add_mask_from_selection, "Ctrl+Alt+Shift+M"),
        ("paint_layer_invert_mask", "Invert Mask",
         bridge.invert_mask, ""),
        ("paint_layer_apply_mask", "Apply Mask",
         bridge.apply_mask, ""),
        ("paint_layer_delete_mask", "Delete Mask",
         bridge.delete_mask, ""),
        (None, None, None, None),
        ("paint_layer_toggle_clip", "Toggle Clipping Mask",
         bridge.toggle_clipping_mask, "Ctrl+Alt+G"),
        (None, None, None, None),
        ("paint_layer_fx_drop_shadow", "Add Drop Shadow",
         bridge.add_drop_shadow, ""),
        ("paint_layer_fx_outer_glow", "Add Outer Glow",
         bridge.add_outer_glow, ""),
        ("paint_layer_fx_stroke", "Add Stroke",
         bridge.add_stroke, ""),
        ("paint_layer_fx_clear", "Clear Effects",
         bridge.clear_effects, ""),
        (None, None, None, None),
        ("paint_layer_set_reference", "Set as Reference Layer",
         bridge.set_reference_layer, ""),
        ("paint_layer_clear_reference", "Clear Reference Layer",
         bridge.clear_reference_layer, ""),
        (None, None, None, None),
        ("paint_layer_toggle_binary", "Toggle 1-bit Layer",
         bridge.toggle_binary_layer, ""),
        ("paint_layer_divide", "Divide Layer by Colour",
         bridge.divide_layer, ""),
        (None, None, None, None),
        ("paint_layer_delete", "Delete Layer",
         bridge.delete_layer, "Ctrl+Shift+Backspace"),
    ):
        if key is None:
            menu.addSeparator()
            continue
        action = menu.addAction(lang.get(key, fallback))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
    _populate_gradient_map_submenu(menu, bridge, lang)


def _populate_gradient_map_submenu(menu, bridge, lang) -> None:
    """Append a "Gradient Map" submenu listing the presets.

    Each entry creates a fresh adjustment layer using the preset's
    stop list. Kept as a sub-routine so the main population loop
    stays focused on the simpler one-shot actions.
    """
    menu.addSeparator()
    submenu = menu.addMenu(
        lang.get("paint_layer_gradient_map", "Add Gradient Map"),
    )
    for preset_id, label_key, fallback, _ in GRADIENT_MAP_PRESETS:
        action = submenu.addAction(lang.get(label_key, fallback))
        action.triggered.connect(
            lambda _checked=False, pid=preset_id: bridge.add_gradient_map(pid),
        )


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class _LayerMenuBridge:
    """Routes Layer-menu actions to the document + canvas refresh."""

    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace

    def add_raster_layer(self) -> None:
        document = self._workspace.canvas().document()
        if document.shape is None:
            return
        document.add_layer()
        self._refresh_canvas()

    def add_vector_layer(self) -> None:
        document = self._workspace.canvas().document()
        if document.shape is None:
            return
        document.add_vector_layer()
        self._refresh_canvas()

    def duplicate_layer(self) -> None:
        document = self._workspace.canvas().document()
        if document.active_layer() is None:
            return
        document.duplicate_active_layer()
        self._refresh_canvas()

    def merge_down(self) -> None:
        document = self._workspace.canvas().document()
        if document.merge_down():
            self._refresh_canvas()

    def delete_layer(self) -> None:
        document = self._workspace.canvas().document()
        if document.layer_count <= 1:
            # Refuse to drop the last layer — matches the document
            # model's own invariant.
            return
        document.remove_active_layer()
        self._refresh_canvas()

    # ---- masks ----------------------------------------------------------

    def add_mask(self) -> None:
        document = self._workspace.canvas().document()
        if document.add_layer_mask():
            self._refresh_canvas()

    def add_mask_from_selection(self) -> None:
        document = self._workspace.canvas().document()
        if document.add_layer_mask_from_selection():
            self._refresh_canvas()

    def delete_mask(self) -> None:
        document = self._workspace.canvas().document()
        if document.clear_layer_mask():
            self._refresh_canvas()

    def invert_mask(self) -> None:
        document = self._workspace.canvas().document()
        if document.invert_layer_mask():
            self._refresh_canvas()

    def apply_mask(self) -> None:
        document = self._workspace.canvas().document()
        if document.apply_layer_mask():
            self._refresh_canvas()

    # ---- layer effects --------------------------------------------------

    def add_drop_shadow(self) -> None:
        self._add_effect("drop_shadow")

    def add_outer_glow(self) -> None:
        self._add_effect("outer_glow")

    def add_stroke(self) -> None:
        self._add_effect("stroke")

    def clear_effects(self) -> None:
        document = self._workspace.canvas().document()
        layer = document.active_layer()
        if layer is None or not layer.effects:
            return
        if document.set_layer_effects(effects=()):
            self._refresh_canvas()

    # ---- reference layer (bucket sampling) ------------------------------

    def set_reference_layer(self) -> None:
        """Mark the active layer as the bucket's reference."""
        document = self._workspace.canvas().document()
        idx = document.active_layer_index()
        if idx < 0:
            return
        if document.set_reference_layer_index(idx):
            self._refresh_canvas()

    def clear_reference_layer(self) -> None:
        """Drop the bucket's reference-layer pointer."""
        document = self._workspace.canvas().document()
        if document.set_reference_layer_index(None):
            self._refresh_canvas()

    def divide_layer(self) -> None:
        """Replace the active layer with one per flat colour.

        Empty / fully-transparent layers leave the stack alone — the
        document verb returns 0 in that case.
        """
        document = self._workspace.canvas().document()
        if document.divide_active_layer() > 0:
            self._refresh_canvas()

    def add_gradient_map(self, preset_id: str) -> None:
        """Insert a Gradient Map adjustment layer for ``preset_id``.

        The adjustment is non-destructive — the underlying pixels stay
        unchanged. Unknown preset ids are a silent no-op so a stale
        toolbar action survives a future preset rename without
        crashing the workspace.
        """
        from Imervue.paint.adjustments import Adjustment
        from Imervue.paint.gradient_map_presets import preset_stops

        stops = preset_stops(preset_id)
        if stops is None:
            return
        document = self._workspace.canvas().document()
        if document.shape is None:
            return
        adjustment = Adjustment(
            kind="gradient_map", params={"stops": stops},
        )
        document.add_adjustment_layer(
            adjustment, name=f"Gradient Map ({preset_id})",
        )
        self._refresh_canvas()

    def toggle_binary_layer(self) -> None:
        """Flip the active layer between plain raster and 1-bit ink.

        On → installs default :class:`BinarySettings` so the
        compositor thresholds the layer's alpha into ink-or-transparent
        every time it composites. Off → drops the hint and the
        original soft strokes reappear.
        """
        from Imervue.paint.binary_layer import BinarySettings
        document = self._workspace.canvas().document()
        layer = document.active_layer()
        if layer is None:
            return
        new_binary = None if layer.binary is not None else BinarySettings()
        if document.set_layer_binary(binary=new_binary):
            self._refresh_canvas()

    def _add_effect(self, kind: str) -> None:
        """Append an effect of ``kind`` to the active layer.

        Replaces an existing effect of the same kind so a second
        click on "Add Drop Shadow" doesn't stack two shadows — the
        renderer takes the first occurrence per kind anyway.
        """
        from Imervue.paint.layer_effects import DEFAULT_PARAMS, LayerEffect
        document = self._workspace.canvas().document()
        layer = document.active_layer()
        if layer is None:
            return
        new_effect = LayerEffect(
            kind=kind, params=dict(DEFAULT_PARAMS[kind]),
        )
        # Drop any existing effect of the same kind so the user gets
        # an obvious "replaced" rather than a silent no-op.
        keep = tuple(e for e in layer.effects if e.kind != kind)
        if document.set_layer_effects(effects=keep + (new_effect,)):
            self._refresh_canvas()

    # ---- clipping mask --------------------------------------------------

    def toggle_clipping_mask(self) -> None:
        """Flip the active layer's ``clip`` flag and refresh.

        Matches Photoshop's Ctrl+Alt+G binding — toggles whether the
        layer is clipped to the alpha of the layer below it.
        """
        document = self._workspace.canvas().document()
        layer = document.active_layer()
        if layer is None:
            return
        if document.set_layer_clip(clip=not layer.clip):
            self._refresh_canvas()

    # ---- internals ------------------------------------------------------

    def _refresh_canvas(self) -> None:
        canvas = self._workspace.canvas()
        canvas.document().invalidate_composite()
        canvas.update()
