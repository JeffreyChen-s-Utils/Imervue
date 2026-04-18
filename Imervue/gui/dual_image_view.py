"""
雙圖顯示檢視
Dual image view — side-by-side display for Split view and Manga/dual-page reading.

Split mode: user picks any two images; arrow keys step both pages in sync.
Manga mode: shows current_index + current_index+1; arrow keys step by 2.
Manga RTL mode: swaps panels so page 1 is on the right (right-to-left reading).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSplitter, QSizePolicy,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


class _Panel(QLabel):
    """Self-scaling pixmap panel used for each half of the dual view."""

    def __init__(self):
        super().__init__()
        self._pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.setMinimumSize(100, 100)
        self.setStyleSheet(
            "background-color: #0f0f0f; color: #888;"
        )

    def load(self, path: str | None) -> None:
        if path is None or not Path(path).is_file():
            self._pixmap = None
            self.setPixmap(QPixmap())
            self.setText("—")
            return
        pm = QPixmap(path)
        if pm.isNull():
            self._pixmap = None
            self.setText("—")
            return
        self._pixmap = pm
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


class DualImageView(QWidget):
    """Widget that shows two images side-by-side with a caption row.

    This sits inside the main window's view stack alongside the GL viewer
    and the list view. Navigation is driven by the main window calling
    ``advance(step)``; the widget itself only handles display.
    """

    closed = Signal()  # emitted when the user presses Esc

    MODE_SPLIT = "split"
    MODE_MANGA = "manga"
    MODE_MANGA_RTL = "manga_rtl"

    def __init__(self, main_window: ImervueMainWindow):
        super().__init__()
        self._main_window = main_window
        self._mode: str = self.MODE_SPLIT
        self._left_path: str | None = None
        self._right_path: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._title = QLabel("")
        title_font = QFont("Segoe UI")
        title_font.setPixelSize(12)
        self._title.setFont(title_font)
        self._title.setStyleSheet("color: #bbb; padding: 4px 8px; background: #1a1a1a;")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._title)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._panel_a = _Panel()
        self._panel_b = _Panel()
        self._splitter.addWidget(self._panel_a)
        self._splitter.addWidget(self._panel_b)
        self._splitter.setChildrenCollapsible(False)
        root.addWidget(self._splitter, stretch=1)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # -------- Public API --------
    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in (self.MODE_SPLIT, self.MODE_MANGA, self.MODE_MANGA_RTL):
            return
        self._mode = mode

    def set_pair(self, left_path: str | None, right_path: str | None) -> None:
        """Load the two images, honouring RTL (right page first in manga RTL)."""
        self._left_path = left_path
        self._right_path = right_path
        if self._mode == self.MODE_MANGA_RTL:
            # Panel A is displayed leftmost visually; in RTL we want the
            # *later* page on the left so the user scans right→left.
            self._panel_a.load(right_path)
            self._panel_b.load(left_path)
        else:
            self._panel_a.load(left_path)
            self._panel_b.load(right_path)
        self._update_title()

    def _update_title(self) -> None:
        lang = language_wrapper.language_word_dict
        if self._mode == self.MODE_SPLIT:
            prefix = lang.get("dual_split_title", "Split View")
        elif self._mode == self.MODE_MANGA_RTL:
            prefix = lang.get("dual_manga_rtl_title", "Dual Page (RTL)")
        else:
            prefix = lang.get("dual_manga_title", "Dual Page")
        a = Path(self._left_path).name if self._left_path else "—"
        b = Path(self._right_path).name if self._right_path else "—"
        self._title.setText(f"{prefix}   \u2502   {a}   |   {b}")

    # -------- Navigation helpers --------
    def step_pair_in_list(self, images: list[str], current_idx: int,
                          step: int) -> int:
        """Advance the (left, right) pair within ``images`` by ``step`` pages.

        Returns the new left-index. In manga mode we usually step by 2; in
        split mode the caller decides the step. Clamped to list bounds.
        """
        if not images:
            return current_idx
        new_left = max(0, min(current_idx + step, len(images) - 1))
        new_right = new_left + 1 if new_left + 1 < len(images) else None
        self.set_pair(
            images[new_left],
            images[new_right] if new_right is not None else None,
        )
        return new_left

    # -------- Events --------
    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Escape:
            self.closed.emit()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction = -1 if key == Qt.Key.Key_Left else 1
            # In manga RTL the spatial direction is flipped — left arrow
            # goes "forward" in reading order
            if self._mode == self.MODE_MANGA_RTL:
                direction = -direction
            step = 2 if self._mode.startswith("manga") else 1
            if mods & Qt.KeyboardModifier.ShiftModifier:
                step = max(1, step // 2)  # Shift → single page step even in manga
            self._request_step(direction * step)
            return
        super().keyPressEvent(event)

    def _request_step(self, step: int) -> None:
        """Ask the main window to advance the dual view by ``step`` images."""
        mw = self._main_window
        images = mw.viewer.model.images
        if not images:
            return
        cur = mw.viewer.current_index
        new_idx = self.step_pair_in_list(images, cur, step)
        mw.viewer.current_index = new_idx
