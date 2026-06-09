"""Pointer-interaction controller for the desktop-pet overlay.

Owns the drag-to-move, click-routing, and hit-detection behaviour that
:class:`~Imervue.desktop_pet.pet_window.PetWindow` used to carry inline
as the ``eventFilter`` / ``_on_press`` / ``_on_move`` / ``_on_release``
/ ``_handle_click`` family.

The controller talks back to the window through its existing public /
semi-public surface (``play_random_motion_in_group``, ``hit_triggered``,
``moved``, ``document``, ``canvas`` …) plus a few state flags it reads
directly, so the behaviour is preserved byte-for-byte. The window keeps
a thin ``eventFilter`` that forwards to :meth:`handle_canvas_event` and
re-exposes the drag-state flags (``_dragging`` …) via properties so the
existing test contract keeps working.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt

from Imervue.desktop_pet import pet_placement
from Imervue.desktop_pet.click_sfx import (
    EVENT_CLICK as SFX_CLICK,
    EVENT_DRAG as SFX_DRAG,
    EVENT_DROP as SFX_DROP,
)
from Imervue.puppet.hit_test import hit_test

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent

CLICK_RADIUS_PX = 6
"""A release within this manhattan radius of the press counts as a
click (hit-area routing) rather than a drag (edge-snap + persist)."""


def widget_to_image(
    widget_x: float, widget_y: float, zoom: float, pan_x: float, pan_y: float,
) -> tuple[float, float] | None:
    """Undo the canvas pan + zoom so a widget-space point becomes the
    puppet-canvas (document) coordinate the hit-test expects.

    Returns ``None`` for a non-positive zoom (degenerate transform).
    Pure helper so the inverse-transform maths is unit-testable without
    a live GL canvas.
    """
    if zoom <= 0:
        return None
    return (widget_x - pan_x) / zoom, (widget_y - pan_y) / zoom


def llm_situation_tag(area_id: str | None, motion_name: str | None) -> str:
    """Pick the situation label to pass to the LLM. Hit-area context
    wins over motion context which wins over the generic greeting
    fallback — same priority chain the script engine uses."""
    if area_id:
        return f"hit:{area_id}"
    if motion_name:
        return f"motion:{motion_name}"
    return "greeting"


class PetInteraction:
    """Drag / click / hit-detection handler bound to one pet overlay.

    ``host`` is the :class:`PetWindow`; the controller reads its flag
    state and calls back into its motion / speech / persistence surface.
    """

    DRAG_MOTION_GROUP = "Drag"
    LAND_MOTION_GROUP = "Land"

    def __init__(self, host) -> None:
        self._host = host
        self._dragging: bool = False
        self._drag_offset: QPoint = QPoint(0, 0)
        self._press_pos: QPoint | None = None

    # ---- drag-state accessors (test contract) ------------------

    @property
    def dragging(self) -> bool:
        return self._dragging

    @property
    def drag_offset(self) -> QPoint:
        return self._drag_offset

    @property
    def press_pos(self) -> QPoint | None:
        return self._press_pos

    # ---- event entry point -------------------------------------

    def handle_canvas_event(self, event) -> bool:   # pragma: no cover - Qt UI
        """Dispatch a canvas event. Returns ``True`` when the event was
        consumed (context menu) and should not propagate."""
        etype = event.type()
        if etype == event.Type.MouseButtonPress:
            self._on_press(event)
        elif etype == event.Type.MouseMove:
            self._on_move(event)
        elif etype == event.Type.MouseButtonRelease:
            self._on_release(event)
        elif etype == event.Type.ContextMenu:
            self._host._show_context_menu(event.globalPos())   # noqa: SLF001
            return True
        return False

    def _on_press(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        host = self._host
        if host.click_through_enabled():
            return
        if event.button() == Qt.MouseButton.RightButton:
            # Right-click → context menu. Eat the event so the canvas
            # doesn't try to start a pan.
            host._show_context_menu(event.globalPosition().toPoint())   # noqa: SLF001
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._press_pos = event.position().toPoint()
        host._notify_user_activity()   # noqa: SLF001
        if not host.anchor_locked():
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - host.pos()
            host.canvas().setCursor(Qt.CursorShape.ClosedHandCursor)
            host.play_random_motion_in_group(self.DRAG_MOTION_GROUP)
            host._play_sfx(SFX_DRAG)   # noqa: SLF001

    def _on_move(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        host = self._host
        host._notify_user_activity()   # noqa: SLF001
        if not self._dragging:
            return
        host.move(event.globalPosition().toPoint() - self._drag_offset)
        host.reanchor_speech()

    def _on_release(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if event.button() != Qt.MouseButton.LeftButton:
            return
        host = self._host
        was_dragging = self._dragging
        self._dragging = False
        host.canvas().unsetCursor()
        press = self._press_pos
        self._press_pos = None
        if not was_dragging:
            self._handle_click(press)
            return
        self._finish_drag(event, press)

    def _finish_drag(self, event, press) -> None:   # pragma: no cover - Qt UI
        """Edge-snap + persist after a real drag, then route the gesture
        as a click (released near the press) or a land (moved away)."""
        host = self._host
        pet_placement.apply_edge_snap(host)
        pos = host.pos()
        host._persist(   # noqa: SLF001
            position=[pos.x(), pos.y()],
            screen_name=host._current_screen_name(),   # noqa: SLF001
        )
        host.moved.emit(pos.x(), pos.y())
        click_inside_press_radius = (
            press is not None
            and (event.position().toPoint() - press).manhattanLength()
            < CLICK_RADIUS_PX
        )
        if click_inside_press_radius:
            self._handle_click(press)
        else:
            host.play_random_motion_in_group(self.LAND_MOTION_GROUP)
            host._play_sfx(SFX_DROP)   # noqa: SLF001

    def _handle_click(self, widget_pos: QPoint | None) -> None:   # pragma: no cover - GL needed
        """A click on the pet body → hit-test → play the linked motion
        + speak the scripted line, or fall back to a greeting."""
        host = self._host
        area = self._hit_test_at(widget_pos)
        if area is None and host.document() is None:
            # ``_hit_test_at`` returns None for both "no document" and
            # "no hit area matched"; only bail when no rig is loaded.
            return
        area_id = area.id if area is not None else ""
        host.hit_triggered.emit(area_id)
        motion_name = area.motion if area is not None else None
        if motion_name:
            host._play_motion_by_name(motion_name)   # noqa: SLF001
        host._play_sfx(SFX_CLICK)   # noqa: SLF001
        host.speak_click_response(area_id, motion_name)

    def _hit_test_at(self, widget_pos: QPoint | None):
        """Run the document's hit-area test at a widget-space position.
        ``None`` when there's no rig, no transform, or no area covers
        the point."""
        if widget_pos is None:
            return None
        host = self._host
        document = host.document()
        if document is None:
            return None
        canvas = host.canvas()
        image_xy = widget_to_image(
            widget_pos.x(), widget_pos.y(),
            float(getattr(canvas, "_zoom", 1.0)),
            float(getattr(canvas, "_pan_x", 0.0)),
            float(getattr(canvas, "_pan_y", 0.0)),
        )
        if image_xy is None:
            return None
        return hit_test(
            document, image_xy[0], image_xy[1],
            deformed_vertices=canvas._deformed_vertices,   # noqa: SLF001
        )
