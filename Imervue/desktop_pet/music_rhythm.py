"""Music-rhythm driver — pet sways to system audio.

When enabled, the driver captures the system playback mix through a
WASAPI *loopback* endpoint (Windows-only, via ``sounddevice``), reads
the playback envelope, and modulates the pet's head + body Z-axis
sway so the rig physically bobs to whatever's playing. Calm tracks
produce subtle sway; loud / percussive material drives bigger
swings.

A loopback endpoint is enumerated by PortAudio as an ordinary *input*
device that happens to mirror a render endpoint, so the capture path is
a plain ``InputStream`` on the index :func:`find_loopback_device`
picks. Builds that expose no such device cannot record system audio at
all, and the driver reports failure instead of falling back to a
microphone — swaying to room noise would look like the feature works
while following the wrong signal entirely.

WASAPI loopback is Windows-specific. macOS / Linux fall back to
"return False on enable" so the workspace can surface the
"system audio loopback isn't supported on this OS" message. Users
on those platforms can still get rhythm sync by routing system
audio through BlackHole / PulseAudio monitor sources into a real
input device, but that's manual setup we don't try to automate.

Pure helpers (:func:`compute_envelope`, :func:`smooth_envelope`,
:func:`envelope_to_sway`, :func:`find_loopback_device`,
:func:`capture_channel_count`, :func:`capture_sample_rate`) work on
plain values with no audio dependency so both the tuning logic and the
device selection are unit-testable without opening a real stream.
"""
from __future__ import annotations

import logging
import math
import platform
import time
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.standard_params import (
    PARAM_ANGLE_Z,
    PARAM_BODY_ANGLE_Z,
)

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.desktop_pet.music_rhythm")

DEFAULT_SAMPLE_RATE: int = 44100
"""Fallback only. The chosen endpoint's own rate wins — see
:func:`capture_sample_rate`."""

DEFAULT_BLOCK_SIZE: int = 1024
"""~23 ms at 44.1 kHz. Short enough to track transients
(percussive hits) without massive CPU overhead."""

MAX_CAPTURE_CHANNELS: int = 2
"""The envelope is one RMS over the whole block, so channels past
stereo add bandwidth without changing the number."""

_LOOPBACK_MARKER = "loopback"
_PREFERRED_HOST_API = "wasapi"

# Preference ranks for a loopback capture candidate — lower wins.
_RANK_DEFAULT_ENDPOINT_ON_WASAPI = 0
_RANK_DEFAULT_ENDPOINT = 1
_RANK_WASAPI = 2
_RANK_OTHER = 3

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


# ---------------------------------------------------------------------
# Loopback capture-device selection (pure — takes plain device dicts)
# ---------------------------------------------------------------------


