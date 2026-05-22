"""Music-rhythm driver — pet sways to system audio.

When enabled, the driver opens a WASAPI loopback stream on the
default output device (Windows-only, via ``sounddevice``), reads
the playback envelope, and modulates the pet's head + body Z-axis
sway so the rig physically bobs to whatever's playing. Calm tracks
produce subtle sway; loud / percussive material drives bigger
swings.

WASAPI loopback is Windows-specific. macOS / Linux fall back to
"return False on enable" so the workspace can surface the
"system audio loopback isn't supported on this OS" message. Users
on those platforms can still get rhythm sync by routing system
audio through BlackHole / PulseAudio monitor sources into a real
input device, but that's manual setup we don't try to automate.

Pure helpers (:func:`compute_envelope`, :func:`smooth_envelope`,
:func:`envelope_to_sway`) work on numpy arrays / floats with no
audio dependency so the tuning logic is unit-testable without
opening a real stream.
"""
from __future__ import annotations

import logging
import math
import platform
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.standard_params import (
    PARAM_ANGLE_Z,
    PARAM_BODY_ANGLE_Z,
)

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.desktop_pet.music_rhythm")

DEFAULT_SAMPLE_RATE: int = 44100
DEFAULT_BLOCK_SIZE: int = 1024
"""~23 ms at 44.1 kHz. Short enough to track transients
(percussive hits) without massive CPU overhead."""

DEFAULT_SWAY_PERIOD_S: float = 0.5
"""Half-period sway — head rocks left-right roughly every half
second at full envelope. Slow enough to read as "dancing" rather
than "shaking"."""

DEFAULT_SWAY_AMPLITUDE: float = 0.55
"""Max ``ParamAngleZ`` amplitude when envelope saturates. Stays
under 1.0 so the rig has rendering head-room above the music
sway for additional drivers (idle drift, webcam tracking)."""

DEFAULT_SMOOTHING_S: float = 0.25
"""Envelope smoothing time constant. ~250 ms feels like the pet
"feels" the music rather than reacting to every sample — too fast
looks jittery, too slow ignores tempo changes."""

_TICK_HZ: int = 30


def compute_envelope(audio_block) -> float:
    """RMS envelope of ``audio_block`` in roughly the ``[0, 1]``
    range.

    ``audio_block`` is whatever ``sounddevice`` passes to the
    callback: a 2-D float32 array of shape ``(frames, channels)``,
    typical values in ``[-1, 1]``. The RMS lands in ``[0, 1]`` for
    well-behaved inputs; we clip at 1.0 to defend against
    drivers reporting slightly above-unity samples.

    Pure helper — accepts any numpy-array-like; tests pass plain
    Python lists so the helper stays importable without numpy.
    """
    try:
        import numpy as np
    except ImportError:
        return 0.0
    arr = np.asarray(audio_block, dtype=np.float32)
    if arr.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(arr.astype(np.float64) ** 2)))
    if math.isnan(rms) or math.isinf(rms):
        return 0.0
    return min(rms, 1.0)


def smooth_envelope(
    current: float, target: float, *, dt_s: float, tau_s: float,
) -> float:
    """Exponential-decay smoothing — same shape as the mouse-gaze
    driver. ``tau_s <= 0`` or ``dt_s <= 0`` snaps to the target so
    callers can opt out of smoothing or recover from a stalled
    clock without a special code path."""
    if tau_s <= 0.0 or dt_s <= 0.0:
        return float(target)
    alpha = 1.0 - math.exp(-float(dt_s) / float(tau_s))
    return float(current) + (float(target) - float(current)) * alpha


def envelope_to_sway(
    envelope: float,
    phase_seconds: float,
    *,
    sway_period_s: float = DEFAULT_SWAY_PERIOD_S,
    sway_amplitude: float = DEFAULT_SWAY_AMPLITUDE,
) -> dict[str, float]:
    """Map a smoothed envelope + accumulated phase to head/body
    Z-axis sway parameters.

    The pet sways at a fixed period (``sway_period_s``); the
    envelope modulates the amplitude. Quiet music → small sway;
    loud music → near-full amplitude. Head and body counter-phase
    by 90° so the motion reads as natural body movement rather
    than rigid bobble.
    """
    if sway_period_s <= 0.0:
        return {PARAM_ANGLE_Z: 0.0, PARAM_BODY_ANGLE_Z: 0.0}
    env = max(0.0, min(1.0, float(envelope)))
    omega = 2.0 * math.pi / float(sway_period_s)
    angle_z = float(sway_amplitude) * env * math.sin(omega * float(phase_seconds))
    body_z = (
        float(sway_amplitude) * env
        * math.sin(omega * float(phase_seconds) + math.pi / 2.0)
        * 0.5   # body sways less than head, otherwise the rig looks rigid
    )
    return {PARAM_ANGLE_Z: angle_z, PARAM_BODY_ANGLE_Z: body_z}


