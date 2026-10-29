"""Desktop-pet overlay window — full edition.

A top-level frameless / transparent-background window that hosts a
:class:`PuppetCanvas` in pet mode. The pet inherits the entire Puppet
runtime (parameters, motions, expressions, physics, live-input drivers)
and adds desktop-widget polish: drag-to-move with edge-snap, click-
through, a right-click context menu, left-click hit detection, anchor
lock, window opacity, always-on-bottom, hide-on-fullscreen, a speech
bubble, and pause-when-hidden.

:class:`PetWindow` is a thin coordinator — the heavy subsystems live in
sibling controllers: pointer interaction (:mod:`pet_interaction`),
canvas-input drivers (:mod:`pet_canvas_drivers`), drop shadow
(:mod:`pet_shadow_controller`), integration hooks (:mod:`pet_features`),
and the lazy LLM / SFX / rhythm / minigame controllers
(:mod:`pet_drivers`). Its own surface is split across mixins: window
flags (:mod:`pet_window_flags`), feature toggles
(:mod:`pet_feature_toggles`), speech and script (:mod:`pet_window_voice`),
motion playback and file drops (:mod:`pet_window_playback`), and
persistence / integrations / menu rows / sizing (:mod:`pet_window_host`).
Every user-tweakable knob round-trips through
:mod:`Imervue.desktop_pet.settings` so the pet restores on next launch.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from Imervue.system.qt_timers import call_later
from Imervue.system.best_effort import best_effort
from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.fullscreen_detector import FullscreenDetector
from Imervue.desktop_pet.pet_drivers import (
    ClickSfxController,
    IdleMinigameController,
    LlmDialogueController,
    MusicRhythmController,
)
from Imervue.desktop_pet.pet_canvas_drivers import PetCanvasDrivers
from Imervue.desktop_pet.pet_interaction import PetInteraction
from Imervue.desktop_pet.pet_shadow_controller import PetShadowController
from Imervue.desktop_pet.pet_features import build_integration_controllers
from Imervue.desktop_pet.pet_feature_toggles import PetFeatureTogglesMixin
from Imervue.desktop_pet.pet_window_flags import PetWindowFlagsMixin
from Imervue.desktop_pet.pet_window_host import (
    PET_IDLE_CYCLE_DURATION_S,
    SIZE_PRESETS,
    PetHostMixin,
)
from Imervue.desktop_pet.pet_window_playback import (
    DROP_MOTION_GROUP,
    PUPPET_FILE_SUFFIX,
    PetPlaybackMixin,
    classify_drop_paths,
)
from Imervue.desktop_pet.pet_window_voice import PetVoiceMixin
from Imervue.desktop_pet.pet_script import PetScriptEngine
from Imervue.desktop_pet.speech_bubble import SpeechBubble
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document_io import load_puppet

if TYPE_CHECKING:
    from Imervue.puppet.document import PuppetDocument
    from Imervue.puppet.idle_driver import IdleDriver
    from Imervue.puppet.idle_motion_cycler import IdleMotionCycler
    from Imervue.puppet.input_engine import InputEngine
    from Imervue.puppet.motion_player import MotionPlayer
    from Imervue.puppet.mouse_gaze_driver import MouseGazeDriver
    from Imervue.puppet.virtual_camera import VirtualCameraOutput
    from Imervue.puppet.webcam_tracker import WebcamTracker

logger = logging.getLogger("Imervue.desktop_pet.pet_window")

__all__ = [
    "DEFAULT_GREETINGS",
    "DEFAULT_PET_SIZE",
    "DRAG_MOTION_GROUP",
    "DROP_MOTION_GROUP",
    "LAND_MOTION_GROUP",
    "PAINT_TICK_INTERVAL_MS",
    "PET_IDLE_CYCLE_DURATION_S",
    "PUPPET_FILE_SUFFIX",
    "SCRIPT_TICK_INTERVAL_MS",
    "SIZE_PRESETS",
    "PetWindow",
    "classify_drop_paths",
]

DEFAULT_PET_SIZE: tuple[int, int] = (320, 480)
"""Initial overlay size, in screen pixels. Vertical 3:4 slot
matches the typical aspect of a rigged character; resize presets
swap into other slots without losing this proportion."""

PAINT_TICK_INTERVAL_MS: int = 33
"""≈ 30 FPS canvas repaint cadence while the overlay is visible."""

SCRIPT_TICK_INTERVAL_MS: int = 1000
"""1 Hz heartbeat that fires the script engine's scheduled chimes."""

DRAG_MOTION_GROUP: str = "Drag"
"""Cubism-convention group name played the moment the user starts
dragging the pet. Rigs without a Drag-group motion silently no-op
so the feature is opt-in via authoring, not via a toggle."""

LAND_MOTION_GROUP: str = "Land"
"""Played when the user drops the pet. Pairs with ``DRAG_MOTION_GROUP``
to bracket a drag interaction; either or both can be absent without
breaking the drag flow."""

from Imervue.desktop_pet.pet_script import DEFAULT_GREETINGS  # noqa: F401, E402
"""Re-export so callers / tests that imported the old constant
keep working. The authoritative copy lives in
:mod:`Imervue.desktop_pet.pet_script` alongside the engine."""


