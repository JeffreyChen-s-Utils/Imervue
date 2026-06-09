"""Canvas-input driver subsystem for the desktop-pet overlay.

Groups the always-present and lazily-constructed canvas-bound input
drivers that :class:`~Imervue.desktop_pet.pet_window.PetWindow` used to
build and toggle inline:

* ``input_engine`` — auto-blink / drag-track-head / mic-lipsync (always
  present; sub-features toggle on the one engine).
* ``motion_player`` — the shared player every motion-playing path binds.
* ``idle_driver`` — breath + drift idle animation (lazy).
* ``idle_cycler`` — periodic idle-motion turnover (lazy).
* ``mouse_gaze`` — eyes / head follow the cursor (lazy).
* ``webcam_tracker`` — face-tracking driver (lazy, optional dep).
* ``virtual_camera`` — system virtual-camera output of the canvas (lazy,
  optional dep).

Extracting this keeps the window a thin coordinator: it owns one
:class:`PetCanvasDrivers` and delegates its ``set_*_enabled`` toggles to
it. The lazy-construction, enable / disable, and persistence behaviour
is preserved byte-for-byte from the original inline methods. The window
re-exposes ``input_engine`` / ``motion_player`` / ``idle_driver`` / … as
``@property`` accessors so the existing test contract (which pokes those
private attributes directly) keeps working.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.puppet.idle_driver import IdleDriver
from Imervue.puppet.idle_motion_cycler import IdleMotionCycler
from Imervue.puppet.input_engine import InputEngine
from Imervue.puppet.motion_player import MotionPlayer
from Imervue.puppet.mouse_gaze_driver import MouseGazeDriver
from Imervue.puppet.virtual_camera import VirtualCameraOutput

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.webcam_tracker import WebcamTracker


class PetCanvasDrivers:
    """Owns the canvas-bound input drivers for one pet overlay.

    Constructed once per :class:`PetWindow`. ``window`` is both the Qt
    parent for every driver (so they're torn down with the overlay) and
    the widget the gaze driver maps the cursor against. ``persist_driver``
    writes a slot in the persisted ``drivers`` dict; ``persist`` writes a
    top-level settings field (used for the virtual-camera flag).
    """

    def __init__(self, window: QWidget, canvas: PuppetCanvas) -> None:
        self._window = window
        self._canvas = canvas
        # Always-present drivers.
        self.input_engine = InputEngine(canvas, parent=window)
        self.motion_player = MotionPlayer(canvas)
        # Lazily-constructed drivers (None until first enable).
        self.idle_driver: IdleDriver | None = None
        self.idle_cycler: IdleMotionCycler | None = None
        self.mouse_gaze: MouseGazeDriver | None = None
        self.webcam_tracker: WebcamTracker | None = None
        self.virtual_camera: VirtualCameraOutput | None = None

    # ---- auto idle (breath + drift) ----------------------------

    def set_auto_idle_enabled(self, enabled: bool) -> None:
        if enabled:
            if self.idle_driver is None:
                self.idle_driver = IdleDriver(self._canvas, parent=self._window)
            self.idle_driver.set_enabled(True)
        elif self.idle_driver is not None:
            self.idle_driver.set_enabled(False)

    # ---- idle motions ------------------------------------------

    def set_idle_motion_enabled(self, enabled: bool, cycle_duration_s: float) -> None:
        if enabled:
            if self.idle_cycler is None:
                self.idle_cycler = IdleMotionCycler(
                    self.motion_player, self._canvas, parent=self._window,
                )
                self.idle_cycler.set_cycle_duration(cycle_duration_s)
            self.idle_cycler.set_enabled(True)
        elif self.idle_cycler is not None:
            self.idle_cycler.set_enabled(False)

    # ---- mouse gaze --------------------------------------------

    def set_mouse_gaze_enabled(self, enabled: bool) -> None:
        if enabled:
            if self.mouse_gaze is None:
                self.mouse_gaze = MouseGazeDriver(
                    self._canvas, self._window, parent=self._window,
                )
            self.mouse_gaze.set_enabled(True)
        elif self.mouse_gaze is not None:
            self.mouse_gaze.set_enabled(False)

    # ---- webcam tracking (optional dep) ------------------------

    def set_webcam_tracking_enabled(self, enabled: bool) -> bool:
        """Returns the driver's own ``set_enabled`` result on enable
        (``False`` when ``opencv`` / the camera is unavailable), ``True``
        on disable."""
        if enabled:
            if self.webcam_tracker is None:
                from Imervue.puppet.webcam_tracker import WebcamTracker
                self.webcam_tracker = WebcamTracker(self._canvas, parent=self._window)
            return bool(self.webcam_tracker.set_enabled(True))
        if self.webcam_tracker is not None:
            self.webcam_tracker.set_enabled(False)
        return True

    # ---- virtual camera (optional dep) -------------------------

    def set_virtual_camera_enabled(self, enabled: bool) -> bool:
        """Returns the output's own ``set_enabled`` result on enable
        (``False`` when ``pyvirtualcam`` / a driver is missing), ``True``
        on disable."""
        if enabled:
            if self.virtual_camera is None:
                self.virtual_camera = VirtualCameraOutput(
                    self._canvas, parent=self._window,
                )
            return bool(self.virtual_camera.set_enabled(True))
        if self.virtual_camera is not None:
            self.virtual_camera.set_enabled(False)
        return True

    def virtual_camera_enabled(self) -> bool:
        return (
            self.virtual_camera is not None and self.virtual_camera.is_enabled()
        )

    # ---- menu state helpers ------------------------------------

    def idle_running(self) -> bool:
        return self.idle_driver is not None and self.idle_driver.is_enabled()

    def idle_motion_running(self) -> bool:
        return self.idle_cycler is not None and self.idle_cycler.is_enabled()

    def gaze_running(self) -> bool:
        return self.mouse_gaze is not None and self.mouse_gaze.is_enabled()

    def webcam_running(self) -> bool:
        return (
            self.webcam_tracker is not None and self.webcam_tracker.is_enabled()
        )
