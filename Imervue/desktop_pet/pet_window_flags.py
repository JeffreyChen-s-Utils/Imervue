"""Window flags, opacity and fullscreen hiding for :class:`PetWindow`.

``PetWindowFlagsMixin`` owns the frameless / on-top-or-bottom / click-through
flag combination, the settings that re-apply it (click-through, always on
bottom), the drag lock and edge-snap threshold, window opacity, and hiding
while another app is fullscreen. It relies on the host window's
``_click_through``, ``_always_on_bottom``, ``_anchor_locked``,
``_snap_threshold``, ``_hide_on_fullscreen``, ``_hidden_by_fullscreen``,
``_fullscreen_detector`` and ``_canvas`` attributes and its ``_persist``.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from Imervue.desktop_pet import pet_placement
from Imervue.desktop_pet.fullscreen_detector import FullscreenDetector


class PetWindowFlagsMixin:
    """Window-flag, opacity and fullscreen-hide behaviour mixed into ``PetWindow``."""

    # =====================================================================
    # Window flags + visibility
    # =====================================================================

    def _configure_window_flags(
        self, *, click_through: bool, on_bottom: bool,
    ) -> None:
        """Build the frameless / on-top-or-bottom / tool /
        optionally-transparent-for-input flag combo and apply it.
        ``WindowDoesNotAcceptFocus`` runs in tandem with on-bottom
        so the pet doesn't steal focus when running as a desktop
        widget under other apps."""
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool   # no taskbar entry, no Alt-Tab
        )
        if on_bottom:
            # WindowStaysOnBottomHint is the explicit "behind
            # everything" hint Qt exposes; DoesNotAcceptFocus
            # keeps clicks from raising the pet to the foreground.
            flags |= Qt.WindowType.WindowStaysOnBottomHint
            flags |= Qt.WindowType.WindowDoesNotAcceptFocus
        else:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if click_through:
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)

    def set_click_through(self, enabled: bool) -> None:
        """Toggle whether clicks pass through to the desktop.
        Re-applying the flag bitmask forces Qt to re-create the
        native window, so we preserve geometry across the cycle."""
        enabled = bool(enabled)
        if enabled == self._click_through:
            return
        self._click_through = enabled
        self._reapply_flags()
        self._persist(click_through=enabled)

    def click_through_enabled(self) -> bool:
        return self._click_through

    def set_always_on_bottom(self, enabled: bool) -> None:
        """Switch between on-top and on-bottom Z-order. On-bottom
        gives the pet the "desktop widget" feel — it sits behind
        every other window and doesn't steal focus."""
        enabled = bool(enabled)
        if enabled == self._always_on_bottom:
            return
        self._always_on_bottom = enabled
        self._reapply_flags()
        self._persist(always_on_bottom=enabled)

    def always_on_bottom(self) -> bool:
        return self._always_on_bottom

    def set_anchor_locked(self, locked: bool) -> None:
        """Disable / re-enable drag-to-move. Lock survives across
        restarts via the settings file."""
        self._anchor_locked = bool(locked)
        self._persist(anchor_locked=self._anchor_locked)

    def anchor_locked(self) -> bool:
        return self._anchor_locked

    def set_snap_threshold(self, px: int) -> None:
        self._snap_threshold = max(0, min(200, int(px)))
        self._persist(snap_threshold=self._snap_threshold)

    def snap_threshold(self) -> int:
        return self._snap_threshold

    def _reapply_flags(self) -> None:
        """Common path for any flag-change toggle: snapshot the
        current geometry, re-set flags, restore geometry, and
        re-show if we were visible (Qt hides on flag change).

        Qt's ``setWindowFlags`` re-creates the underlying native
        window on Windows, which silently drops every widget
        attribute (including the translucent-background flags we
        rely on). We re-apply them here, plus force a fresh canvas
        repaint after the re-show — otherwise the first post-toggle
        frame can render with an opaque (black) backdrop until the
        next QTimer tick."""
        geom = self.geometry()
        was_visible = self.isVisible()
        self._configure_window_flags(
            click_through=self._click_through,
            on_bottom=self._always_on_bottom,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setGeometry(geom)
        if was_visible:
            self.show()
            self._canvas.update()

    # ---- opacity -----------------------------------------------

    def set_pet_opacity(self, value: float) -> None:
        """Window-level opacity, 0.1 - 1.0. ``setWindowOpacity``
        composites the entire overlay (puppet + WA translucent
        background) so the pet fades gracefully rather than just
        the puppet pixels."""
        value = max(0.1, min(1.0, float(value)))
        self.setWindowOpacity(value)
        self._persist(opacity=value)

    def pet_opacity(self) -> float:
        return float(self.windowOpacity())

    # =====================================================================
    # Fullscreen hide / restore
    # =====================================================================

    def set_hide_on_fullscreen(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self._hide_on_fullscreen = enabled
        self._persist(hide_on_fullscreen=enabled)
        if enabled:
            if self._fullscreen_detector is None:
                self._fullscreen_detector = FullscreenDetector(
                    self._screen_rect_for_detector, parent=self,
                )
                self._fullscreen_detector.state_changed.connect(
                    self._on_fullscreen_state_changed,
                )
            if self.isVisible():
                self._fullscreen_detector.start()
        elif self._fullscreen_detector is not None:
            self._fullscreen_detector.stop()
            # If the pet was forcibly hidden by a previous fullscreen
            # event, bring it back so the user isn't left looking at a
            # missing pet after toggling the option off.
            if self._hidden_by_fullscreen:
                self._hidden_by_fullscreen = False
                self.show()

    def hide_on_fullscreen(self) -> bool:
        return self._hide_on_fullscreen

    def _screen_rect_for_detector(self):   # pragma: no cover - Qt geometry
        return pet_placement.screen_rect_for_detector(self)

    def _on_fullscreen_state_changed(   # pragma: no cover - Qt UI
        self, is_fullscreen: bool,
    ) -> None:
        if is_fullscreen and self.isVisible():
            self._hidden_by_fullscreen = True
            self.hide()
        elif not is_fullscreen and self._hidden_by_fullscreen:
            self._hidden_by_fullscreen = False
            self.show()
