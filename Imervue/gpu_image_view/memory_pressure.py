"""Memory-pressure indicator for the GPU tile cache.

The GPUImageView already tracks VRAM usage against a budget
(``_vram_usage`` / ``_vram_limit``); the Ctrl+F3 Debug HUD surfaces
it, but only when the user explicitly enables the overlay. Users
running on tight budgets or browsing large folders don't see the
pressure until tiles start evicting visibly.

This module ships an always-visible status-bar widget: a small
coloured dot + percentage label that goes green / yellow / red as
usage approaches the limit. Click for a tooltip showing the raw
numbers and a "clear cache" hook.

Pure helpers (:func:`state_from_usage`, :func:`format_usage_label`)
encapsulate the colour and label policy with no Qt dependency so
tests cover the thresholds without spawning a widget.
"""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

DEFAULT_POLL_INTERVAL_MS: int = 1000
"""How often the indicator polls the source. One second matches
the Debug HUD's natural update rate; finer polling is wasted CPU
because the tile cache doesn't change on every paint."""

YELLOW_THRESHOLD: float = 0.60
"""Fraction of the VRAM budget at which the dot turns yellow.
Below this the cache has plenty of headroom; above, the next
folder swap may start evicting hot tiles."""

RED_THRESHOLD: float = 0.85
"""Fraction at which the dot turns red. Past 85 % the LRU is
working hard — every prefetch costs an eviction. Click the dot to
inspect or clear the cache."""

DOT_DIAMETER_PX: int = 10
"""Small enough to read as 'a dot' rather than 'a status box'."""


class MemoryPressureState(Enum):
    """Three discrete states the indicator can show. Mapping to a
    colour + tooltip phrasing lives in the widget; the threshold
    policy lives in :func:`state_from_usage`."""

    GREEN = "green"     # < YELLOW_THRESHOLD
    YELLOW = "yellow"   # YELLOW_THRESHOLD ≤ usage < RED_THRESHOLD
    RED = "red"         # ≥ RED_THRESHOLD


def state_from_usage(
    used_bytes: int,
    limit_bytes: int,
    *,
    yellow_threshold: float = YELLOW_THRESHOLD,
    red_threshold: float = RED_THRESHOLD,
) -> MemoryPressureState:
    """Map a ``(used, limit)`` byte pair to a discrete state.

    Robust against zero / negative ``limit`` (returns
    :attr:`MemoryPressureState.GREEN` — without a limit we can't
    say anything meaningful about pressure, and the UI shouldn't
    light up red on a misconfigured cache).
    """
    if limit_bytes <= 0:
        return MemoryPressureState.GREEN
    fraction = max(0.0, float(used_bytes) / float(limit_bytes))
    if fraction >= red_threshold:
        return MemoryPressureState.RED
    if fraction >= yellow_threshold:
        return MemoryPressureState.YELLOW
    return MemoryPressureState.GREEN


def format_usage_label(used_bytes: int, limit_bytes: int) -> str:
    """Human-readable percentage for the status-bar text.

    Returns ``"--"`` when the limit is zero / negative so the
    widget shows a placeholder instead of ``inf%`` during the
    brief window between widget construction and first VRAM probe.
    """
    if limit_bytes <= 0:
        return "--"
    pct = (float(used_bytes) / float(limit_bytes)) * 100.0
    return f"{pct:.0f}%"


def format_tooltip(
    used_bytes: int,
    limit_bytes: int,
    *,
    tile_count: int | None = None,
    prefetch_count: int | None = None,
) -> str:
    """Multi-line tooltip body for the indicator. ``tile_count`` /
    ``prefetch_count`` are optional — when the caller doesn't have
    them, just the byte totals are shown."""
    used_mb = used_bytes / (1024 * 1024)
    limit_mb = limit_bytes / (1024 * 1024) if limit_bytes > 0 else 0.0
    lines = [
        f"Tile-cache VRAM: {used_mb:.1f} MB / {limit_mb:.1f} MB",
    ]
    if tile_count is not None:
        lines.append(f"Loaded tiles: {tile_count}")
    if prefetch_count is not None:
        lines.append(f"Prefetched images: {prefetch_count}")
    lines.append("Click to clear the tile cache.")
    return "\n".join(lines)


