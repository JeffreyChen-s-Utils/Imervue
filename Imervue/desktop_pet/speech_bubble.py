"""Speech-bubble overlay for the desktop pet.

A tiny frameless / transparent / top-most QWidget that pops above
the pet to display a short message — fired when the user clicks
the pet, when an idle motion starts, or whenever the caller wants
to draw attention. Auto-fades after a configurable hold time so
the pet doesn't end up wearing a permanent caption.

The bubble is positioned relative to a reference window (the pet
overlay) so dragging the pet brings the bubble along — handled by
the pet window calling :meth:`anchor_to` whenever it moves.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QWidget

logger = logging.getLogger("Imervue.desktop_pet.speech_bubble")

DEFAULT_HOLD_MS: int = 4000
"""How long the bubble stays at full opacity before the fade-out
animation starts. Long enough to read a short greeting comfortably;
short enough that the pet doesn't camp on top of the user's work."""

FADE_MS: int = 400
"""Duration of the fade-out animation that runs after the hold."""

_BUBBLE_BACKGROUND: QColor = QColor(255, 255, 255, 235)
_BUBBLE_BORDER: QColor = QColor(80, 80, 90, 255)
_BUBBLE_TEXT: QColor = QColor(30, 30, 35, 255)
_PADDING_X: int = 12
_PADDING_Y: int = 8
_RADIUS: int = 10
_TAIL: int = 8


class SpeechBubble(QWidget):
    """Frameless overlay that draws a rounded rectangle with a
    pointed tail, holding one short text line. Anchored to a
    parent reference window via :meth:`anchor_to`."""

    closed = Signal()
    """Emitted after the fade-out finishes — owner can use it to
    deallocate / pool the bubble if they're managing many."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(None)
        # Always-on-top + frameless + tool (no taskbar) + click-
        # through. The bubble is decorative — it should never steal
        # focus or block clicks from reaching whatever's under it.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # Label inside the bubble carries the text + handles
        # alignment / wrapping. Setting margins on the label gives
        # the rounded-rect background room around the text.
        self._label = QLabel("", self)
        self._label.setStyleSheet(
            f"color: rgba({_BUBBLE_TEXT.red()}, {_BUBBLE_TEXT.green()}, "
            f"{_BUBBLE_TEXT.blue()}, 255); "
            "font-size: 11pt; padding: 0;",
        )
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
        )
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._start_fade)
        self._fade_anim: QPropertyAnimation | None = None
        self._anchor_rect: QRect | None = None
        self.hide()

    # ---- public API --------------------------------------------

    def show_message(
        self, text: str, *, hold_ms: int = DEFAULT_HOLD_MS,
    ) -> None:
        """Pop the bubble with ``text``. If a bubble is already
        showing, swap the message rather than spawning a second
        one — the pet should never wear two speech bubbles at
        once. ``hold_ms`` 0 keeps it open until explicitly closed."""
        text = text.strip()
        if not text:
            return
        self._label.setText(text)
        self._resize_for_text()
        self._reposition_to_anchor()
        if self._fade_anim is not None:
            self._fade_anim.stop()
            self._fade_anim = None
        self.setWindowOpacity(1.0)
        self.show()
        # ``hold_ms == 0`` means "stay open until close_bubble is
        # called explicitly" — used by callers that want the bubble
        # to hold while a longer-running event is in flight.
        if hold_ms > 0:
            self._hold_timer.start(max(0, int(hold_ms)))
        else:
            self._hold_timer.stop()

    def anchor_to(self, rect: QRect) -> None:
        """Caller (pet window) calls this every time the pet
        moves or resizes. The bubble re-snaps itself above the
        rect; passing ``None`` (or an empty rect) leaves it as-is."""
        if rect is None or rect.isEmpty():
            return
        self._anchor_rect = QRect(rect)
        if self.isVisible():
            self._reposition_to_anchor()

    def close_bubble(self) -> None:
        """Caller (pet window) calls this to dismiss the bubble
        immediately, skipping the fade — used when the pet hides
        or the rig swaps."""
        self._hold_timer.stop()
        if self._fade_anim is not None:
            self._fade_anim.stop()
            self._fade_anim = None
        self.hide()
        self.closed.emit()

    # ---- painting ----------------------------------------------

    def paintEvent(self, event) -> None:   # pragma: no cover - GL/paint
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        body_rect = rect.adjusted(0, 0, 0, -_TAIL)
        path = QPainterPath()
        path.addRoundedRect(body_rect, _RADIUS, _RADIUS)
        # Triangular tail pointing down from the bottom-centre of
        # the body — anchored a little left of centre so the
        # bubble points "toward the pet" rather than directly down.
        tail_x = body_rect.center().x() + 6
        tail_top_y = body_rect.bottom()
        path.moveTo(tail_x - _TAIL, tail_top_y)
        path.lineTo(tail_x, rect.bottom())
        path.lineTo(tail_x + _TAIL, tail_top_y)
        path.closeSubpath()
        painter.fillPath(path, _BUBBLE_BACKGROUND)
        pen = QPen(_BUBBLE_BORDER, 1.5)
        painter.setPen(pen)
        painter.drawPath(path)

    # ---- internals ---------------------------------------------

    def _resize_for_text(self) -> None:
        """Pick a width based on the text, then ask Qt for the
        natural label height. Wrap caps at ~280 px so long
        sentences fold into two lines instead of stretching across
        the screen."""
        # The label's own size hint gives us a reasonable target;
        # add padding for the rounded rect + tail.
        hint = self._label.sizeHint()
        width = min(hint.width(), 280) + _PADDING_X * 2
        self._label.setWordWrap(True)
        self._label.setFixedWidth(max(80, width - _PADDING_X * 2))
        height_hint = self._label.heightForWidth(self._label.width())
        height = max(hint.height(), height_hint) + _PADDING_Y * 2 + _TAIL
        self.resize(width, height)
        # Centre the label inside the body region (excluding the tail).
        self._label.setGeometry(
            _PADDING_X, _PADDING_Y,
            self.width() - _PADDING_X * 2,
            self.height() - _PADDING_Y * 2 - _TAIL,
        )

    def _reposition_to_anchor(self) -> None:
        if self._anchor_rect is None:
            return
        # Position bubble centred horizontally above the anchor,
        # offset upward by its own height + a small gap.
        gap = 6
        x = self._anchor_rect.center().x() - self.width() // 2
        y = self._anchor_rect.top() - self.height() - gap
        # Push the bubble back inside the parent rect if anchor
        # is near the top of the screen — better to overlap the
        # pet than disappear off-screen.
        if y < 0:
            y = self._anchor_rect.top() + gap
        self.move(x, y)

    def _start_fade(self) -> None:
        """Hold timer expired — fade to opacity 0 and then
        actually hide. Using window opacity (not widget opacity)
        keeps the rounded-rect anti-aliasing intact during the
        fade."""
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(FADE_MS)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self._on_fade_finished)
        self._fade_anim = anim
        anim.start()

    def _on_fade_finished(self) -> None:
        self._fade_anim = None
        self.hide()
        self.setWindowOpacity(1.0)
        self.closed.emit()