def _as_int(value: Any, default: int = 0) -> int:
    """Best-effort int coercion; device dicts come from a C library."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _strip_loopback_marker(name: str) -> str:
    """*name* without its loopback tag and the bracket that held it.

    ``"Speakers (Realtek) [Loopback]"`` → ``"Speakers (Realtek)"``, which
    is what matches the render endpoint the device mirrors — that one
    carries no tag.
    """
    index = name.lower().find(_LOOPBACK_MARKER)
    if index < 0:
        return name.strip()
    return name[:index].rstrip(" ([{-").strip()


def _host_api_name(hostapis: Sequence[Mapping[str, Any]],
                   info: Mapping[str, Any]) -> str:
    """Lower-cased host-API name for *info*, or ``""`` when unresolvable."""
    index = _as_int(info.get("hostapi"), -1)
    if not 0 <= index < len(hostapis):
        return ""
    return str(hostapis[index].get("name", "")).lower()


def _default_output_name(devices: Sequence[Mapping[str, Any]],
                         default_output: Any) -> str:
    """Lower-cased name of the default render endpoint, or ``""``."""
    index = _as_int(default_output, -1)
    if not 0 <= index < len(devices):
        return ""
    return str(devices[index].get("name", "")).strip().lower()


def _rank_loopback_candidate(name: str, host_api: str, target: str) -> int:
    """Preference rank for a loopback capture device; lower wins."""
    on_wasapi = _PREFERRED_HOST_API in host_api
    if target and _strip_loopback_marker(name).lower() == target:
        return (_RANK_DEFAULT_ENDPOINT_ON_WASAPI if on_wasapi
                else _RANK_DEFAULT_ENDPOINT)
    return _RANK_WASAPI if on_wasapi else _RANK_OTHER


def find_loopback_device(
    devices: Sequence[Mapping[str, Any]],
    hostapis: Sequence[Mapping[str, Any]],
    default_output: Any = None,
) -> int | None:
    """Index of the capture device that records what the system is playing.

    PortAudio exposes a render endpoint's loopback as an extra *input*
    device whose name carries a ``[Loopback]`` tag; opening that index
    captures the mix the user is hearing. Output-only entries are skipped
    because an ``InputStream`` on a device with no input channels fails
    outright, which is the trap this selection exists to avoid.

    ``None`` means the running PortAudio build exposes no loopback
    endpoint. Deliberately not a fall back to the default microphone: the
    pet would sway convincingly to room noise and the user would have no
    way to tell the feature was following the wrong signal.

    The endpoint mirroring *default_output* wins so the pet follows what
    the user is actually listening to, and WASAPI breaks the tie because
    a tagged device on another host API is a virtual cable whose routing
    we cannot verify.
    """
    target = _default_output_name(devices, default_output)
    best: tuple[int, int] | None = None
    for index, info in enumerate(devices):
        if _as_int(info.get("max_input_channels")) <= 0:
            continue
        name = str(info.get("name", ""))
        if _LOOPBACK_MARKER not in name.lower():
            continue
        rank = _rank_loopback_candidate(
            name, _host_api_name(hostapis, info), target)
        if best is None or rank < best[0]:
            best = (rank, index)
    return None if best is None else best[1]


def capture_channel_count(max_input_channels: Any) -> int:
    """Channel count to open on a loopback endpoint.

    Clamped into ``[1, MAX_CAPTURE_CHANNELS]``: a mono endpoint must not
    be asked for two, and a surround endpoint gains nothing from the
    extra channels.
    """
    return max(1, min(MAX_CAPTURE_CHANNELS, _as_int(max_input_channels)))


def capture_sample_rate(default_samplerate: Any) -> int:
    """Sample rate to request on a loopback endpoint.

    The endpoint's own rate rather than a fixed 44.1 kHz: WASAPI shared
    mode runs at the system mixer rate and rejects anything else, so a
    hard-coded rate fails outright on the 48 kHz devices most Windows
    machines ship with. The envelope is an RMS, so it reads the same at
    any rate.
    """
    rate = _as_int(default_samplerate)
    return rate if rate > 0 else DEFAULT_SAMPLE_RATE


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
        """Open a capture stream on the system's loopback endpoint.

        Returns ``False`` on any failure — missing module, non-Windows
        OS, a PortAudio build that enumerates no loopback endpoint,
        refused permission.
        """
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
            devices = sd.query_devices()
            index = find_loopback_device(
                devices, sd.query_hostapis(), sd.default.device[1],
            )
        except Exception as exc:   # noqa: BLE001 - sounddevice raises many types
            logger.warning("music rhythm device query failed: %s", exc)
            return False
        if index is None:
            logger.info(
                "music rhythm: no loopback capture endpoint is available; "
                "this PortAudio build does not expose one. Enable Stereo "
                "Mix or install a virtual loopback cable to sync the pet "
                "to system audio",
            )
            return False
        return self._start_stream(sd, index, devices[index])

    def _start_stream(self, sd, index: int, info: Mapping[str, Any]) -> bool:
        """Open and start the capture stream on the chosen endpoint."""
        try:
            self._stream = sd.InputStream(
                device=index,
                samplerate=capture_sample_rate(info.get("default_samplerate")),
                channels=capture_channel_count(info.get("max_input_channels")),
                blocksize=DEFAULT_BLOCK_SIZE,
                dtype="float32",
                callback=self._on_audio_block,
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
