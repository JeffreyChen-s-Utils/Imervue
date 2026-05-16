"""Desktop-pet overlay window.

A top-level frameless / always-on-top / transparent-background
window that hosts a :class:`PuppetCanvas` in pet mode. Drag the
puppet's body to move the window; release near a screen edge to
snap onto it. Click-through mode can be toggled to let the user
keep interacting with whatever's behind the pet.

The window owns no GL state of its own — it just configures the
top-level window flags / attributes and forwards driver toggles
into the embedded canvas. Live drivers (idle, blink, mic, webcam,
drag-track) construct lazily on first enable so a hidden pet
window pays zero cost for unused features.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget

from Imervue.desktop_pet.edge_snap import (
    DEFAULT_SNAP_THRESHOLD,
    Rect,
    snap_to_screen_edges,
)
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document_io import load_puppet
from Imervue.puppet.idle_driver import IdleDriver
from Imervue.puppet.idle_motion_cycler import IdleMotionCycler
from Imervue.puppet.input_engine import InputEngine
from Imervue.puppet.motion_player import MotionPlayer

if TYPE_CHECKING:
    from Imervue.puppet.document import PuppetDocument
    from Imervue.puppet.webcam_tracker import WebcamTracker

logger = logging.getLogger("Imervue.desktop_pet.pet_window")

DEFAULT_PET_SIZE: tuple[int, int] = (320, 480)
"""Initial overlay size, in screen pixels. ``PuppetCanvas``'s fit
logic scales the puppet to whatever the widget allocates, so the
tuple just picks a sensible vertically-tall slot — most rigged
characters end up ~3:4 aspect, taller than wide."""


class PetWindow(QWidget):
    """The on-desktop puppet overlay.

    Constructed once per session; show / hide via :meth:`show` /
    :meth:`hide` rather than recreating, so the GL context (and
    every uploaded texture / VBO) sticks around between toggles.
    """

    visibility_changed = Signal(bool)
    """Emitted after :meth:`show` / :meth:`hide` so the workspace
    can keep its check-state in sync."""

    moved = Signal(int, int)
    """``(x, y)`` after a drag release lands on a final position
    (post edge-snap). Lets the workspace persist the last pet
    location to user settings."""

    def __init__(self) -> None:
        super().__init__(None)
        self._configure_window_flags(click_through=False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.resize(*DEFAULT_PET_SIZE)

        # The puppet canvas runs in pet mode: transparent clear, no
        # checker backdrop, no selection overlay. Wrap it in a tiny
        # layout so the canvas fills the entire window.
        self._canvas = PuppetCanvas(self, pet_mode=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        # Click-through state — when True the pet ignores all mouse
        # events and the desktop behind it stays interactive.
        self._click_through: bool = False
        # Drag-to-move state. The pet canvas captures the press; we
        # store the cursor-to-window offset and apply it on every
        # subsequent move event until release.
        self._dragging: bool = False
        self._drag_offset: QPoint = QPoint(0, 0)
        self._snap_threshold: int = DEFAULT_SNAP_THRESHOLD
        self._install_drag_filter()

        # Live drivers — the puppet workspace uses one bundled
        # ``InputEngine`` for the drag-track / blink / mic-lipsync
        # trio and separate ``IdleDriver`` + ``IdleMotionCycler``
        # for the idle-loop pair. Same pattern here so the desktop
        # pet inherits every fix / driver added to the Puppet tab.
        self._input_engine = InputEngine(self._canvas, parent=self)
        self._idle_driver: IdleDriver | None = None
        self._webcam_tracker: WebcamTracker | None = None

        # Motion-cycler needs a MotionPlayer; one player serves
        # both the random idle pick and any manually-triggered
        # motion the user might wire later.
        self._motion_player = MotionPlayer(self._canvas)
        self._idle_cycler: IdleMotionCycler | None = None

        # Repaint the canvas every ~33 ms so physics / motion
        # playback advances even when no mouse / keyboard event is
        # firing. Same cadence the Puppet tab uses.
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._canvas.update)
        self._tick.start()

    # ---- window flags + visibility -----------------------------

    def _configure_window_flags(self, *, click_through: bool) -> None:
        """Apply the always-on-top / frameless / tool flag combo,
        optionally with ``WindowTransparentForInput`` so clicks
        pass through to whatever app sits behind the pet."""
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool   # no taskbar entry, no Alt-Tab
        )
        if click_through:
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)

    def set_click_through(self, enabled: bool) -> None:
        """Toggle the OS-level click-through state. Reapplying the
        window flags forces a re-show on Qt; we preserve the
        current geometry across the cycle so the pet doesn't snap
        back to ``(0, 0)`` between toggles."""
        enabled = bool(enabled)
        if enabled == self._click_through:
            return
        self._click_through = enabled
        geom = self.geometry()
        was_visible = self.isVisible()
        self._configure_window_flags(click_through=enabled)
        self.setGeometry(geom)
        if was_visible:
            self.show()

    def click_through_enabled(self) -> bool:
        return self._click_through

    def showEvent(self, event) -> None:   # pragma: no cover - Qt UI
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:   # pragma: no cover - Qt UI
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    # ---- document / rig ----------------------------------------

    def load_puppet_file(self, path: str | Path) -> bool:
        """Load a ``.puppet`` zip and hand its document to the
        canvas. Returns ``True`` on success, ``False`` if the file
        couldn't be parsed (the workspace surfaces the error)."""
        try:
            document = load_puppet(path)
        except Exception as exc:   # noqa: BLE001 - load_puppet has many failure modes
            logger.warning("desktop-pet failed to load %s: %s", path, exc)
            return False
        self.load_document(document)
        return True

    def load_document(self, document: PuppetDocument | None) -> None:
        """Bind ``document`` directly — used when the workspace
        forwards the rig the Puppet tab is editing live."""
        self._canvas.load_document(document)

    def document(self) -> PuppetDocument | None:
        return self._canvas.document()

    def canvas(self) -> PuppetCanvas:
        """Test / advanced caller hook — exposes the embedded
        canvas so the workspace can wire dock controls into it the
        same way the Puppet tab does."""
        return self._canvas

    # ---- drag-to-move ------------------------------------------

    def _install_drag_filter(self) -> None:
        """The canvas swallows mouse events for pan / zoom in its
        normal mode. In pet mode it doesn't, so we just install an
        event filter that watches the press / move / release trio."""
        self._canvas.installEventFilter(self)

    def eventFilter(self, obj, event):   # pragma: no cover - Qt UI
        if obj is self._canvas:
            etype = event.type()
            if etype == event.Type.MouseButtonPress:
                self._on_drag_press(event)
            elif etype == event.Type.MouseMove:
                self._on_drag_move(event)
            elif etype == event.Type.MouseButtonRelease:
                self._on_drag_release(event)
        return super().eventFilter(obj, event)

    def _on_drag_press(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if event.button() != Qt.MouseButton.LeftButton or self._click_through:
            return
        self._dragging = True
        self._drag_offset = event.globalPosition().toPoint() - self.pos()
        self._canvas.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _on_drag_move(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if not self._dragging:
            return
        new_pos = event.globalPosition().toPoint() - self._drag_offset
        self.move(new_pos)

    def _on_drag_release(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if event.button() != Qt.MouseButton.LeftButton or not self._dragging:
            return
        self._dragging = False
        self._canvas.unsetCursor()
        self._apply_edge_snap()
        pos = self.pos()
        self.moved.emit(pos.x(), pos.y())

    def _apply_edge_snap(self) -> None:   # pragma: no cover - Qt geometry
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        window_rect = Rect(self.x(), self.y(), self.width(), self.height())
        screen_rect = Rect(avail.x(), avail.y(), avail.width(), avail.height())
        new_x, new_y = snap_to_screen_edges(
            window_rect, screen_rect, threshold=self._snap_threshold,
        )
        if (new_x, new_y) != (self.x(), self.y()):
            self.move(new_x, new_y)

    # ---- live drivers ------------------------------------------

    def set_auto_blink_enabled(self, enabled: bool) -> None:
        """Toggle the auto-blink cosine cycle on the bundled
        :class:`InputEngine`."""
        self._input_engine.set_blink_enabled(bool(enabled))

    def set_auto_idle_enabled(self, enabled: bool) -> None:
        """Breath + drift on standard params. Lazy-creates the
        ``IdleDriver`` on first enable so a never-idling pet pays
        zero timer cost."""
        if enabled:
            if self._idle_driver is None:
                self._idle_driver = IdleDriver(self._canvas, parent=self)
            self._idle_driver.set_enabled(True)
        elif self._idle_driver is not None:
            self._idle_driver.set_enabled(False)

    def set_idle_motion_enabled(self, enabled: bool) -> None:
        """Random cycling through ``Idle`` group motions."""
        if enabled:
            if self._idle_cycler is None:
                self._idle_cycler = IdleMotionCycler(
                    self._motion_player, self._canvas, parent=self,
                )
            self._idle_cycler.set_enabled(True)
        elif self._idle_cycler is not None:
            self._idle_cycler.set_enabled(False)

    def set_mic_lipsync_enabled(self, enabled: bool) -> bool:
        """Returns whether the driver actually started — mic lip-
        sync needs ``sounddevice``, which isn't installed by
        default."""
        return bool(self._input_engine.set_lipsync_enabled(bool(enabled)))

    def set_webcam_tracking_enabled(self, enabled: bool) -> bool:
        """Lazy-import the webcam tracker so the desktop-pet
        package doesn't pay for opencv-python / mediapipe imports
        when the user never enables face tracking."""
        if enabled:
            if self._webcam_tracker is None:
                from Imervue.puppet.webcam_tracker import WebcamTracker
                self._webcam_tracker = WebcamTracker(self._canvas, parent=self)
            return bool(self._webcam_tracker.set_enabled(True))
        if self._webcam_tracker is not None:
            self._webcam_tracker.set_enabled(False)
        return True

    def set_drag_track_enabled(self, enabled: bool) -> None:
        """Head-follows-cursor driver. ``InputEngine.push_cursor``
        is fed from the canvas mouse-move below, so the pet only
        looks at the mouse while it's over the window. Matches
        Puppet-tab semantics."""
        self._input_engine.set_drag_enabled(bool(enabled))

    # ---- size presets ------------------------------------------

    def set_size_preset(self, preset: str) -> None:
        """Resize the window to one of the named slots. Centred on
        the current position so the pet doesn't jump across the
        screen when the user picks a different size."""
        sizes = {
            "small": (200, 300),
            "medium": (320, 480),
            "large": (480, 720),
        }
        size = sizes.get(preset)
        if size is None:
            return
        old_centre = self.geometry().center()
        self.resize(*size)
        new_geom = self.geometry()
        new_geom.moveCenter(old_centre)
        self.setGeometry(new_geom)
        self._apply_edge_snap()
