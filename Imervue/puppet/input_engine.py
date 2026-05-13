"""Live input pumping into a :class:`PuppetCanvas`.

Owns the QTimers that drive auto-blink, the active drag-tracking
state, and (when ``sounddevice`` is installed) a microphone stream
feeding lip-sync. Each driver is independently toggleable; absent
optional deps degrade silently rather than blocking the rest.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.input_drivers import (
    DEFAULT_EYE_PARAMS,
    DEFAULT_MOUTH_FORM_PARAM,
    DEFAULT_MOUTH_PARAM,
    audio_to_viseme,
    blink_curve_value,
    cursor_to_angle_params,
)

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.plugin.puppet.input_engine")

_BLINK_TICK_HZ: int = 30
_AUDIO_BLOCK_SAMPLES: int = 1024
_AUDIO_SAMPLE_RATE: int = 22050


class InputEngine(QObject):
    """Holds the state for the three live-input sources."""

    state_changed = Signal()

    def __init__(self, canvas: PuppetCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self._blink_enabled = False
        self._drag_enabled = False
        self._lipsync_enabled = False
        self._blink_anchor: float = time.monotonic()
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(int(1000 / _BLINK_TICK_HZ))
        self._blink_timer.timeout.connect(self._on_blink_tick)
        self._mic_stream = None

    # ---- public ---------------------------------------------------------

    def set_drag_enabled(self, enabled: bool) -> None:
        self._drag_enabled = bool(enabled)
        if not enabled:
            self._reset_drag_params()
        self.state_changed.emit()

    def drag_enabled(self) -> bool:
        return self._drag_enabled

    def push_cursor(self, image_x: float, image_y: float) -> None:
        """Workspace forwards canvas mouse hovers here. No-op when drag
        tracking is off — keeps the wiring cheap when unused."""
        if not self._drag_enabled or self._canvas.document() is None:
            return
        size = self._canvas.document().size
        values = cursor_to_angle_params(image_x, image_y, size[0], size[1])
        self._canvas.set_parameter_values(values)

    def set_blink_enabled(self, enabled: bool) -> None:
        if enabled == self._blink_enabled:
            return
        self._blink_enabled = bool(enabled)
        if enabled:
            self._blink_anchor = time.monotonic()
            self._blink_timer.start()
        else:
            self._blink_timer.stop()
            self._reset_blink_params()
        self.state_changed.emit()

    def blink_enabled(self) -> bool:
        return self._blink_enabled

    def set_lipsync_enabled(self, enabled: bool) -> bool:
        """Returns ``True`` if the requested state was reached. Mic
        capture failure (no device / no sounddevice) sets back to
        ``False`` and reports failure to the caller."""
        if enabled == self._lipsync_enabled:
            return True
        if enabled:
            ok = self._start_mic()
            if not ok:
                self._lipsync_enabled = False
                self.state_changed.emit()
                return False
        else:
            self._stop_mic()
        self._lipsync_enabled = bool(enabled)
        self.state_changed.emit()
        return True

    def lipsync_enabled(self) -> bool:
        return self._lipsync_enabled

    def shutdown(self) -> None:
        self._blink_timer.stop()
        self._stop_mic()

    # ---- blink ----------------------------------------------------------

    def _on_blink_tick(self) -> None:
        if not self._blink_enabled or self._canvas.document() is None:
            return
        elapsed = time.monotonic() - self._blink_anchor
        value = blink_curve_value(elapsed)
        self._canvas.set_parameter_values(
            {eye_param: value for eye_param in DEFAULT_EYE_PARAMS},
        )

    def _reset_blink_params(self) -> None:
        if self._canvas.document() is None:
            return
        self._canvas.set_parameter_values(
            {eye_param: 1.0 for eye_param in DEFAULT_EYE_PARAMS},
        )

    def _reset_drag_params(self) -> None:
        if self._canvas.document() is None:
            return
        self._canvas.set_parameter_values({
            "ParamAngleX": 0.0,
            "ParamAngleY": 0.0,
            "ParamEyeBallX": 0.0,
            "ParamEyeBallY": 0.0,
        })

    # ---- microphone -----------------------------------------------------

    def _start_mic(self) -> bool:
        try:
            import sounddevice as sd
        except ImportError:
            logger.info("sounddevice not installed; lip-sync unavailable")
            return False
        try:
            self._mic_stream = sd.InputStream(
                samplerate=_AUDIO_SAMPLE_RATE, channels=1,
                blocksize=_AUDIO_BLOCK_SAMPLES, dtype="float32",
                callback=self._on_audio_block,
            )
            self._mic_stream.start()
        except Exception as exc:   # noqa: BLE001 - sounddevice raises a zoo of types
            logger.warning("mic stream failed: %s", exc)
            self._mic_stream = None
            return False
        return True

    def _stop_mic(self) -> None:
        stream = self._mic_stream
        self._mic_stream = None
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        except Exception as exc:   # noqa: BLE001 - same; never want to crash teardown
            logger.warning("mic stream close failed: %s", exc)
        if self._canvas.document() is not None:
            self._canvas.set_parameter_values({
                DEFAULT_MOUTH_PARAM: 0.0,
                DEFAULT_MOUTH_FORM_PARAM: 0.0,
            })

    def _on_audio_block(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            logger.debug("mic status %s", status)
        if self._canvas.document() is None:
            return
        viseme = audio_to_viseme(indata, sample_rate=_AUDIO_SAMPLE_RATE)
        # Defer the parameter writes to the Qt thread — Qt slots aren't
        # thread-safe to call from sounddevice's callback. ``QTimer.singleShot``
        # with a 0 ms delay queues the work onto the GUI loop.
        QTimer.singleShot(0, lambda v=viseme: self._apply_viseme(v))

    def _apply_viseme(self, viseme: dict[str, float]) -> None:
        if not self._lipsync_enabled or self._canvas.document() is None:
            return
        self._canvas.set_parameter_values({
            DEFAULT_MOUTH_PARAM: float(viseme.get(DEFAULT_MOUTH_PARAM, 0.0)),
            DEFAULT_MOUTH_FORM_PARAM: float(
                viseme.get(DEFAULT_MOUTH_FORM_PARAM, 0.0),
            ),
        })