class MusicRhythmDriver(QObject):
    """Drives the rig's Z-axis sway from the system audio envelope.

    Constructed cheap; the audio stream + sounddevice import only
    materialise on :meth:`set_enabled(True)`. Off by default; the
    workspace toggle / tray menu wires the user toggle.
    """

    state_changed = Signal()

    def __init__(self, canvas: PuppetCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self._enabled = False
        self._stream = None
        self._envelope_target: float = 0.0
        self._envelope_smoothed: float = 0.0
        self._phase_anchor: float = 0.0
        self._last_tick: float = 0.0
        self._tau_s: float = DEFAULT_SMOOTHING_S
        self._sway_period_s: float = DEFAULT_SWAY_PERIOD_S
        self._sway_amplitude: float = DEFAULT_SWAY_AMPLITUDE
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / _TICK_HZ))
        self._timer.timeout.connect(self._on_tick)

    # ---- public ----------------------------------------------------

    def is_enabled(self) -> bool:
        return self._enabled

    def envelope(self) -> float:
        """Current smoothed envelope value — useful for tuning UIs
        and tests verifying the audio path is alive."""
        return self._envelope_smoothed

    def set_enabled(self, enabled: bool) -> bool:
        if enabled == self._enabled:
            return True
        if enabled:
            ok = self._open_stream()
            if not ok:
                self._enabled = False
                self.state_changed.emit()
                return False
            self._phase_anchor = time.monotonic()
            self._last_tick = self._phase_anchor
            self._envelope_target = 0.0
            self._envelope_smoothed = 0.0
            self._timer.start()
        else:
            self._timer.stop()
            self._close_stream()
            self._reset_params()
        self._enabled = bool(enabled)
        self.state_changed.emit()
        return True

    def shutdown(self) -> None:
        self._timer.stop()
        self._close_stream()

    def push_envelope(self, value: float) -> None:
        """Test hook — bypass the audio callback by setting the
        envelope target directly. The next ``_on_tick`` will smooth
        toward it and write the sway parameters."""
        self._envelope_target = max(0.0, min(1.0, float(value)))

    def tick_once(self) -> None:
        """Test / debug hook — drive a single tick without the
        QTimer."""
        self._on_tick()

    # ---- stream lifecycle ------------------------------------------

    def _open_stream(self) -> bool:
        """Open a WASAPI loopback InputStream on the default output
        device. Returns ``False`` on any failure — missing module,
        non-Windows OS, no output device, refused permission."""
        if platform.system() != "Windows":
            logger.info(
                "music rhythm: WASAPI loopback is Windows-only "
                "(detected %s); use a virtual loopback device "
                "(BlackHole / PulseAudio monitor) on other OSes",
                platform.system(),
            )
            return False
        try:
            import sounddevice as sd
        except ImportError:
            logger.info("sounddevice not installed; music rhythm unavailable")
            return False
        try:
            output_device = sd.default.device[1]   # (input, output)
            settings = sd.WasapiSettings(loopback=True)
            self._stream = sd.InputStream(
                device=output_device,
                samplerate=DEFAULT_SAMPLE_RATE,
                channels=2,
                blocksize=DEFAULT_BLOCK_SIZE,
                dtype="float32",
                callback=self._on_audio_block,
                extra_settings=settings,
            )
            self._stream.start()
        except Exception as exc:   # noqa: BLE001 - sounddevice raises many types
            logger.warning("music rhythm stream failed: %s", exc)
            self._stream = None
            return False
        return True

    def _close_stream(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        except Exception as exc:   # noqa: BLE001 - same; never crash teardown
            logger.warning("music rhythm stream close failed: %s", exc)

    def _reset_params(self) -> None:
        """Settle the rig back to neutral Z-angles when we stop —
        otherwise the puppet stays frozen mid-sway."""
        if self._canvas.document() is None:
            return
        canvas_values = self._canvas.parameter_values()
        batch = {
            pid: 0.0 for pid in (PARAM_ANGLE_Z, PARAM_BODY_ANGLE_Z)
            if pid in canvas_values
        }
        if batch:
            self._canvas.set_parameter_values(batch)

    # ---- audio callback (background thread) -----------------------

    def _on_audio_block(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        """Runs on sounddevice's worker thread. Just stores the
        envelope target — the GUI-thread :meth:`_on_tick` reads it
        on the next 30 Hz tick. Plain float assignment is GIL-safe,
        so no lock needed."""
        if status:
            logger.debug("music rhythm audio status: %s", status)
        self._envelope_target = compute_envelope(indata)

    # ---- GUI-thread tick ------------------------------------------

    def _on_tick(self) -> None:
        if not self._enabled or self._canvas.document() is None:
            return
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now
        self._envelope_smoothed = smooth_envelope(
            self._envelope_smoothed,
            self._envelope_target,
            dt_s=dt,
            tau_s=self._tau_s,
        )
        phase = now - self._phase_anchor
        targets = envelope_to_sway(
            self._envelope_smoothed,
            phase,
            sway_period_s=self._sway_period_s,
            sway_amplitude=self._sway_amplitude,
        )
        canvas_values = self._canvas.parameter_values()
        batch = {pid: v for pid, v in targets.items() if pid in canvas_values}
        if batch:
            self._canvas.set_parameter_values(batch)
