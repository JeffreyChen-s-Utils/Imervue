"""Idle minigame — pet gets curious / yawns when the user is away.

After a configurable idle period, the pet enters "curious" mode:
it picks random gaze targets and drifts its head + eyes toward
them, as if watching things move on the desktop. After a longer
idle, it plays a Yawn motion group; longer still, a Sleep group.
Mouse activity resets the timeline back to ACTIVE.

This complements (rather than competes with) :class:`MouseGazeDriver`:
the minigame only writes look-at parameters when the user is idle
*and* MouseGazeDriver isn't currently enabled. So users who like
"eyes always follow cursor" don't see the phantom targets fight
the cursor; users who don't enable MouseGazeDriver still get
something interesting during long idle periods.

Pure helpers (:func:`pick_phantom_offset`, :func:`stage_for_idle`)
have no Qt and no global state so the policy + RNG-shaped logic
is unit-testable without a QApplication.
"""
from __future__ import annotations

import logging
import secrets
import time
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.standard_params import (
    PARAM_ANGLE_X,
    PARAM_ANGLE_Y,
    PARAM_EYE_BALL_X,
    PARAM_EYE_BALL_Y,
)

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.desktop_pet.idle_minigame")

DEFAULT_CURIOUS_THRESHOLD_S: float = 15.0
"""Idle seconds before phantom-target gazing starts. Short enough
to kick in within a typical "stepped away from the keyboard"
moment; long enough that brief pauses don't cause the rig to
visibly drift."""

DEFAULT_YAWN_THRESHOLD_S: float = 60.0
"""Idle seconds before the Yawn motion plays."""

DEFAULT_SLEEP_THRESHOLD_S: float = 300.0
"""Idle seconds before the Sleep motion plays. Past 5 min the
user is presumably away from the desk — sleep posture reads as
"pet is also resting" rather than "pet is broken"."""

DEFAULT_TARGET_DWELL_S: float = 5.0
"""Seconds the pet looks at one phantom target before picking
another. Short dwell looks restless; long dwell looks zoned out.
5 s reads as "watching something move"."""

DEFAULT_GAZE_RANGE: float = 0.55
"""Max gaze magnitude when wandering. Stays under 1.0 so the rig
has range left over for the small drift IdleDriver also writes
into ParamAngleX/Y when active."""

_TICK_HZ: int = 4
"""Watchdog tick rate. Low — the only thing changing on a tick is
the gaze target and the stage threshold check; 4 Hz feels live
enough without burning CPU during long idle stretches."""

YAWN_MOTION_GROUP: str = "Yawn"
SLEEP_MOTION_GROUP: str = "Sleep"


class IdleStage(Enum):
    """Phases of idleness, ordered by escalation."""

    ACTIVE = "active"           # user is here — minigame writes nothing
    CURIOUS = "curious"         # phantom-target gaze drift
    YAWN = "yawn"               # play Yawn motion (one-shot per visit)
    SLEEP = "sleep"             # play Sleep motion (one-shot per visit)


def stage_for_idle(
    idle_seconds: float,
    *,
    curious_threshold: float = DEFAULT_CURIOUS_THRESHOLD_S,
    yawn_threshold: float = DEFAULT_YAWN_THRESHOLD_S,
    sleep_threshold: float = DEFAULT_SLEEP_THRESHOLD_S,
) -> IdleStage:
    """Pure mapping from elapsed idle seconds to the current
    :class:`IdleStage`. Tests sample this directly; the Qt
    wrapper uses it on each tick.

    Thresholds escalate; passing them in deliberately so future
    tuning UIs (per-pet patience) can plug straight in."""
    if idle_seconds >= sleep_threshold:
        return IdleStage.SLEEP
    if idle_seconds >= yawn_threshold:
        return IdleStage.YAWN
    if idle_seconds >= curious_threshold:
        return IdleStage.CURIOUS
    return IdleStage.ACTIVE


def pick_phantom_offset(
    *,
    gaze_range: float = DEFAULT_GAZE_RANGE,
    random_unit: tuple[float, float] | None = None,
) -> dict[str, float]:
    """Pick a random gaze target and return the parameter map.

    Returns ``{PARAM_ANGLE_X, PARAM_ANGLE_Y, PARAM_EYE_BALL_X,
    PARAM_EYE_BALL_Y}`` values in ``[-gaze_range, gaze_range]``.
    Eyes saturate further than the head (same lead-and-follow
    relationship :class:`MouseGazeDriver` uses) so the pet's eyes
    catch the target first.

    ``random_unit`` lets tests inject deterministic targets; in
    production it's drawn from :mod:`secrets` so a long-running pet
    doesn't fall into a predictable loop.
    """
    if random_unit is None:
        ux = (secrets.randbits(16) / 65535.0) * 2.0 - 1.0
        uy = (secrets.randbits(16) / 65535.0) * 2.0 - 1.0
    else:
        ux, uy = random_unit
    ux = max(-1.0, min(1.0, float(ux)))
    uy = max(-1.0, min(1.0, float(uy)))
    head_x = ux * float(gaze_range)
    head_y = uy * float(gaze_range)
    return {
        PARAM_ANGLE_X: head_x,
        PARAM_ANGLE_Y: head_y,
        PARAM_EYE_BALL_X: max(-1.0, min(1.0, ux * 1.5)),
        PARAM_EYE_BALL_Y: max(-1.0, min(1.0, uy * 1.5)),
    }


