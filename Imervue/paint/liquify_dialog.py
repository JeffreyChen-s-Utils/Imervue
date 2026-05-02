"""Modal liquify dialog wrapping the :mod:`Imervue.paint.liquify` engine.

The engine ships four brushes — push / pinch / bloat / twirl — but
until now only as pure-numpy verbs callable from a script. The
dialog provides:

* a brush-kind dropdown (the four warp kinds),
* radius / strength sliders,
* a preview QLabel showing the working image,
* drag-on-the-preview to apply the active brush at the cursor,
* OK / Cancel — Cancel restores the original buffer.

The engine is unchanged; the dialog is purely UI plumbing plus the
mouse-to-image-coord conversion.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.liquify import (
    WARP_KINDS,
    bloat_warp,
    pinch_warp,
    push_warp,
    twirl_warp,
)

DEFAULT_BRUSH_RADIUS = 60
DEFAULT_BRUSH_STRENGTH_PERCENT = 50   # slider is 0..100; engine takes 0..1
DEFAULT_TWIRL_DEGREES = 30
PREVIEW_MAX_DIMENSION = 512


class LiquifyDialog(QDialog):
    """Edit an HxWx4 RGBA buffer in place via the liquify brushes."""

    def __init__(self, image: np.ndarray, parent=None):
        super().__init__(parent)
        if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
            raise ValueError(
                f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
            )
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("paint_liquify_title", "Liquify"))

        self._original = image.copy()
        self._working = image.copy()
        self._kind = WARP_KINDS[0]
        self._radius = DEFAULT_BRUSH_RADIUS
        self._strength_percent = DEFAULT_BRUSH_STRENGTH_PERCENT
        self._last_mouse: QPointF | None = None

        layout = QVBoxLayout(self)

        self._preview = QLabel()
        self._preview.setMinimumSize(320, 240)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMouseTracking(True)
        self._preview.setStyleSheet("background:#222;")
        self._preview.installEventFilter(self)
        layout.addWidget(self._preview, stretch=1)

        controls = QHBoxLayout()
        self._kind_combo = QComboBox()
        for kind in WARP_KINDS:
            self._kind_combo.addItem(
                lang.get(f"paint_liquify_kind_{kind}", kind.title()),
                userData=kind,
            )
        self._kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        controls.addWidget(QLabel(
            lang.get("paint_liquify_kind", "Brush:"),
        ))
        controls.addWidget(self._kind_combo)

        self._radius_slider = QSlider(Qt.Orientation.Horizontal)
        self._radius_slider.setRange(4, 200)
        self._radius_slider.setValue(self._radius)
        self._radius_slider.valueChanged.connect(self._on_radius_changed)
        controls.addWidget(QLabel(
            lang.get("paint_liquify_radius", "Radius:"),
        ))
        controls.addWidget(self._radius_slider, stretch=1)

        self._strength_slider = QSlider(Qt.Orientation.Horizontal)
        self._strength_slider.setRange(0, 100)
        self._strength_slider.setValue(self._strength_percent)
        self._strength_slider.valueChanged.connect(self._on_strength_changed)
        controls.addWidget(QLabel(
            lang.get("paint_liquify_strength", "Strength:"),
        ))
        controls.addWidget(self._strength_slider, stretch=1)

        layout.addLayout(controls)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Reset,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(
            self._on_reset,
        )
        layout.addWidget(buttons)

        self._refresh_preview()

    # ---- public ----------------------------------------------------------

    def working_image(self) -> np.ndarray:
        """Return the current edited buffer (callers commit on accept)."""
        return self._working

    def kind(self) -> str:
        return self._kind

    def radius(self) -> int:
        return int(self._radius)

    def strength(self) -> float:
        """Engine-space strength in [0, 1] derived from the percent slider."""
        return float(self._strength_percent) / 100.0

    # ---- internals -------------------------------------------------------

    def _on_kind_changed(self, index: int) -> None:
        self._kind = self._kind_combo.itemData(index)

    def _on_radius_changed(self, value: int) -> None:
        self._radius = int(value)

    def _on_strength_changed(self, value: int) -> None:
        self._strength_percent = int(value)

    def _on_reset(self) -> None:
        self._working = self._original.copy()
        self._refresh_preview()

    def eventFilter(self, obj, event):  # pragma: no cover - Qt UI
        if obj is self._preview and isinstance(event, QMouseEvent):
            handled = self._handle_preview_mouse_event(event)
            if handled:
                return True
        return super().eventFilter(obj, event)

    def _handle_preview_mouse_event(self, event) -> bool:  # pragma: no cover - Qt UI
        """Dispatch press / move / release on the preview QLabel.

        Returns ``True`` once it consumed the event; falsy returns let
        the base class handle it (matches QObject.eventFilter contract).
        """
        kind = event.type()
        if kind == QMouseEvent.Type.MouseButtonPress:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            self._last_mouse = event.position()
            self._apply_at(event.position(), drag_dx=0.0, drag_dy=0.0)
            return True
        if kind == QMouseEvent.Type.MouseMove:
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                return False
            if self._last_mouse is not None:
                dx = event.position().x() - self._last_mouse.x()
                dy = event.position().y() - self._last_mouse.y()
                self._apply_at(event.position(), drag_dx=dx, drag_dy=dy)
            self._last_mouse = event.position()
            return True
        if kind == QMouseEvent.Type.MouseButtonRelease:
            self._last_mouse = None
            return True
        return False

    # ---- engine plumbing (testable) -------------------------------------

    def apply_warp_at(
        self,
        image_pos: tuple[float, float],
        *,
        drag_dx: float = 0.0,
        drag_dy: float = 0.0,
    ) -> None:
        """Apply the active brush at ``image_pos`` (image-space pixels).

        Public so callers / tests can drive the dialog without going
        through the QLabel mouse path.
        """
        cx, cy = float(image_pos[0]), float(image_pos[1])
        radius = float(self._radius)
        strength = self.strength()
        if self._kind == "push":
            self._working = push_warp(
                self._working, cx, cy, radius, drag_dx, drag_dy,
                strength=strength,
            )
        elif self._kind == "pinch":
            self._working = pinch_warp(
                self._working, cx, cy, radius, strength=strength,
            )
        elif self._kind == "bloat":
            self._working = bloat_warp(
                self._working, cx, cy, radius, strength=strength,
            )
        elif self._kind == "twirl":
            self._working = twirl_warp(
                self._working, cx, cy, radius,
                angle_deg=DEFAULT_TWIRL_DEGREES * strength,
            )
        self._refresh_preview()

    def _apply_at(  # pragma: no cover - Qt UI
        self,
        screen_pos: QPointF,
        *,
        drag_dx: float,
        drag_dy: float,
    ) -> None:
        """Map a preview-widget click to image coordinates and warp."""
        image_pos = self._preview_to_image(screen_pos)
        if image_pos is None:
            return
        # Scale drag by the same factor used to map the click — the
        # preview may be smaller than the source image.
        scale = self._preview_to_image_scale()
        self.apply_warp_at(
            image_pos,
            drag_dx=drag_dx * scale,
            drag_dy=drag_dy * scale,
        )

    def _preview_to_image_scale(self) -> float:
        h, w = self._working.shape[:2]
        cap = float(PREVIEW_MAX_DIMENSION)
        scale = min(cap / max(1, w), cap / max(1, h), 1.0)
        return 1.0 / scale if scale > 0 else 1.0

    def _preview_to_image(  # pragma: no cover - Qt UI
        self, screen_pos: QPointF,
    ) -> tuple[float, float] | None:
        h, w = self._working.shape[:2]
        if h <= 0 or w <= 0:
            return None
        scale = self._preview_to_image_scale()
        # screen_pos is in preview-widget coords; the image is centred
        # within the preview label.
        preview_w = self._preview.width()
        preview_h = self._preview.height()
        scaled_w = int(round(w / scale))
        scaled_h = int(round(h / scale))
        ox = max(0, (preview_w - scaled_w) // 2)
        oy = max(0, (preview_h - scaled_h) // 2)
        rel_x = screen_pos.x() - ox
        rel_y = screen_pos.y() - oy
        if not 0 <= rel_x < scaled_w or not 0 <= rel_y < scaled_h:
            return None
        return (rel_x * scale, rel_y * scale)

    def _refresh_preview(self) -> None:  # pragma: no cover - Qt UI
        h, w = self._working.shape[:2]
        # Use a contiguous bytes() because some PySide6 builds upload
        # garbage when handed a numpy array directly.
        qimage = QImage(
            bytes(self._working.tobytes()),
            w, h, w * 4, QImage.Format.Format_RGBA8888,
        )
        cap = PREVIEW_MAX_DIMENSION
        if max(h, w) > cap:
            qimage = qimage.scaled(
                cap, cap,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._preview.setPixmap(QPixmap.fromImage(qimage))
