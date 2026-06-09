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
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet import pet_placement
from Imervue.desktop_pet.fullscreen_detector import FullscreenDetector
from Imervue.desktop_pet.click_sfx import (
    EVENT_CLICK as SFX_CLICK,
    EVENT_DRAG as SFX_DRAG,
    EVENT_DROP as SFX_DROP,
    EVENT_NOTIFY as SFX_NOTIFY,
)
from Imervue.desktop_pet.pet_context_menu import build_context_menu
from Imervue.desktop_pet.hotkey_manager import (
    ACTION_SPEAK_NOW,
    ACTION_TOGGLE_CLICK_THROUGH,
    ACTION_TOGGLE_LOCK,
    ACTION_TOGGLE_VISIBLE,
)
from Imervue.desktop_pet.pet_drivers import (
    ClickSfxController,
    IdleMinigameController,
    LlmDialogueController,
    MusicRhythmController,
)
from Imervue.desktop_pet.pet_features import build_integration_controllers
from Imervue.desktop_pet.pet_script import (
    PetScript,
    PetScriptEngine,
    PetScriptError,
    load_script,
)
from Imervue.desktop_pet.speech_bubble import SpeechBubble
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document_io import load_puppet
from Imervue.puppet.hit_test import hit_test
from Imervue.puppet.idle_driver import IdleDriver
from Imervue.puppet.idle_motion_cycler import IdleMotionCycler
from Imervue.puppet.input_engine import InputEngine
from Imervue.puppet.motion_picker import pick_random_motion_in_group
from Imervue.puppet.motion_player import MotionPlayer
from Imervue.puppet.mouse_gaze_driver import MouseGazeDriver
from Imervue.puppet.virtual_camera import VirtualCameraOutput

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

PAINT_TICK_INTERVAL_MS: int = 33
"""≈ 30 FPS canvas repaint cadence while the overlay is visible."""

SCRIPT_TICK_INTERVAL_MS: int = 1000
"""1 Hz heartbeat that fires the script engine's scheduled chimes."""

PET_IDLE_CYCLE_DURATION_S: float = 4.0
"""Override the puppet module's 8s default for the desktop overlay.
On the desktop the pet is decorative and benefits from livelier
turnover; the editor workspace still uses the slower default so
authoring previews aren't constantly interrupted."""

DRAG_MOTION_GROUP: str = "Drag"
"""Cubism-convention group name played the moment the user starts
dragging the pet. Rigs without a Drag-group motion silently no-op
so the feature is opt-in via authoring, not via a toggle."""

LAND_MOTION_GROUP: str = "Land"
"""Played when the user drops the pet. Pairs with ``DRAG_MOTION_GROUP``
to bracket a drag interaction; either or both can be absent without
breaking the drag flow."""

DROP_MOTION_GROUP: str = "Drop"
"""Played when the user drops *external content* (a file from
Explorer / Finder) onto the pet. Distinct from ``LAND_MOTION_GROUP``
so rigs can react differently to "moved the pet" vs "fed the pet
something"."""

PUPPET_FILE_SUFFIX: str = ".puppet"
"""Extension treated as "drop this and the pet loads it as its new
rig". Anything else triggers the generic Drop reaction instead."""


def _llm_situation_tag(area_id: str | None, motion_name: str | None) -> str:
    """Pick the situation label to pass to the LLM. Hit-area
    context wins over motion context which wins over the generic
    greeting fallback — same priority chain the script engine
    uses when looking up scripted lines."""
    if area_id:
        return f"hit:{area_id}"
    if motion_name:
        return f"motion:{motion_name}"
    return "greeting"


def classify_drop_paths(paths: list[Path]) -> tuple[str, Path | None]:
    """Decide what the pet should do with a file-drop payload.

    Returns ``("puppet", path)`` when the drop contains at least one
    ``.puppet`` archive (the first one wins — multiple-file drops
    aren't a use case worth solving), ``("other", path_or_None)``
    when the drop has files but none are a rig (the first path is
    handed back so callers can log / display it), or ``("none", None)``
    for an empty payload.

    Pure helper so the dispatcher logic is tested without spinning
    up a QMimeData — Qt's drop machinery is hard to fake."""
    if not paths:
        return ("none", None)
    for path in paths:
        if path.suffix.lower() == PUPPET_FILE_SUFFIX:
            return ("puppet", path)
    return ("other", paths[0])

