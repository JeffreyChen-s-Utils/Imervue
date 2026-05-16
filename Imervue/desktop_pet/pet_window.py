"""Desktop-pet overlay window — full edition.

A top-level frameless / transparent-background window that hosts
a :class:`PuppetCanvas` in pet mode. The pet inherits the entire
Puppet runtime — same parameters, motions, expressions, physics,
live-input drivers — and adds the polish that makes it feel like
a commercial desktop widget:

* Drag-to-move with edge-snap on release (snaps onto whichever
  edge of the active screen the user releases near; off-screen
  drags clamp back inside).
* Click-through toggle so the pet can become decorative without
  blocking interaction with whatever's behind it.
* Right-click context menu with submenus for motions and
  expressions discovered from the loaded rig, plus quick-access
  toggles for visibility / drivers / size / opacity / anchor /
  on-top vs on-bottom.
* Left-click hit detection that maps the click into puppet-canvas
  coordinates and plays the linked motion / expression if any
  :class:`HitArea` covers the hit drawable.
* Anchor lock so accidental drags can't reposition the pet.
* Opacity slider (window-level, 0.1 - 1.0).
* Always-on-bottom mode for desktop-widget feel (pet sits behind
  every other window instead of on top).
* Hide-on-fullscreen — politely vanishes while another app holds
  fullscreen on the pet's monitor.
* Speech bubble that pops above the pet on hit / motion triggers.
* Pause-when-hidden: the canvas tick timer stops while the
  overlay is hidden so a dormant pet costs zero CPU.
* Persistence: every user-tweakable knob round-trips through
  :mod:`Imervue.desktop_pet.settings` so the pet returns to the
  same state on the next Imervue launch.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QPoint, QRect, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QMenu,
    QVBoxLayout,
    QWidget,
)

from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.edge_snap import (
    Rect,
    snap_to_screen_edges,
)
from Imervue.desktop_pet.fullscreen_detector import FullscreenDetector
from Imervue.desktop_pet.speech_bubble import SpeechBubble
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document_io import load_puppet
from Imervue.puppet.hit_test import hit_test
from Imervue.puppet.idle_driver import IdleDriver
from Imervue.puppet.idle_motion_cycler import IdleMotionCycler
from Imervue.puppet.input_engine import InputEngine
from Imervue.puppet.motion_player import MotionPlayer

if TYPE_CHECKING:
    from Imervue.puppet.document import PuppetDocument
    from Imervue.puppet.webcam_tracker import WebcamTracker

logger = logging.getLogger("Imervue.desktop_pet.pet_window")

DEFAULT_PET_SIZE: tuple[int, int] = (320, 480)
"""Initial overlay size, in screen pixels. Vertical 3:4 slot
matches the typical aspect of a rigged character; resize presets
swap into other slots without losing this proportion."""

SIZE_PRESETS: dict[str, tuple[int, int]] = {
    "small": (200, 300),
    "medium": (320, 480),
    "large": (480, 720),
}

DEFAULT_GREETINGS: tuple[str, ...] = (
    "Hello!",
    "Hi there!",
    "What's up?",
    "Hey!",
    "Need anything?",
)
"""Short speech-bubble lines used when the user clicks the pet
and the hit area has no associated motion. Kept neutral so the
default voice works for any rig; localized strings come through
:mod:`Imervue.multi_language` when callers want to swap them."""


class PetWindow(QWidget):
    """The on-desktop puppet overlay.

    Long-lived: constructed once per Imervue session, the pet
    shows / hides via :meth:`show` / :meth:`hide` rather than
    being recreated. That keeps the GL context and every
    uploaded texture / VBO alive across visibility toggles, so
    "hide then show" doesn't incur a re-upload.
    """

    visibility_changed = Signal(bool)
    """``True`` after show / ``False`` after hide."""

    moved = Signal(int, int)
    """``(x, y)`` after a drag release lands on its final
    post-snap position. Workspace persists the result."""

    hit_triggered = Signal(str)
    """The ID of the :class:`HitArea` that fired, or ``""`` when
    the click landed on a drawable that isn't covered by any
    hit area (used to drive default greetings)."""

    def __init__(self) -> None:
        super().__init__(None)
        # Snapshot the persisted state once at startup so every
        # subsystem we wire up below can read its initial value
        # from the same dict. ``settings.load()`` is cheap (pure
        # python dict copy + clamp), but caching it avoids a
        # subtle bug where two consecutive ``load()`` calls in
        # this ctor could observe each other's writes.
        self._settings = pet_settings.load()
        self._configure_window_flags(
            click_through=bool(self._settings["click_through"]),
            on_bottom=bool(self._settings["always_on_bottom"]),
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        size = SIZE_PRESETS.get(
            self._settings["size_preset"], DEFAULT_PET_SIZE,
        )
        self.resize(*size)
        self.setWindowOpacity(float(self._settings["opacity"]))

        # The puppet canvas owns the GL surface. Pet mode skips
        # the editor's checker backdrop / selection overlay and
        # clears to fully transparent so the host window's
        # WA_TranslucentBackground actually shows through.
        self._canvas = PuppetCanvas(self, pet_mode=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        # ---- interaction state ---------------------------------
        # ``_anchor_locked`` is the user-toggled "freeze position"
        # flag; ``_click_through`` is the OS-level transparent-
        # for-input flag. They're independent — you can lock the
        # pet AND make it click-through (purely decorative), or
        # have either alone.
        self._click_through: bool = bool(self._settings["click_through"])
        self._anchor_locked: bool = bool(self._settings["anchor_locked"])
        self._always_on_bottom: bool = bool(self._settings["always_on_bottom"])
        self._dragging: bool = False
        self._drag_offset: QPoint = QPoint(0, 0)
        self._snap_threshold: int = int(self._settings["snap_threshold"])
        self._press_pos: QPoint | None = None
        self._install_event_filter()

        # ---- live drivers --------------------------------------
        self._input_engine = InputEngine(self._canvas, parent=self)
        self._idle_driver: IdleDriver | None = None
        self._webcam_tracker: WebcamTracker | None = None
        self._motion_player = MotionPlayer(self._canvas)
        self._idle_cycler: IdleMotionCycler | None = None

        # ---- speech bubble + greetings -------------------------
        self._speech_enabled: bool = bool(self._settings["speech_enabled"])
        self._speech: SpeechBubble | None = None
        self._next_greeting_index: int = 0

        # ---- tick timer ----------------------------------------
        # 33 ms ≈ 30 FPS. Stopped while the overlay is hidden so
        # the dormant pet doesn't tick. We also pause during a
        # detected fullscreen so a background-running game gets
        # its frames undisturbed.
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._canvas.update)

        # ---- fullscreen detector -------------------------------
        # Lazy-created on first ``hide_on_fullscreen`` enable so
        # users who opt out don't pay for the 1 Hz poll.
        self._hide_on_fullscreen: bool = bool(self._settings["hide_on_fullscreen"])
        self._fullscreen_detector: FullscreenDetector | None = None
        self._hidden_by_fullscreen: bool = False

        # ---- restore position ----------------------------------
        self._restore_position()

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
        pet_settings.update(click_through=enabled)

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
        pet_settings.update(always_on_bottom=enabled)

    def always_on_bottom(self) -> bool:
        return self._always_on_bottom

    def set_anchor_locked(self, locked: bool) -> None:
        """Disable / re-enable drag-to-move. Lock survives across
        restarts via the settings file."""
        self._anchor_locked = bool(locked)
        pet_settings.update(anchor_locked=self._anchor_locked)

    def anchor_locked(self) -> bool:
        return self._anchor_locked

    def set_snap_threshold(self, px: int) -> None:
        self._snap_threshold = max(0, min(200, int(px)))
        pet_settings.update(snap_threshold=self._snap_threshold)

    def snap_threshold(self) -> int:
        return self._snap_threshold

    def _reapply_flags(self) -> None:
        """Common path for any flag-change toggle: snapshot the
        current geometry, re-set flags, restore geometry, and
        re-show if we were visible (Qt hides on flag change)."""
        geom = self.geometry()
        was_visible = self.isVisible()
        self._configure_window_flags(
            click_through=self._click_through,
            on_bottom=self._always_on_bottom,
        )
        self.setGeometry(geom)
        if was_visible:
            self.show()

    # ---- opacity -----------------------------------------------

    def set_pet_opacity(self, value: float) -> None:
        """Window-level opacity, 0.1 - 1.0. ``setWindowOpacity``
        composites the entire overlay (puppet + WA translucent
        background) so the pet fades gracefully rather than just
        the puppet pixels."""
        value = max(0.1, min(1.0, float(value)))
        self.setWindowOpacity(value)
        pet_settings.update(opacity=value)

    def pet_opacity(self) -> float:
        return float(self.windowOpacity())

    # ---- visibility hooks --------------------------------------

    def showEvent(self, event) -> None:   # pragma: no cover - Qt UI
        super().showEvent(event)
        # Resume ticking — paintGL needs the timer ticks to
        # advance physics / motions while no input event is firing.
        self._tick.start()
        if self._hide_on_fullscreen and self._fullscreen_detector is not None:
            self._fullscreen_detector.start()
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:   # pragma: no cover - Qt UI
        super().hideEvent(event)
        # Stop the tick timer so the dormant pet doesn't repaint.
        self._tick.stop()
        if self._fullscreen_detector is not None:
            self._fullscreen_detector.stop()
        if self._speech is not None:
            self._speech.close_bubble()
        self.visibility_changed.emit(False)

    # =====================================================================
    # Rig loading
    # =====================================================================

    def load_puppet_file(self, path: str | Path) -> bool:
        """Load a ``.puppet`` zip and bind its document.
        Returns ``True`` on success and persists the path so the
        next launch reopens the same rig."""
        try:
            document = load_puppet(path)
        except Exception as exc:   # noqa: BLE001 - load_puppet has many failure modes
            logger.warning("desktop-pet failed to load %s: %s", path, exc)
            return False
        self.load_document(document)
        pet_settings.update(last_rig_path=str(path))
        return True

    def load_document(self, document: PuppetDocument | None) -> None:
        """Bind ``document`` directly — used when the workspace
        passes the rig already loaded by the Puppet tab."""
        if self._speech is not None:
            self._speech.close_bubble()
        self._canvas.load_document(document)

    def document(self) -> PuppetDocument | None:
        return self._canvas.document()

    def canvas(self) -> PuppetCanvas:
        return self._canvas

    # =====================================================================
    # Drag-to-move + hit detection
    # =====================================================================

    def _install_event_filter(self) -> None:
        self._canvas.installEventFilter(self)

    def eventFilter(self, obj, event):   # pragma: no cover - Qt UI
        if obj is self._canvas:
            etype = event.type()
            if etype == event.Type.MouseButtonPress:
                self._on_press(event)
            elif etype == event.Type.MouseMove:
                self._on_move(event)
            elif etype == event.Type.MouseButtonRelease:
                self._on_release(event)
            elif etype == event.Type.ContextMenu:
                self._show_context_menu(event.globalPos())
                return True
        return super().eventFilter(obj, event)

    def _on_press(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if self._click_through:
            return
        if event.button() == Qt.MouseButton.RightButton:
            # Right-click → context menu. Eat the event so the
            # canvas doesn't try to start a pan.
            self._show_context_menu(event.globalPosition().toPoint())
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._press_pos = event.position().toPoint()
        if not self._anchor_locked:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self._canvas.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _on_move(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if not self._dragging:
            return
        new_pos = event.globalPosition().toPoint() - self._drag_offset
        self.move(new_pos)
        if self._speech is not None:
            self._speech.anchor_to(self.geometry())

    def _on_release(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if event.button() != Qt.MouseButton.LeftButton:
            return
        was_dragging = self._dragging
        self._dragging = False
        self._canvas.unsetCursor()
        # A short release without movement is a "click" — try
        # hit-area routing. A real drag triggers edge-snap + position
        # persistence instead.
        press = self._press_pos
        self._press_pos = None
        if was_dragging:
            self._apply_edge_snap()
            pos = self.pos()
            pet_settings.update(position=[pos.x(), pos.y()])
            self.moved.emit(pos.x(), pos.y())
            if press is not None and (event.position().toPoint() - press).manhattanLength() < 6:
                self._handle_click(press)
        else:
            self._handle_click(press)

    def _handle_click(self, widget_pos: QPoint | None) -> None:   # pragma: no cover - GL needed
        """A click on the pet body → run hit-test → play the
        linked motion / show a default greeting if nothing
        matches."""
        if widget_pos is None:
            return
        document = self.document()
        if document is None:
            return
        image_xy = self._widget_to_image(widget_pos)
        if image_xy is None:
            return
        area = hit_test(
            document, image_xy[0], image_xy[1],
            deformed_vertices=self._canvas._deformed_vertices,   # noqa: SLF001
        )
        area_id = area.id if area is not None else ""
        self.hit_triggered.emit(area_id)
        if area is not None and area.motion:
            self._play_motion_by_name(area.motion)
            if self._speech_enabled and area.id:
                self._show_speech(area.id)
        elif self._speech_enabled:
            self._show_speech(self._next_default_greeting())

    def _widget_to_image(self, widget_pos: QPoint) -> tuple[float, float] | None:
        """Inverse of the canvas's modelview transform: undo
        pan + zoom so a widget-space mouse position becomes the
        puppet-canvas (document) coordinate hit-test expects."""
        canvas = self._canvas
        zoom = float(getattr(canvas, "_zoom", 1.0))
        if zoom <= 0:
            return None
        pan_x = float(getattr(canvas, "_pan_x", 0.0))
        pan_y = float(getattr(canvas, "_pan_y", 0.0))
        image_x = (widget_pos.x() - pan_x) / zoom
        image_y = (widget_pos.y() - pan_y) / zoom
        return image_x, image_y

    def _apply_edge_snap(self) -> None:   # pragma: no cover - Qt geometry
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        window_rect = Rect(self.x(), self.y(), self.width(), self.height())
        screen_rect = Rect(avail.x(), avail.y(), avail.width(), avail.height())
        new_x, new_y = snap_to_screen_edges(
            window_rect, screen_rect, threshold=self._snap_threshold,
        )
        if (new_x, new_y) != (self.x(), self.y()):
            self.move(new_x, new_y)

    # =====================================================================
    # Context menu
    # =====================================================================

    def _show_context_menu(self, global_pos: QPoint) -> None:   # pragma: no cover - Qt UI
        tr = language_wrapper.language_word_dict.get
        menu = QMenu(self)
        hide_action = menu.addAction(tr("desktop_pet_menu_hide", "Hide pet"))
        hide_action.triggered.connect(self.hide)
        menu.addSeparator()
        self._build_drivers_submenu(menu, tr)
        self._build_motions_submenu(menu, tr)
        self._build_expressions_submenu(menu, tr)
        menu.addSeparator()
        self._build_toggle_actions(menu, tr)
        menu.addSeparator()
        self._build_size_submenu(menu, tr)
        menu.exec(global_pos)

    def _build_drivers_submenu(self, menu: QMenu, tr) -> None:   # pragma: no cover - Qt UI
        """Live-input toggles. Each driver's "is it running?" state
        is sourced from its own object so the menu's check-state
        always matches the world."""
        drivers_menu = menu.addMenu(tr("desktop_pet_group_drivers", "Live drivers"))
        idle_running = (
            self._idle_driver is not None and self._idle_driver.is_enabled()
        )
        self._add_driver_action(
            drivers_menu, tr("desktop_pet_auto_idle", "Auto idle (breath + drift)"),
            idle_running, self.set_auto_idle_enabled,
        )
        idle_motion_running = (
            self._idle_cycler is not None and self._idle_cycler.is_enabled()
        )
        self._add_driver_action(
            drivers_menu, tr("desktop_pet_idle_motion", "Idle motions"),
            idle_motion_running, self.set_idle_motion_enabled,
        )
        self._add_driver_action(
            drivers_menu, tr("desktop_pet_auto_blink", "Auto-blink"),
            self._input_engine.blink_enabled(), self.set_auto_blink_enabled,
        )
        self._add_driver_action(
            drivers_menu, tr("desktop_pet_drag_track", "Drag-track head"),
            self._input_engine.drag_enabled(), self.set_drag_track_enabled,
        )
        self._add_driver_action(
            drivers_menu, tr("desktop_pet_mic_lipsync", "Mic lip-sync"),
            self._input_engine.lipsync_enabled(),
            self.set_mic_lipsync_enabled,
        )
        self._add_driver_action(
            drivers_menu, tr("desktop_pet_webcam", "Webcam tracking"),
            self._webcam_tracker is not None and self._webcam_tracker.is_enabled(),
            self.set_webcam_tracking_enabled,
        )

    def _build_motions_submenu(self, menu: QMenu, tr) -> None:   # pragma: no cover - Qt UI
        """Lists every motion in the active rig. Each entry plays
        that motion directly. Disabled when no rig is loaded."""
        motions_menu = menu.addMenu(tr("desktop_pet_menu_play_motion", "Play motion"))
        document = self.document()
        if document is None or not document.motions:
            motions_menu.setEnabled(False)
            return
        for motion in document.motions:
            action = motions_menu.addAction(motion.name or "(unnamed)")
            action.triggered.connect(
                lambda _checked=False, m=motion: self._play_motion(m),
            )

    def _build_expressions_submenu(self, menu: QMenu, tr) -> None:   # pragma: no cover - Qt UI
        expressions_menu = menu.addMenu(
            tr("desktop_pet_menu_apply_expression", "Apply expression"),
        )
        document = self.document()
        if document is None or not document.expressions:
            expressions_menu.setEnabled(False)
            return
        for expression in document.expressions:
            action = expressions_menu.addAction(expression.name or "(unnamed)")
            action.triggered.connect(
                lambda _checked=False, e=expression: self._apply_expression(e.name),
            )

    def _build_toggle_actions(self, menu: QMenu, tr) -> None:   # pragma: no cover - Qt UI
        """The five top-level checkable toggles (anchor, click-
        through, on-bottom, fullscreen-hide, speech bubble). Each
        is wired so the user can flip it from the right-click menu
        as a faster alternative to digging through the tab."""
        for key, default, attr, setter in (
            ("desktop_pet_anchor", "Lock position",
             "_anchor_locked", self.set_anchor_locked),
            ("desktop_pet_click_through", "Click-through (let mouse pass)",
             "_click_through", self.set_click_through),
            ("desktop_pet_on_bottom", "Always on bottom (desktop widget)",
             "_always_on_bottom", self.set_always_on_bottom),
            ("desktop_pet_hide_fullscreen", "Hide when other app is fullscreen",
             "_hide_on_fullscreen", self.set_hide_on_fullscreen),
            ("desktop_pet_speech", "Speech bubble on click",
             "_speech_enabled", self.set_speech_enabled),
        ):
            action = menu.addAction(tr(key, default))
            action.setCheckable(True)
            action.setChecked(bool(getattr(self, attr)))
            action.triggered.connect(setter)

    def _build_size_submenu(self, menu: QMenu, tr) -> None:   # pragma: no cover - Qt UI
        size_menu = menu.addMenu(tr("desktop_pet_menu_size", "Size"))
        size_labels = {
            "small": tr("desktop_pet_size_small", "Small"),
            "medium": tr("desktop_pet_size_medium", "Medium"),
            "large": tr("desktop_pet_size_large", "Large"),
        }
        current = self._current_size_preset()
        for preset in ("small", "medium", "large"):
            action = size_menu.addAction(size_labels[preset])
            action.setCheckable(True)
            action.setChecked(preset == current)
            action.triggered.connect(
                lambda _checked=False, p=preset: self.set_size_preset(p),
            )

    def _add_driver_action(
        self, parent_menu: QMenu, label: str, current: bool, setter,
    ) -> QAction:   # pragma: no cover - Qt UI
        action = parent_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(current)
        action.triggered.connect(lambda checked: setter(checked))
        return action

    # =====================================================================
    # Live drivers
    # =====================================================================

    def set_auto_blink_enabled(self, enabled: bool) -> None:
        self._input_engine.set_blink_enabled(bool(enabled))
        self._persist_driver("auto_blink", bool(enabled))

    def set_auto_idle_enabled(self, enabled: bool) -> None:
        if enabled:
            if self._idle_driver is None:
                self._idle_driver = IdleDriver(self._canvas, parent=self)
            self._idle_driver.set_enabled(True)
        elif self._idle_driver is not None:
            self._idle_driver.set_enabled(False)
        self._persist_driver("auto_idle", bool(enabled))

    def set_idle_motion_enabled(self, enabled: bool) -> None:
        if enabled:
            if self._idle_cycler is None:
                self._idle_cycler = IdleMotionCycler(
                    self._motion_player, self._canvas, parent=self,
                )
            self._idle_cycler.set_enabled(True)
        elif self._idle_cycler is not None:
            self._idle_cycler.set_enabled(False)
        self._persist_driver("idle_motion", bool(enabled))

    def set_mic_lipsync_enabled(self, enabled: bool) -> bool:
        ok = bool(self._input_engine.set_lipsync_enabled(bool(enabled)))
        self._persist_driver("mic_lipsync", bool(enabled and ok))
        return ok

    def set_webcam_tracking_enabled(self, enabled: bool) -> bool:
        if enabled:
            if self._webcam_tracker is None:
                from Imervue.puppet.webcam_tracker import WebcamTracker
                self._webcam_tracker = WebcamTracker(self._canvas, parent=self)
            ok = bool(self._webcam_tracker.set_enabled(True))
        else:
            if self._webcam_tracker is not None:
                self._webcam_tracker.set_enabled(False)
            ok = True
        self._persist_driver("webcam_tracking", bool(enabled and ok))
        return ok

    def set_drag_track_enabled(self, enabled: bool) -> None:
        self._input_engine.set_drag_enabled(bool(enabled))
        self._persist_driver("drag_track", bool(enabled))

    def _persist_driver(self, key: str, value: bool) -> None:
        drivers = dict(self._settings.get("drivers", {}))
        drivers[key] = bool(value)
        self._settings["drivers"] = drivers
        pet_settings.update(drivers=drivers)

    # =====================================================================
    # Motion / expression playback (context menu + hit-area)
    # =====================================================================

    def _play_motion(self, motion) -> None:
        """Bind ``motion`` on the player and start playback. Used
        from the context-menu motions submenu."""
        self._motion_player.set_motion(motion)
        self._motion_player.play()

    def _play_motion_by_name(self, name: str) -> None:
        document = self.document()
        if document is None:
            return
        for motion in document.motions:
            if motion.name == name:
                self._play_motion(motion)
                return

    def _apply_expression(self, name: str) -> None:
        """Toggle an expression on the canvas. The canvas's
        expression stack tolerates duplicates by deduping on
        name, so re-applying the same expression is a no-op
        rather than a double-stack."""
        canvas = self._canvas
        if hasattr(canvas, "add_expression"):
            canvas.add_expression(name)

    # =====================================================================
    # Speech bubble
    # =====================================================================

    def set_speech_enabled(self, enabled: bool) -> None:
        self._speech_enabled = bool(enabled)
        pet_settings.update(speech_enabled=self._speech_enabled)
        if not enabled and self._speech is not None:
            self._speech.close_bubble()

    def speech_enabled(self) -> bool:
        return self._speech_enabled

    def _show_speech(self, text: str) -> None:   # pragma: no cover - Qt UI
        if not self._speech_enabled or not text:
            return
        if self._speech is None:
            self._speech = SpeechBubble()
        self._speech.anchor_to(self.geometry())
        self._speech.show_message(text)

    def _next_default_greeting(self) -> str:
        # Round-robin through DEFAULT_GREETINGS so consecutive
        # clicks don't repeat the same line.
        idx = self._next_greeting_index % len(DEFAULT_GREETINGS)
        self._next_greeting_index += 1
        return DEFAULT_GREETINGS[idx]

    # =====================================================================
    # Fullscreen hide / restore
    # =====================================================================

    def set_hide_on_fullscreen(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self._hide_on_fullscreen = enabled
        pet_settings.update(hide_on_fullscreen=enabled)
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
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        return screen.geometry() if screen is not None else None

    def _on_fullscreen_state_changed(   # pragma: no cover - Qt UI
        self, is_fullscreen: bool,
    ) -> None:
        if is_fullscreen and self.isVisible():
            self._hidden_by_fullscreen = True
            self.hide()
        elif not is_fullscreen and self._hidden_by_fullscreen:
            self._hidden_by_fullscreen = False
            self.show()

    # =====================================================================
    # Size presets
    # =====================================================================

    def set_size_preset(self, preset: str) -> None:
        size = SIZE_PRESETS.get(preset)
        if size is None:
            return
        old_centre = self.geometry().center()
        self.resize(*size)
        new_geom = self.geometry()
        new_geom.moveCenter(old_centre)
        self.setGeometry(new_geom)
        self._apply_edge_snap()
        pet_settings.update(size_preset=preset)

    def _current_size_preset(self) -> str:
        w, h = self.width(), self.height()
        for name, (pw, ph) in SIZE_PRESETS.items():
            if (pw, ph) == (w, h):
                return name
        return "medium"

    # =====================================================================
    # Position restore
    # =====================================================================

    def _restore_position(self) -> None:   # pragma: no cover - Qt geometry
        """Apply the saved ``(x, y)`` if it falls inside any
        connected screen — otherwise default to the bottom-right
        of the primary screen (the canonical desktop-pet spot).
        Multi-monitor disconnection between sessions is the most
        common cause of "saved position outside any screen",
        which we handle by gracefully falling back."""
        pos = self._settings.get("position", [-1, -1])
        if not (isinstance(pos, list) and len(pos) == 2):
            self._move_to_default_corner()
            return
        x, y = int(pos[0]), int(pos[1])
        if x == -1 and y == -1:
            self._move_to_default_corner()
            return
        # Validate: at least one screen must contain the
        # top-left of the saved rect.
        test_rect = QRect(x, y, self.width(), self.height())
        if any(
            screen.geometry().intersects(test_rect)
            for screen in QGuiApplication.screens()
        ):
            self.move(x, y)
        else:
            self._move_to_default_corner()

    def _move_to_default_corner(self) -> None:   # pragma: no cover - Qt geometry
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        x = avail.right() - self.width() - 16
        y = avail.bottom() - self.height() - 16
        self.move(x, y)
