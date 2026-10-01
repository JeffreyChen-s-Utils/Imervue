"""Pointer, keyboard and drag-and-drop input of the paint canvas.

Mouse and tablet events become ``PointerEvent`` s (pressure, tilt, button,
modifiers in image coordinates) routed to the tool dispatcher; middle-drag and
Space-drag pan, the wheel zooms, Enter / Escape commit or cancel the pen tool,
and image files dropped on the canvas open or become layers.
``PaintCanvas`` mixes these methods in.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCursor, QMouseEvent, QTabletEvent, QWheelEvent

from Imervue.paint.damage import DamageRect
from Imervue.paint.damage import EMPTY as EMPTY_DAMAGE
from Imervue.paint.pointer_event import PointerEvent


ZOOM_STEP = 1.15
# QTabletEvent.type() → PointerEvent.phase. Wacom-style stylii deliver
# distinct event types for press / move / release; a missing entry means
# we ignore the event (e.g. ``TabletEnterProximity``).
_TABLET_PHASE = {
    QEvent.Type.TabletPress: "press",
    QEvent.Type.TabletMove: "move",
    QEvent.Type.TabletRelease: "release",
}


class PaintCanvasInputMixin:
    """Pointer, keyboard and drag-and-drop input of the paint canvas."""

    def keyPressEvent(self, event) -> None:  # pragma: no cover - Qt UI
        """Bracket-key brush size + Enter pen-commit + HUD flash."""
        from PySide6.QtCore import Qt as _Qt
        key = event.key()
        if key in (_Qt.Key.Key_BracketLeft, _Qt.Key.Key_BracketRight):
            if self._tool_state_for_hud is None or self._size_hud is None:
                event.ignore()
                return
            from Imervue.paint.size_hud_bridge import (
                adjust_brush_size, trigger_size_hud,
            )
            adjust_brush_size(
                self._tool_state_for_hud,
                larger=(key == _Qt.Key.Key_BracketRight),
            )
            trigger_size_hud(self._tool_state_for_hud, self._size_hud)
            self.update()
            return
        if key in (_Qt.Key.Key_Return, _Qt.Key.Key_Enter):
            workspace = self._workspace_for_pen_commit()
            if workspace is None:
                event.ignore()
                return
            from Imervue.paint.pen_commit import commit_pen_path
            if commit_pen_path(workspace):
                self._needs_upload = True
                self.document_changed.emit()
                self.update()
            return
        super().keyPressEvent(event)

    def _workspace_for_pen_commit(self):
        """Return the workspace if it owns a bezier pen path.

        The canvas doesn't import :class:`PaintWorkspace` directly to
        avoid a circular dependency; instead it duck-types on the
        ``_bezier_pen_path`` attribute the pen tool stores.
        """
        candidate = self.parent()
        for _ in range(4):   # walk up at most a few parents
            if candidate is None:
                break
            if hasattr(candidate, "_bezier_pen_path"):
                return candidate
            candidate = candidate.parent() if hasattr(candidate, "parent") else None
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - Qt UI
        if self._is_pan_button(event):
            self._panning = True
            self._pan_anchor = (event.position().x(), event.position().y())
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return
        # Hand / zoom tools work on the canvas widget itself, not on
        # the layer image — handle them here before the dispatcher
        # would silently no-op (it has no handlers for these tools).
        active_tool = (
            self._tool_state_for_hud.tool
            if self._tool_state_for_hud is not None
            else None
        )
        if (
            active_tool == "hand"
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._panning = True
            self._pan_anchor = (event.position().x(), event.position().y())
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return
        if (
            active_tool == "zoom"
            and event.button() == Qt.MouseButton.LeftButton
        ):
            # Click zooms in 1.25×; Alt+click zooms out, mirroring
            # the Photoshop / raster paint apps convention.
            factor = 1.0 / 1.25 if (
                event.modifiers() & Qt.KeyboardModifier.AltModifier
            ) else 1.25
            self._apply_zoom(
                factor, event.position().x(), event.position().y(),
            )
            return
        self._dispatch("press", event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - Qt UI
        x, y = self._screen_to_image(event.position().x(), event.position().y())
        self.hover_changed.emit(int(x), int(y))
        if self._panning:
            dx = event.position().x() - self._pan_anchor[0]
            dy = event.position().y() - self._pan_anchor[1]
            self._pan_anchor = (event.position().x(), event.position().y())
            self._pan_x += dx
            self._pan_y += dy
            # Manual pan — stop auto-fitting on subsequent resizes.
            self._user_view_locked = True
            self.update()
            return
        self._dispatch("move", event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - Qt UI
        if self._panning and self._is_pan_button(event):
            self._panning = False
            # Restore the active tool's cursor — the open-hand was only
            # valid while the pan gesture was active. Falling back to
            # "brush" when the workspace hasn't installed a tool-state
            # is safer than leaving the closed-hand stuck.
            active_tool = (
                self._tool_state_for_hud.tool
                if self._tool_state_for_hud is not None
                else "brush"
            )
            self.set_cursor_for_tool(active_tool)
            return
        self._dispatch("release", event)

    def leaveEvent(self, event) -> None:  # pragma: no cover - Qt UI
        self.hover_changed.emit(-1, -1)
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # pragma: no cover - Qt UI
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = ZOOM_STEP if delta > 0 else 1.0 / ZOOM_STEP
        self._apply_zoom(factor, event.position().x(), event.position().y())

    def tabletEvent(self, event: QTabletEvent) -> None:  # pragma: no cover - tablet
        # ``event.accept()`` suppresses Qt's synthesised mouse event,
        # so the brush would receive nothing if we only stored pressure
        # here — that is the original "下筆後沒顏色" symptom for tablet
        # users. Map the tablet event onto the same dispatch path used
        # by mouse input so press / move / release reach the active
        # tool with full pressure + tilt detail.
        phase = _TABLET_PHASE.get(event.type())
        if phase is not None:
            self._dispatch_pointer(
                phase,
                event.position().x(), event.position().y(),
                button=int(event.button().value),
                modifiers=int(event.modifiers().value),
                pressure=self._pen_pressure(float(event.pressure())),
                tilt_x=float(event.xTilt()) / 60.0,
                tilt_y=float(event.yTilt()) / 60.0,
            )
        event.accept()

    def _dispatch(self, phase: str, event: QMouseEvent) -> None:
        # PySide6 6.x returns Qt.MouseButton / Qt.KeyboardModifier as
        # flag enums that don't auto-convert via int() — go through
        # ``.value`` so PointerEvent stays plain-int as the tests expect.
        self._dispatch_pointer(
            phase,
            event.position().x(), event.position().y(),
            button=int(event.button().value),
            modifiers=int(event.modifiers().value),
            # A mouse has no pressure. The pen's last value (0 on lifting it)
            # used to stay here and thinned every later mouse stroke.
            pressure=1.0,
        )

    def _pen_pressure(self, raw: float) -> float:
        """Tablet pressure shaped by the tool state's curve (Settings > Pressure Curve…)."""
        from Imervue.paint.pressure_curve import apply_curve
        curve = getattr(self._tool_state_for_hud, "pressure_curve", None)
        return apply_curve(curve, raw)

    def _dispatch_pointer(
        self,
        phase: str,
        x_screen: float,
        y_screen: float,
        *,
        button: int,
        modifiers: int,
        pressure: float,
        tilt_x: float = 0.0,
        tilt_y: float = 0.0,
    ) -> None:
        """Shared mouse / tablet entry into the tool dispatcher.

        Translates screen coordinates into image space, builds the
        immutable :class:`PointerEvent`, hands it to the active tool,
        and refreshes the canvas only when the tool reported a change.
        """
        if self._dispatcher is None:
            return
        x, y = self._screen_to_image(x_screen, y_screen)
        evt = PointerEvent(
            phase=phase,
            x=x, y=y,
            button=button,
            modifiers=modifiers,
            pressure=pressure,
            tilt_x=max(-1.0, min(1.0, tilt_x)),
            tilt_y=max(-1.0, min(1.0, tilt_y)),
        )
        # GPU brush rasterisation needs this widget's GL context bound
        # for the duration of the dispatcher call. Qt only auto-binds
        # during ``paintGL`` / ``resizeGL`` / ``initializeGL``; pointer
        # events arrive without a current context. The ``suppress``
        # wrappers cover the early-test path where the widget has no
        # platform handle yet (``makeCurrent`` raises in that state);
        # the gpu-session flag tells the brush factory that the
        # context is freshly bound (vs leaked from an earlier test).
        import contextlib
        from Imervue.paint.gpu_brush import set_gpu_session_active
        gpu_active = False
        with contextlib.suppress(RuntimeError, AttributeError):  # pragma: no cover - Qt edge
            self.makeCurrent()
            gpu_active = True
        if gpu_active:
            set_gpu_session_active(True)
        try:
            handled = self._dispatcher(evt)
        finally:
            if gpu_active:
                set_gpu_session_active(False)
            with contextlib.suppress(RuntimeError, AttributeError):  # pragma: no cover - Qt edge
                self.doneCurrent()
        if handled:
            # The dispatcher mutated the active layer in place. When it
            # reports a bounded ``last_damage`` rect we can let the
            # document patch only that region of the cached composite —
            # ``mark_composite_dirty`` keeps the rest of the cache,
            # which is the dominant per-dab cost when materials add a
            # full-canvas layer that would otherwise be re-composited
            # on every brush stamp. Without a damage rect we fall back
            # to a full invalidation so the next paint rebuilds the
            # whole frame.
            self._needs_upload = True
            damage = getattr(self._dispatcher, "last_damage", None)
            if isinstance(damage, DamageRect) and not damage.is_empty:
                self._document.mark_composite_dirty(
                    (damage.x, damage.y, damage.w, damage.h),
                )
                self._pending_damage = self._pending_damage.union(damage)
            else:
                self._document.invalidate_composite()
                self._pending_damage = EMPTY_DAMAGE
            self.document_changed.emit()
            self.update()

    def dragEnterEvent(self, event) -> None:  # pragma: no cover - Qt UI
        from Imervue.paint.material_drop import MATERIAL_MIME_TYPE
        mime = event.mimeData()
        if mime is None:
            event.ignore()
            return
        if mime.hasFormat(MATERIAL_MIME_TYPE) or mime.hasUrls():
            event.acceptProposedAction()
            self.set_drag_overlay_active(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # pragma: no cover - Qt UI
        # Re-affirm on every move so Qt keeps showing the move cursor.
        event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # pragma: no cover - Qt UI
        # Cursor left the canvas without dropping — clear the overlay
        # so the visual matches the actual drop-target state.
        self.set_drag_overlay_active(False)
        event.accept()

    def dropEvent(self, event) -> None:  # pragma: no cover - Qt UI
        from Imervue.paint.material_drop import (
            MATERIAL_MIME_TYPE,
            commit_material_to_document,
            load_material_image,
        )
        # Always clear the highlight when the drag completes, even on
        # ignore paths — leaving it on after a rejected drop would
        # mislead the user into thinking the drop succeeded.
        self.set_drag_overlay_active(False)
        mime = event.mimeData()
        if mime is None:
            event.ignore()
            return
        path: str | None = None
        if mime.hasFormat(MATERIAL_MIME_TYPE):
            blob = mime.data(MATERIAL_MIME_TYPE)
            try:
                path = bytes(blob.data()).decode("utf-8")
            except UnicodeDecodeError:
                path = None
        elif mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    break
        if not path:
            event.ignore()
            return
        try:
            tile = load_material_image(path)
        except (OSError, ValueError):
            event.ignore()
            return
        pos = event.position() if hasattr(event, "position") else event.pos()
        sx = float(pos.x())
        sy = float(pos.y())
        ix, iy = self._screen_to_image(sx, sy)
        commit_material_to_document(
            self._document, tile,
            drop_x=int(round(ix)), drop_y=int(round(iy)),
        )
        self.document_changed.emit()
        self._needs_upload = True
        self.update()
        event.acceptProposedAction()

    def set_drag_overlay_active(self, active: bool) -> None:
        """Toggle the drag-target highlight and request a repaint.

        Pulled out of the Qt drag handlers so unit tests can flip
        the flag and assert the canvas re-renders with / without
        the blue overlay.
        """
        new_state = bool(active)
        if self._drag_overlay_active == new_state:
            return
        self._drag_overlay_active = new_state
        self.update()

    def _is_pan_button(self, event: QMouseEvent) -> bool:
        if event.button() == Qt.MouseButton.MiddleButton:
            return True
        return bool(
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.AltModifier,
        )
