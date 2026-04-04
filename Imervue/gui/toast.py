"""
Toast 通知系統
Lightweight toast/snackbar notifications displayed at the bottom of the viewer.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QLabel, QWidget, QGraphicsOpacityEffect


class ToastWidget(QLabel):
    """半透明浮動通知標籤"""

    _STYLE = {
        "info": "background: rgba(50,50,50,200); color: #eee;",
        "success": "background: rgba(30,100,50,210); color: #eee;",
        "warning": "background: rgba(160,120,10,210); color: #fff;",
        "error": "background: rgba(160,30,30,210); color: #fff;",
    }

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setVisible(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

        self._anim: QPropertyAnimation | None = None

    def show_message(self, text: str, level: str = "info", duration_ms: int = 2500):
        base = self._STYLE.get(level, self._STYLE["info"])
        self.setStyleSheet(
            f"{base} border-radius: 6px; padding: 8px 18px; font-size: 13px;"
        )
        self.setText(text)
        self.adjustSize()
        self._reposition()
        self.setVisible(True)

        # 淡入
        if self._anim:
            self._anim.stop()
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(200)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

        self._hide_timer.start(duration_ms)

    def _fade_out(self):
        if self._anim:
            self._anim.stop()
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(400)
        self._anim.setStartValue(self._opacity.opacity())
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InQuad)
        self._anim.finished.connect(lambda: self.setVisible(False))
        self._anim.start()

    def _reposition(self):
        parent = self.parentWidget()
        if parent:
            w = min(self.sizeHint().width() + 36, parent.width() - 40)
            self.setFixedWidth(w)
            x = (parent.width() - w) // 2
            y = parent.height() - self.sizeHint().height() - 40
            self.move(x, max(y, 10))


class ToastManager:
    """全局 toast 管理器（每個主視窗一個）"""

    def __init__(self, parent: QWidget):
        self._toast = ToastWidget(parent)

    def info(self, text: str, duration_ms: int = 2500):
        self._toast.show_message(text, "info", duration_ms)

    def success(self, text: str, duration_ms: int = 2500):
        self._toast.show_message(text, "success", duration_ms)

    def warning(self, text: str, duration_ms: int = 3000):
        self._toast.show_message(text, "warning", duration_ms)

    def error(self, text: str, duration_ms: int = 4000):
        self._toast.show_message(text, "error", duration_ms)