class MemoryPressureIndicator(QWidget):
    """Status-bar widget: small coloured dot + percentage label.

    The widget owns nothing about the GPUImageView — it polls a
    user-supplied callable each tick and re-paints. This keeps the
    widget testable in isolation (tests pass a fake source) and
    avoids a hard dependency on the view's specific attribute
    names.

    Source callable contract:
        ``source() → dict`` with keys:
            * ``used_bytes`` (int)
            * ``limit_bytes`` (int)
            * ``tile_count`` (int, optional)
            * ``prefetch_count`` (int, optional)

        Missing optional keys default to ``None`` in the tooltip.
    """

    def __init__(
        self,
        source: Callable[[], dict],
        *,
        clear_cache: Callable[[], None] | None = None,
        poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._clear_cache = clear_cache
        self._state: MemoryPressureState = MemoryPressureState.GREEN
        self._used_bytes: int = 0
        self._limit_bytes: int = 0
        self._tile_count: int | None = None
        self._prefetch_count: int | None = None
        self._dot = _DotWidget(self)
        self._label = QLabel("--", self)
        self._label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred,
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        from PySide6.QtWidgets import QHBoxLayout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)
        layout.addWidget(self._dot)
        layout.addWidget(self._label)
        self._timer = QTimer(self)
        self._timer.setInterval(int(poll_interval_ms))
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        # Prime the display so the user doesn't see "--" for a full
        # tick after the widget is added to the status bar.
        self.refresh()

    # ---- public API -----------------------------------------------

    def state(self) -> MemoryPressureState:
        return self._state

    def refresh(self) -> None:
        """Poll the source + repaint. Called on a timer and on
        manual request."""
        try:
            data = self._source() or {}
        except Exception:   # noqa: BLE001 - source might be a stale view ref during shutdown
            return
        self._used_bytes = int(data.get("used_bytes", 0))
        self._limit_bytes = int(data.get("limit_bytes", 0))
        self._tile_count = data.get("tile_count")
        self._prefetch_count = data.get("prefetch_count")
        self._state = state_from_usage(self._used_bytes, self._limit_bytes)
        self._label.setText(
            format_usage_label(self._used_bytes, self._limit_bytes),
        )
        self.setToolTip(format_tooltip(
            self._used_bytes, self._limit_bytes,
            tile_count=self._tile_count,
            prefetch_count=self._prefetch_count,
        ))
        self._dot.set_state(self._state)

    def shutdown(self) -> None:
        self._timer.stop()

    def mousePressEvent(self, event) -> None:   # noqa: N802 - Qt override
        """Left-click → clear the cache via the user-supplied
        callback. Falls back to a no-op when no callback was wired
        so the widget can be used as a pure display."""
        if event.button() == Qt.MouseButton.LeftButton and self._clear_cache:
            self._clear_cache()
            # Repaint right away — otherwise the dot stays red for
            # up to one poll interval after the user clicked clear.
            self.refresh()
        super().mousePressEvent(event)


class _DotWidget(QWidget):
    """The coloured circle. Drawn manually so a future style swap
    (gradient, ring instead of disc, etc.) doesn't fight QSS."""

    _COLOURS: dict[MemoryPressureState, QColor] = {
        MemoryPressureState.GREEN: QColor(46, 200, 70),
        MemoryPressureState.YELLOW: QColor(220, 180, 30),
        MemoryPressureState.RED: QColor(220, 60, 60),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = MemoryPressureState.GREEN
        self.setFixedSize(DOT_DIAMETER_PX + 4, DOT_DIAMETER_PX + 4)

    def set_state(self, state: MemoryPressureState) -> None:
        if state is self._state:
            return
        self._state = state
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:   # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._COLOURS[self._state])
        offset = (self.width() - DOT_DIAMETER_PX) // 2
        painter.drawEllipse(offset, offset, DOT_DIAMETER_PX, DOT_DIAMETER_PX)