class IdleMinigameDriver(QObject):
    """Plays the phantom-curiosity / yawn / sleep escalation when
    the user is idle.

    Activity tracking is push-based: the pet window calls
    :meth:`notify_activity` from its mouse + key event filters.
    The driver then knows the last activity timestamp and
    computes the stage on each tick.
    """

    stage_changed = Signal(str)
    """Emitted when the stage transitions. Value is the
    :class:`IdleStage` ``value`` (``"active"`` / ``"curious"`` /
    ``"yawn"`` / ``"sleep"``)."""

    def __init__(self, canvas: PuppetCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self._enabled = False
        self._last_activity: float = time.monotonic()
        self._last_target_t: float = 0.0
        self._stage: IdleStage = IdleStage.ACTIVE
        self._stages_fired: set[IdleStage] = set()
        self._motion_callback = None
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / _TICK_HZ))
        self._timer.timeout.connect(self._on_tick)

    # ---- public API -----------------------------------------------

    def is_enabled(self) -> bool:
        return self._enabled

    def stage(self) -> IdleStage:
        return self._stage

    def set_motion_callback(self, callback) -> None:
        """Bind the "play a motion group" function. The pet window
        passes its :meth:`play_random_motion_in_group` here so
        Yawn / Sleep fire on the right rig."""
        self._motion_callback = callback

    def set_enabled(self, enabled: bool) -> None:
        if enabled == self._enabled:
            return
        self._enabled = bool(enabled)
        if enabled:
            self.notify_activity()
            self._stages_fired.clear()
            self._timer.start()
        else:
            self._timer.stop()
            self._reset_gaze_to_neutral()
        if self._stage != IdleStage.ACTIVE:
            self._stage = IdleStage.ACTIVE
            self.stage_changed.emit(self._stage.value)

    def notify_activity(self) -> None:
        """Reset the idle clock. Called from the pet window's
        mouse / drag handlers; can also be called from external
        hooks (e.g. webhook trigger should reset idleness)."""
        self._last_activity = time.monotonic()
        if self._stage != IdleStage.ACTIVE:
            self._stage = IdleStage.ACTIVE
            self._stages_fired.clear()
            self.stage_changed.emit(self._stage.value)

    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_activity

    def tick_once(self) -> None:
        """Test hook — drive a single tick without the QTimer."""
        self._on_tick()

    def shutdown(self) -> None:
        self._timer.stop()

    # ---- internal -------------------------------------------------

    def _on_tick(self) -> None:
        if not self._enabled or self._canvas.document() is None:
            return
        idle = self.idle_seconds()
        new_stage = stage_for_idle(idle)
        if new_stage != self._stage:
            self._stage = new_stage
            self.stage_changed.emit(new_stage.value)
            if new_stage in (IdleStage.YAWN, IdleStage.SLEEP):
                self._fire_stage_motion(new_stage)
        if new_stage == IdleStage.CURIOUS:
            self._maybe_pick_new_target()

    def _maybe_pick_new_target(self) -> None:
        """Pick a fresh phantom target every
        :data:`DEFAULT_TARGET_DWELL_S` seconds while in CURIOUS
        stage. Writes the four standard look-at params; missing
        params on the rig are skipped silently."""
        now = time.monotonic()
        if now - self._last_target_t < DEFAULT_TARGET_DWELL_S:
            return
        self._last_target_t = now
        targets = pick_phantom_offset()
        canvas_values = self._canvas.parameter_values()
        batch = {pid: v for pid, v in targets.items() if pid in canvas_values}
        if batch:
            self._canvas.set_parameter_values(batch)

    def _fire_stage_motion(self, stage: IdleStage) -> None:
        """Play the Yawn / Sleep group once per stage entry. The
        ``_stages_fired`` set debounces — re-entering YAWN from
        SLEEP doesn't re-trigger Yawn until the user activates +
        the timeline rewinds."""
        if stage in self._stages_fired:
            return
        self._stages_fired.add(stage)
        callback = self._motion_callback
        if callback is None:
            return
        group = YAWN_MOTION_GROUP if stage == IdleStage.YAWN else SLEEP_MOTION_GROUP
        try:
            callback(group)
        except Exception as exc:   # noqa: BLE001 - callback owner's exceptions shouldn't kill the driver
            logger.warning("idle minigame motion callback failed: %s", exc)

    def _reset_gaze_to_neutral(self) -> None:
        """Settle the look-at params to neutral when the minigame
        is turned off — otherwise the rig stays mid-glance."""
        if self._canvas.document() is None:
            return
        canvas_values = self._canvas.parameter_values()
        batch = {
            pid: 0.0 for pid in (
                PARAM_ANGLE_X, PARAM_ANGLE_Y,
                PARAM_EYE_BALL_X, PARAM_EYE_BALL_Y,
            )
            if pid in canvas_values
        }
        if batch:
            self._canvas.set_parameter_values(batch)