class PetWindow(
    PetWindowFlagsMixin, PetFeatureTogglesMixin, PetVoiceMixin,
    PetPlaybackMixin, PetHostMixin, QWidget,
):
    """The on-desktop puppet overlay.

    Long-lived: constructed once per Imervue session, the pet
    shows / hides via :meth:`show` / :meth:`hide` rather than
    being recreated. That keeps the GL context and every
    uploaded texture / VBO alive across visibility toggles, so
    "hide then show" doesn't incur a re-upload.
    """

    visibility_changed = Signal(bool)
    """``True`` after show / ``False`` after hide."""

    setting_changed = Signal(str, object)
    """``(key, value)`` for every setting the pet saves, wherever the
    change came from (context menu, tray, hotkey, tab). Workspace
    mirrors it into its checkboxes."""

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
        # ``"default"`` (preserves the single-pet schema); any other
        # id gets its own slot.
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
        self._shadow = PetShadowController(
            self._canvas, self.setting, self._persist,
        )
        self._shadow.apply_initial()

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
        self._snap_threshold: int = int(self._settings["snap_threshold"])
        # Drag / click / hit-detection lives in its own controller; the
        # window re-exposes its drag-state flags via properties below.
        self._interaction = PetInteraction(self)
        self._canvas.installEventFilter(self)

    def _init_drivers_and_voice(self) -> None:
        """Construct the always-present canvas-input drivers, the
        speech / script engine, and the paint + script tick timers."""
        # Canvas-input drivers (auto-blink / idle / gaze / webcam /
        # virtual-camera / motion player) live in one controller; the
        # window re-exposes them via @property accessors below so the
        # construction + enable logic stays out of this class.
        self._canvas_drivers = PetCanvasDrivers(self, self._canvas)

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

        # Hotkeys and the integrations plugins add (add_integration) share
        # one lazy-worker lifecycle; the registry holds them so shutdown()
        # stops every one.
        self._features = build_integration_controllers(self)

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
    # Canvas-driver accessors
    # =====================================================================
    # The input drivers live in ``self._canvas_drivers`` (see
    # pet_canvas_drivers). These read-only properties preserve the
    # historical attribute names so the menu builder and the pet-window
    # tests can reach each driver without knowing about the controller.

    @property
    def _input_engine(self) -> InputEngine:
        return self._canvas_drivers.input_engine

    @property
    def _motion_player(self) -> MotionPlayer:
        return self._canvas_drivers.motion_player

    @property
    def _idle_driver(self) -> IdleDriver | None:
        return self._canvas_drivers.idle_driver

    @property
    def _idle_cycler(self) -> IdleMotionCycler | None:
        return self._canvas_drivers.idle_cycler

    @property
    def _mouse_gaze(self) -> MouseGazeDriver | None:
        return self._canvas_drivers.mouse_gaze

    @property
    def _webcam_tracker(self) -> WebcamTracker | None:
        return self._canvas_drivers.webcam_tracker

    @property
    def _virtual_camera(self) -> VirtualCameraOutput | None:
        return self._canvas_drivers.virtual_camera

    # ---- visibility hooks --------------------------------------

    def showEvent(self, event) -> None:   # pragma: no cover - Qt UI
        super().showEvent(event)
        # Resume ticking — paintGL needs the timer ticks to
        # advance physics / motions while no input event is firing.
        # The 1 Hz script tick wakes up for scheduled chimes.
        self._tick.start()
        self._script_tick.start()
        self._watch_fullscreen_on_show()
        # Force a fresh canvas repaint on show. Qt does call paintGL
        # automatically after showEvent, but a delayed singleShot
        # update covers the case where textures finish uploading
        # mid-show — without it, the first visible frame can flash
        # white silhouettes on a black backdrop while the GL thread
        # is still wiring up the texture cache.
        call_later(50, self._canvas, self._canvas.update)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:   # pragma: no cover - Qt UI
        super().hideEvent(event)
        # Stop the tick timer so the dormant pet doesn't repaint.
        self._tick.stop()
        self._script_tick.stop()
        self._watch_fullscreen_on_hide()
        if self._speech is not None:
            self._speech.close_bubble()
        self.visibility_changed.emit(False)

    def shutdown(self) -> None:
        """Stop every background worker / OS hook this pet owns.

        ``hideEvent`` only stops the repaint timers; despawn must ALSO release
        the webcam (camera LED off), unbind the webhook port, remove the global
        hotkey OS hook, close the twitch / OBS sockets and stop the audio
        loopback — none of which ``deleteLater`` does, because the spawned Python
        threads / OS hooks outlive the destroyed C++ QObject. Nothing is
        persisted, so re-spawning restores whatever the user had enabled.
        """
        for controller in self._features.values():
            with best_effort("shut down a feature controller"):
                controller.shutdown()
        with best_effort("shut down music rhythm"):
            self._music_rhythm.shutdown()
        with best_effort("shut down the canvas drivers"):
            self._canvas_drivers.shutdown()
        with best_effort("shut down the LLM client"):
            # An in-flight LLM request can still be blocked in urlopen; mark it
            # dead so its late reply doesn't emit on this soon-deleted window.
            self._llm.shutdown()

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
        call_later(50, self._canvas, self._canvas.update)

    def document(self) -> PuppetDocument | None:
        return self._canvas.document()

    def canvas(self) -> PuppetCanvas:
        return self._canvas

    # =====================================================================
    # Drag-to-move + hit detection
    # =====================================================================
    # The pointer-interaction behaviour lives in ``self._interaction``
    # (see pet_interaction). The drag-state flags are re-exposed as
    # read-only properties so the existing tests can poke them.

    @property
    def _dragging(self) -> bool:
        return self._interaction.dragging

    @property
    def _drag_offset(self) -> QPoint:
        return self._interaction.drag_offset

    @property
    def _press_pos(self) -> QPoint | None:
        return self._interaction.press_pos

    def eventFilter(self, obj, event):   # pragma: no cover - Qt UI
        if obj is self._canvas and self._interaction.handle_canvas_event(event):
            return True
        return super().eventFilter(obj, event)