from Imervue.desktop_pet.pet_script import DEFAULT_GREETINGS  # noqa: F401, E402
"""Re-export so callers / tests that imported the old constant
keep working. The authoritative copy lives in
:mod:`Imervue.desktop_pet.pet_script` alongside the engine."""


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

    def __init__(self, pet_id: str = pet_settings.DEFAULT_PET_ID) -> None:
        super().__init__(None)
        # Pet id identifies which slot under ``user_setting_dict``
        # this instance reads / writes. The primary pet is
        # ``"default"`` (preserves the single-pet schema); extras
        # have stable string ids managed by :mod:`pet_registry`.
        self._pet_id: str = str(pet_id)
        # Snapshot the persisted state once at startup so every
        # subsystem we wire up below can read its initial value
        # from the same dict. ``settings.load()`` is cheap (pure
        # python dict copy + clamp), but caching it avoids a
        # subtle bug where two consecutive ``load()`` calls in
        # this ctor could observe each other's writes.
        self._settings = pet_settings.load(self._pet_id)
        self._init_window_chrome()
        self._init_canvas()
        self._init_interaction_state()
        self._init_drivers_and_voice()
        self._init_feature_controllers()
        # Restore saved position, then wake every persisted driver so
        # a pet launched straight from the tray feels alive without
        # the workspace tab having re-ticked its checkboxes.
        self._restore_position()
        self._restore_drivers()

    def _init_window_chrome(self) -> None:
        """Apply window flags, translucency, drop-accept, size and
        opacity from the snapshotted settings."""
        self._configure_window_flags(
            click_through=bool(self._settings["click_through"]),
            on_bottom=bool(self._settings["always_on_bottom"]),
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        # File-drop hook: a dropped ``.puppet`` archive is auto-loaded
        # as the new rig; anything else fires the Drop motion group.
        # Click-through mode disables drops at the OS level, which is
        # documented as the trade-off in the user guide.
        self.setAcceptDrops(True)
        size = SIZE_PRESETS.get(self._settings["size_preset"], DEFAULT_PET_SIZE)
        self.resize(*size)
        self.setWindowOpacity(float(self._settings["opacity"]))

    def _init_canvas(self) -> None:
        """Build the GL canvas in pet mode and apply the persisted
        drop-shadow so the very first paint already includes it."""
        # The puppet canvas owns the GL surface. Pet mode skips the
        # editor's checker backdrop / selection overlay and clears to
        # fully transparent so the host window's translucent
        # background actually shows through.
        self._canvas = PuppetCanvas(self, pet_mode=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)
        self._canvas.set_pet_shadow(
            enabled=bool(self._settings.get("pet_shadow_enabled", True)),
            opacity=float(self._settings.get("pet_shadow_opacity", 0.7)),
            scale=float(self._settings.get("pet_shadow_scale", 1.0)),
        )

    def _init_interaction_state(self) -> None:
        """Seed the drag / click-through / anchor state and install
        the canvas event filter that drives them."""
        # ``_anchor_locked`` is the user-toggled "freeze position"
        # flag; ``_click_through`` is the OS-level transparent-for-
        # input flag. They're independent — you can lock the pet AND
        # make it click-through, or have either alone.
        self._click_through: bool = bool(self._settings["click_through"])
        self._anchor_locked: bool = bool(self._settings["anchor_locked"])
        self._always_on_bottom: bool = bool(self._settings["always_on_bottom"])
        self._dragging: bool = False
        self._drag_offset: QPoint = QPoint(0, 0)
        self._snap_threshold: int = int(self._settings["snap_threshold"])
        self._press_pos: QPoint | None = None
        self._install_event_filter()

    def _init_drivers_and_voice(self) -> None:
        """Construct the always-present canvas-input drivers, the
        speech / script engine, and the paint + script tick timers."""
        self._input_engine = InputEngine(self._canvas, parent=self)
        self._idle_driver: IdleDriver | None = None
        self._webcam_tracker: WebcamTracker | None = None
        self._motion_player = MotionPlayer(self._canvas)
        self._idle_cycler: IdleMotionCycler | None = None
        self._mouse_gaze: MouseGazeDriver | None = None

        # The pet's "voice" comes from a user-loadable
        # ``.petscript.json``; the engine defaults to the built-in
        # greeting set so an unconfigured pet still talks.
        self._speech_enabled: bool = bool(self._settings["speech_enabled"])
        self._speech: SpeechBubble | None = None
        self._script_engine = PetScriptEngine()
        self._restore_persisted_script()

        # 30 FPS paint tick + a 1 Hz heartbeat for scheduled chimes
        # (finer resolution wouldn't matter — the smallest sensible
        # chime interval is multi-second).
        self._tick = QTimer(self)
        self._tick.setInterval(PAINT_TICK_INTERVAL_MS)
        self._tick.timeout.connect(self._canvas.update)
        self._script_tick = QTimer(self)
        self._script_tick.setInterval(SCRIPT_TICK_INTERVAL_MS)
        self._script_tick.timeout.connect(self._on_script_tick)

    def _init_feature_controllers(self) -> None:
        """Wire the fullscreen detector plus the integration /
        canvas-driver / subsystem controllers the window delegates to."""
        # Fullscreen detector is lazy-created on first enable so users
        # who opt out don't pay for the 1 Hz poll.
        self._hide_on_fullscreen: bool = bool(self._settings["hide_on_fullscreen"])
        self._fullscreen_detector: FullscreenDetector | None = None
        self._hidden_by_fullscreen: bool = False

        # OBS / Twitch / webhook / Windows-notifications / hotkeys
        # share one lazy-worker lifecycle; the registry holds them and
        # the window delegates its public toggles in.
        self._features = build_integration_controllers(self)

        # Virtual camera stays a direct window attribute (vs a
        # controller) because its lazy-construction contract is
        # asserted directly by the pet-window tests.
        self._virtual_camera: VirtualCameraOutput | None = None

        # LLM dialogue, click SFX, music-rhythm and idle-minigame each
        # get a controller owning lazy construction + settings
        # round-trip + persistence (see pet_drivers).
        self._llm = LlmDialogueController(
            self, self._on_llm_line, self._on_llm_failed,
        )
        self._click_sfx_ctl = ClickSfxController(self)
        if bool(self._settings.get("click_sfx_enabled", False)):
            self._click_sfx_ctl.ensure_player()
        self._music_rhythm = MusicRhythmController(self)
        self._idle_minigame = IdleMinigameController(self)

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

    # ---- visibility hooks --------------------------------------

    def showEvent(self, event) -> None:   # pragma: no cover - Qt UI
        super().showEvent(event)
        # Resume ticking — paintGL needs the timer ticks to
        # advance physics / motions while no input event is firing.
        # The 1 Hz script tick wakes up for scheduled chimes.
        self._tick.start()
        self._script_tick.start()
        if self._hide_on_fullscreen and self._fullscreen_detector is not None:
            self._fullscreen_detector.start()
        # Force a fresh canvas repaint on show. Qt does call paintGL
        # automatically after showEvent, but a delayed singleShot
        # update covers the case where textures finish uploading
        # mid-show — without it, the first visible frame can flash
        # white silhouettes on a black backdrop while the GL thread
        # is still wiring up the texture cache.
        QTimer.singleShot(50, self._canvas.update)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:   # pragma: no cover - Qt UI
        super().hideEvent(event)
        # Stop the tick timer so the dormant pet doesn't repaint.
        self._tick.stop()
        self._script_tick.stop()
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
        self._persist(last_rig_path=str(path))
        return True

    def load_document(self, document: PuppetDocument | None) -> None:
        """Bind ``document`` directly — used when the workspace
        passes the rig already loaded by the Puppet tab.

        Schedules a follow-up canvas repaint via QTimer.singleShot
        so the first visible frame has a full chance to upload
        every texture. Without this, rigs with many drawables can
        flash a "white silhouette on black backdrop" frame while
        textures are still uploading on the GL thread."""
        if self._speech is not None:
            self._speech.close_bubble()
        self._canvas.load_document(document)
        # 50 ms is "next event loop tick + a couple of paint frames" —
        # enough for the texture cache to populate without making the
        # rig load feel laggy.
        QTimer.singleShot(50, self._canvas.update)

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
        self._notify_user_activity()
        if not self._anchor_locked:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self._canvas.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.play_random_motion_in_group(DRAG_MOTION_GROUP)
            self._play_sfx(SFX_DRAG)

    def _on_move(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        self._notify_user_activity()
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
            self._persist(
                position=[pos.x(), pos.y()],
                screen_name=self._current_screen_name(),
            )
            self.moved.emit(pos.x(), pos.y())
            click_inside_press_radius = (
                press is not None
                and (event.position().toPoint() - press).manhattanLength() < 6
            )
            if click_inside_press_radius:
                self._handle_click(press)
            else:
                self.play_random_motion_in_group(LAND_MOTION_GROUP)
                self._play_sfx(SFX_DROP)
        else:
            self._handle_click(press)

    def _handle_click(self, widget_pos: QPoint | None) -> None:   # pragma: no cover - GL needed
        """A click on the pet body → run hit-test → play the
        linked motion + speak the scripted line for that area, or
        fall back to a greeting when no hit area covers the click.

        Line selection order:

        1. ``script.hit_responses[area.id]`` — per-area override.
        2. ``script.motion_lines[area.motion]`` — per-motion line
           when the script doesn't override the area itself.
        3. ``script.greetings`` (or the built-in defaults) — the
           generic voice for "nothing better matched".
        """
        area = self._hit_test_at(widget_pos)
        if area is None and self.document() is None:
            # ``_hit_test_at`` returns None for both "no document"
            # and "no hit area matched"; only bail when no rig is
            # loaded at all.
            return
        area_id = area.id if area is not None else ""
        self.hit_triggered.emit(area_id)
        motion_name = area.motion if area is not None else None
        if motion_name:
            self._play_motion_by_name(motion_name)
        self._play_sfx(SFX_CLICK)
        self._speak_click_response(area_id, motion_name)

    def _hit_test_at(self, widget_pos: QPoint | None):
        """Run the document's hit-area test at a widget-space
        position. ``None`` when there's no rig, no transform, or
        no area covers the point."""
        if widget_pos is None:
            return None
        document = self.document()
        if document is None:
            return None
        image_xy = self._widget_to_image(widget_pos)
        if image_xy is None:
            return None
        return hit_test(
            document, image_xy[0], image_xy[1],
            deformed_vertices=self._canvas._deformed_vertices,   # noqa: SLF001
        )

    def _speak_click_response(
        self, area_id: str, motion_name: str | None,
    ) -> None:
        """Show the scripted speech line for a click (if speech is
        on) and fire the LLM in parallel if enabled. The scripted
        line shows immediately for snappy feedback; the LLM reply
        replaces it via ``_on_llm_line`` if/when it lands."""
        if not self._speech_enabled:
            return
        line = (
            self._script_engine.pick_for_hit_area(area_id or None)
            or self._script_engine.pick_for_motion(motion_name)
            or self._script_engine.pick_time_of_day_greeting()
            or self._script_engine.pick_greeting()
        )
        if line:
            self._show_speech(line)
        if not self.llm_dialogue_enabled():
            return
        try:
            self._llm.request_line(_llm_situation_tag(area_id, motion_name))
        except ValueError:
            return

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
        pet_placement.apply_edge_snap(self)

    # =====================================================================
    # Context menu
    # =====================================================================

    def _show_context_menu(self, global_pos: QPoint) -> None:   # pragma: no cover - Qt UI
        build_context_menu(self, global_pos)

    def driver_menu_entries(
        self,
    ) -> list[tuple[str, str, bool, Any]]:   # pragma: no cover - Qt UI
        """Rows for the "Live drivers" submenu: ``(label_key,
        default_label, currently_running, setter)``. Each running
        flag is sourced from the driver's own object so the menu
        check-state always matches the world."""
        idle_running = (
            self._idle_driver is not None and self._idle_driver.is_enabled()
        )
        idle_motion_running = (
            self._idle_cycler is not None and self._idle_cycler.is_enabled()
        )
        gaze_running = (
            self._mouse_gaze is not None and self._mouse_gaze.is_enabled()
        )
        webcam_running = (
            self._webcam_tracker is not None
            and self._webcam_tracker.is_enabled()
        )
        return [
            ("desktop_pet_auto_idle", "Auto idle (breath + drift)",
             idle_running, self.set_auto_idle_enabled),
            ("desktop_pet_idle_motion", "Idle motions",
             idle_motion_running, self.set_idle_motion_enabled),
            ("desktop_pet_auto_blink", "Auto-blink",
             self._input_engine.blink_enabled(), self.set_auto_blink_enabled),
            ("desktop_pet_drag_track", "Drag-track head",
             self._input_engine.drag_enabled(), self.set_drag_track_enabled),
            ("desktop_pet_mouse_gaze", "Mouse gaze (eyes follow cursor)",
             gaze_running, self.set_mouse_gaze_enabled),
            ("desktop_pet_mic_lipsync", "Mic lip-sync",
             self._input_engine.lipsync_enabled(), self.set_mic_lipsync_enabled),
            ("desktop_pet_webcam", "Webcam tracking",
             webcam_running, self.set_webcam_tracking_enabled),
        ]

    def toggle_menu_entries(
        self,
    ) -> list[tuple[str, str, bool, Any]]:   # pragma: no cover - Qt UI
        """Rows for the five top-level checkable toggles: ``(label_key,
        default_label, current_state, setter)``."""
        return [
            ("desktop_pet_anchor", "Lock position",
             self._anchor_locked, self.set_anchor_locked),
            ("desktop_pet_click_through", "Click-through (let mouse pass)",
             self._click_through, self.set_click_through),
            ("desktop_pet_on_bottom", "Always on bottom (desktop widget)",
             self._always_on_bottom, self.set_always_on_bottom),
            ("desktop_pet_hide_fullscreen", "Hide when other app is fullscreen",
             self._hide_on_fullscreen, self.set_hide_on_fullscreen),
            ("desktop_pet_speech", "Speech bubble on click",
             self._speech_enabled, self.set_speech_enabled),
        ]

    def current_size_preset(self) -> str:   # pragma: no cover - Qt UI
        """Public alias of the active size-preset name for the menu."""
        return self._current_size_preset()

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
                self._idle_cycler.set_cycle_duration(PET_IDLE_CYCLE_DURATION_S)
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

    def set_hotkeys_enabled(self, enabled: bool, bindings: dict | None = None) -> bool:
        """Toggle the global-hotkey listener. Returns ``True`` when
        the requested state was reached; ``False`` means ``pynput``
        is missing or the OS refused the keyboard hook. ``bindings``
        overrides the persisted map; ``None`` reads from settings."""
        return self._features["hotkeys"].set_enabled(enabled, bindings)

    def hotkeys_enabled(self) -> bool:
        return self._features["hotkeys"].is_enabled()

    def _persisted_bindings(self) -> dict[str, str]:
        """Merge persisted overrides on top of the module defaults
        so a user who saved only one custom binding keeps the others."""
        return self._features["hotkeys"].persisted_bindings()

    def _on_hotkey_action(self, action: str) -> None:
        """Route a hotkey hit to the matching toggle. Lives in
        :class:`PetWindow` because every action needs window-state
        access (visibility, click-through, anchor)."""
        if action == ACTION_TOGGLE_VISIBLE:
            if self.isVisible():
                self.hide()
            else:
                self.show()
        elif action == ACTION_TOGGLE_LOCK:
            self.set_anchor_locked(not self._anchor_locked)
        elif action == ACTION_TOGGLE_CLICK_THROUGH:
            self.set_click_through(not self._click_through)
        elif action == ACTION_SPEAK_NOW:
            line = (
                self._script_engine.pick_time_of_day_greeting()
                or self._script_engine.pick_greeting()
            )
            if line and self._speech_enabled:
                self._show_speech(line)

    def set_obs_hook_enabled(self, enabled: bool) -> bool:
        """Connect or disconnect the OBS event listener. Returns
        ``True`` when the requested state was reached; ``False``
        means ``obs-websocket-py`` is missing or the connection
        failed (wrong port / password / OBS not running)."""
        return self._features["obs"].set_enabled(enabled)

    def obs_hook_enabled(self) -> bool:
        return self._features["obs"].is_enabled()

    def set_twitch_hook_enabled(self, enabled: bool) -> bool:
        """Connect or disconnect the Twitch chat listener. Returns
        ``True`` when the requested state was reached; ``False``
        when no channel / oauth is configured or the IRC handshake
        failed."""
        return self._features["twitch"].set_enabled(enabled)

    def twitch_hook_enabled(self) -> bool:
        return self._features["twitch"].is_enabled()

    def set_virtual_camera_enabled(self, enabled: bool) -> bool:
        """Toggle the system virtual camera output. Returns ``True``
        when the requested state was reached; ``False`` means
        ``pyvirtualcam`` is missing or no virtual camera driver is
        installed on the host (the macOS / Linux flows usually need
        a one-time driver setup)."""
        if enabled:
            if self._virtual_camera is None:
                self._virtual_camera = VirtualCameraOutput(self._canvas, parent=self)
            ok = self._virtual_camera.set_enabled(True)
            self._persist(virtual_camera_enabled=bool(ok))
            return ok
        if self._virtual_camera is not None:
            self._virtual_camera.set_enabled(False)
        self._persist(virtual_camera_enabled=False)
        return True

    def virtual_camera_enabled(self) -> bool:
        return (
            self._virtual_camera is not None and self._virtual_camera.is_enabled()
        )

    def set_llm_dialogue_enabled(self, enabled: bool) -> bool:
        """Toggle LLM-backed speech generation. Returns ``True`` on
        successful configuration; ``False`` when the saved base URL
        is invalid (HTTP non-loopback, unknown scheme). Connection
        failures only surface later, per request — we don't ping
        on enable since Ollama spin-up can lag."""
        return self._llm.set_enabled(enabled)

    def llm_dialogue_enabled(self) -> bool:
        return self._llm.is_enabled()

    def _on_llm_line(self, line: str) -> None:   # pragma: no cover - Qt UI
        """Async callback when the LLM returns a fresh line. We
        only surface it if the user still wants LLM speech and
        the speech bubble subsystem is enabled — a stale
        in-flight response after the user disables the feature
        gets discarded."""
        if not self._speech_enabled or not self.llm_dialogue_enabled():
            return
        if not line:
            return
        self._show_speech(line)

    def _on_llm_failed(self, reason: str) -> None:   # pragma: no cover - Qt UI
        """Log + fall through. The scripted line already showed
        synchronously when the user clicked, so there's nothing
        more to surface — the pet just stays with the scripted
        line."""
        logger.info("llm dialogue failed (%s); keeping scripted line", reason)

    def set_music_rhythm_enabled(self, enabled: bool) -> bool:
        """Toggle the system-audio rhythm driver. Returns ``True``
        when the requested state was reached; ``False`` when
        ``sounddevice`` is missing or WASAPI loopback isn't
        available (non-Windows OS, no output device)."""
        return self._music_rhythm.set_enabled(enabled)

    def music_rhythm_enabled(self) -> bool:
        return self._music_rhythm.is_enabled()

    def set_idle_minigame_enabled(self, enabled: bool) -> None:
        """Toggle the idle minigame (phantom curiosity + yawn /
        sleep escalation). Independent of other drivers."""
        self._idle_minigame.set_enabled(enabled)

    def idle_minigame_enabled(self) -> bool:
        return self._idle_minigame.is_enabled()

    def _notify_user_activity(self) -> None:   # pragma: no cover - Qt UI
        """Reset the idle clock — pet window mouse / drag handlers
        call this so the minigame knows the user is still there."""
        self._idle_minigame.notify_activity()

    def set_windows_notifications_enabled(self, enabled: bool) -> bool:
        """Toggle the Windows toast notification listener. Returns
        ``True`` only after the OS access prompt was granted and
        the handler is registered; ``False`` covers missing winrt,
        non-Windows, denied permission, or registration failure."""
        return self._features["windows_notifications"].set_enabled(enabled)

    def windows_notifications_enabled(self) -> bool:
        return self._features["windows_notifications"].is_enabled()

    def speak_notification(self, line: str) -> None:   # pragma: no cover - Qt UI
        """Route a notification's title through the speech bubble +
        SFX. Called by the notification controller; bypasses the
        script engine because the notification text already carries
        its own content (no generic-greeting fallback)."""
        if not self._speech_enabled or not line:
            return
        self._show_speech(line)
        self._play_sfx(SFX_NOTIFY)

    def set_webhook_enabled(self, enabled: bool) -> bool:
        """Toggle the localhost HTTP webhook receiver. Returns
        ``True`` when the requested state was reached; ``False``
        means the bind failed (port in use, OS refusal). The
        persisted flag is updated to match the actual state so a
        bind failure doesn't leave settings claiming it's on."""
        return self._features["webhook"].set_enabled(enabled)

    def webhook_enabled(self) -> bool:
        return self._features["webhook"].is_enabled()

    def set_pet_shadow_enabled(self, enabled: bool) -> None:
        """Toggle the drop shadow + persist. Live update — the next
        canvas paint reflects the new state."""
        self._persist(pet_shadow_enabled=bool(enabled))
        self._canvas.set_pet_shadow(
            enabled=bool(enabled),
            opacity=float(self._settings.get("pet_shadow_opacity", 0.7)),
            scale=float(self._settings.get("pet_shadow_scale", 1.0)),
        )

    def pet_shadow_enabled(self) -> bool:
        return self._canvas.pet_shadow_enabled()

    def set_pet_shadow_opacity(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))
        self._persist(pet_shadow_opacity=clamped)
        self._canvas.set_pet_shadow(
            enabled=self._canvas.pet_shadow_enabled(),
            opacity=clamped,
            scale=float(self._settings.get("pet_shadow_scale", 1.0)),
        )

    def set_pet_shadow_scale(self, value: float) -> None:
        clamped = max(0.0, min(2.0, float(value)))
        self._persist(pet_shadow_scale=clamped)
        self._canvas.set_pet_shadow(
            enabled=self._canvas.pet_shadow_enabled(),
            opacity=float(self._settings.get("pet_shadow_opacity", 0.7)),
            scale=clamped,
        )

    def set_click_sfx_enabled(self, enabled: bool) -> None:
        """Toggle the click SFX subsystem. Paths and volume are
        read from settings each time the player is configured —
        the workspace edit roundtrips through here."""
        self._click_sfx_ctl.set_enabled(enabled)

    def click_sfx_enabled(self) -> bool:
        return self._click_sfx_ctl.is_enabled()

    def _play_sfx(self, event: str) -> None:
        """Best-effort SFX play. No-op when the subsystem is off
        or the event has no configured path."""
        self._click_sfx_ctl.play(event)

    def set_mouse_gaze_enabled(self, enabled: bool) -> None:
        if enabled:
            if self._mouse_gaze is None:
                self._mouse_gaze = MouseGazeDriver(
                    self._canvas, self, parent=self,
                )
            self._mouse_gaze.set_enabled(True)
        elif self._mouse_gaze is not None:
            self._mouse_gaze.set_enabled(False)
        self._persist_driver("mouse_gaze", bool(enabled))

    def _persist_driver(self, key: str, value: bool) -> None:
        drivers = dict(self._settings.get("drivers", {}))
        drivers[key] = bool(value)
        self._settings["drivers"] = drivers
        self._persist(drivers=drivers)

    def _persist(self, **fields: Any) -> None:
        """Thread the pet's own id through :func:`pet_settings.update`
        so each instance writes to its own slot. Single seam for the
        whole window — every persist call goes through here, which
        keeps the multi-pet refactor from sprawling across 20+ call
        sites."""
        pet_settings.update(self._pet_id, **fields)

    # ---- FeatureHost adapter ------------------------------------
    # The thin surface the integration controllers depend on (see
    # pet_feature_base.FeatureHost). Each call forwards to the
    # window's existing machinery so controller behaviour stays
    # identical to the old inline implementations.

    def persist(self, **fields: Any) -> None:
        """FeatureHost hook — forward to the window's persist seam."""
        self._persist(**fields)

    def setting(self, key: str, default: Any) -> Any:
        """FeatureHost hook — read a persisted setting with a default."""
        return self._settings.get(key, default)

    def persist_driver(self, key: str, value: bool) -> None:
        """FeatureHost hook — persist a slot in the ``drivers`` dict."""
        self._persist_driver(key, value)

    def play_group(self, group: str) -> bool:
        """FeatureHost hook — play a random motion from ``group``."""
        return self.play_random_motion_in_group(group)

    def speak(self, line: str) -> None:
        """FeatureHost hook — surface ``line`` in the speech bubble."""
        self._show_speech(line)

    def on_hotkey_action(self, action: str) -> None:
        """FeatureHost hook — route a hotkey hit to its window action."""
        self._on_hotkey_action(action)

    @property
    def speech_on(self) -> bool:
        """FeatureHost hook — whether the speech bubble is enabled."""
        return self._speech_enabled

    def pet_id(self) -> str:
        """The id this pet persists under — useful for the registry
        and tests that need to verify isolation."""
        return self._pet_id

    # =====================================================================
    # Motion / expression playback (context menu + hit-area)
    # =====================================================================

    def _play_motion(self, motion) -> None:
        """Bind ``motion`` on the player and start playback. Used
        from the context-menu motions submenu."""
        self._motion_player.set_motion(motion)
        self._motion_player.play()

    def play_motion(self, motion) -> None:
        """Public alias used by the context-menu motions submenu."""
        self._play_motion(motion)

    def apply_expression(self, name: str) -> None:
        """Public alias used by the context-menu expressions submenu."""
        self._apply_expression(name)

    # ---- file drag-drop -------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:   # noqa: N802 - Qt override
        """Accept drops that carry file URLs. Anything else (text,
        in-app drags) is ignored so we don't intercept random
        events from elsewhere in the app."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:   # noqa: N802 - Qt override
        """Thin glue over :meth:`handle_dropped_paths` — Qt's drop
        event class is awkward to construct in tests, so all the
        real dispatch logic sits in the path-based helper that
        tests can drive directly."""
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile() and url.toLocalFile()
        ]
        self.handle_dropped_paths(paths)
        event.acceptProposedAction()

    def handle_dropped_paths(self, paths: list[Path]) -> str:
        """Dispatch a list of dropped paths. Returns the same kind
        string :func:`classify_drop_paths` produces so callers (and
        tests) can verify which branch ran. Side effects:

        * ``"puppet"`` → loads the rig and emits ``hit_triggered("")``.
        * ``"other"``  → plays the Drop motion group + a greeting.
        * ``"none"``   → no-op.
        """
        kind, target = classify_drop_paths(paths)
        if kind == "puppet" and target is not None:
            self.load_puppet_file(target)
            self.hit_triggered.emit("")
        elif kind == "other":
            self.play_random_motion_in_group(DROP_MOTION_GROUP)
            if self._speech_enabled:
                line = (
                    self._script_engine.pick_time_of_day_greeting()
                    or self._script_engine.pick_greeting()
                )
                if line:
                    self._show_speech(line)
        return kind

    def play_random_motion_in_group(self, group: str) -> bool:
        """Pick + play a random motion from ``group``. Returns ``True``
        when the rig had at least one motion in the group and playback
        was started; ``False`` is a silent no-op (rigs without authored
        Drag / Land groups still work)."""
        last_name = (
            self._motion_player.motion().name
            if self._motion_player.motion() is not None
            else None
        )
        motion = pick_random_motion_in_group(
            self.document(), group, exclude_name=last_name,
        )
        if motion is None:
            return False
        self._play_motion(motion)
        return True

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
        self._persist(speech_enabled=self._speech_enabled)
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

    # =====================================================================
    # Pet script (user-customisable voice)
    # =====================================================================

    def load_script_file(self, path: str | Path) -> bool:
        """Load a ``.petscript.json`` and bind it to the engine.
        Returns ``True`` on success; failure writes the path to
        the settings so the workspace can show a useful message
        but doesn't crash the pet."""
        try:
            script = load_script(path)
        except PetScriptError as exc:
            logger.warning("pet script %s failed: %s", path, exc)
            return False
        self._script_engine.set_script(script)
        self._persist(script_path=str(path))
        return True

    def reset_script_to_default(self) -> None:
        """Drop the user script and revert to the built-in
        greeting set. Clears the persisted path so the next
        launch doesn't reload the now-rejected script."""
        self._script_engine.set_script(PetScript.default())
        self._persist(script_path="")

    def script_engine(self) -> PetScriptEngine:
        """Test / advanced caller hook — exposes the engine so
        external code can read the active script without poking
        the private attribute."""
        return self._script_engine

    def _restore_persisted_script(self) -> None:
        """Apply the script the previous session ended with. A
        missing / unreadable file falls back silently to the
        default voice — the workspace's status label is the
        user-facing reporting channel."""
        path = str(self._settings.get("script_path", "") or "")
        if not path:
            return
        try:
            self._script_engine.set_script(load_script(path))
        except PetScriptError as exc:
            logger.info("ignoring stale pet script %s: %s", path, exc)

    def _restore_drivers(self) -> None:
        """Wake every persisted driver the user had running last
        session. Without this, drivers only started when the user
        opened the workspace tab (its ``_reapply_persisted_toggles``
        re-ticks the checkboxes, which fires the signal chain).
        Pets launched directly from the tray / hotkey / autorun
        went static."""
        drivers = self._settings.get("drivers", {}) or {}
        if not isinstance(drivers, dict):
            return
        # Zero-dep drivers we can flip on confidently. The rest
        # (mic_lipsync, webcam_tracking) need optional packages and
        # might fail loudly; let the user re-enable them via the
        # workspace, which has the status-label surface for the
        # "missing dep" message.
        if drivers.get("auto_idle"):
            self.set_auto_idle_enabled(True)
        if drivers.get("idle_motion"):
            self.set_idle_motion_enabled(True)
        if drivers.get("auto_blink"):
            self.set_auto_blink_enabled(True)
        if drivers.get("drag_track"):
            self.set_drag_track_enabled(True)
        if drivers.get("mouse_gaze"):
            self.set_mouse_gaze_enabled(True)
        if drivers.get("music_rhythm"):
            self.set_music_rhythm_enabled(True)
        if drivers.get("idle_minigame"):
            self.set_idle_minigame_enabled(True)

    def _on_script_tick(self) -> None:   # pragma: no cover - Qt timer
        """1 Hz heartbeat that fires any due
        :class:`ScheduledEvent` from the active script."""
        if not self._speech_enabled:
            return
        line = self._script_engine.due_scheduled_message()
        if line:
            self._show_speech(line)

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
        self._persist(size_preset=preset)

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
        pet_placement.restore_position(self)

    def _current_screen_name(self) -> str:   # pragma: no cover - Qt geometry
        return pet_placement.current_screen_name(self)
