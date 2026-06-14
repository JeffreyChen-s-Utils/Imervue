"""Window-placement helpers for the desktop-pet overlay.

Edge-snap, multi-monitor position restore, default-corner parking and
the Qt-screen snapshotting these need. Pulled out of
:class:`~Imervue.desktop_pet.pet_window.PetWindow` so the window does
not also own all the geometry maths; the pure decision logic already
lives in :mod:`Imervue.desktop_pet.edge_snap` and these functions are
the thin Qt-geometry glue that feeds it.

Each function takes the ``window`` it operates on rather than being a
method, keeping the window class focused on lifecycle / coordination.
The Qt-geometry calls can't run headless, so the glue is excluded from
coverage; the decision logic it delegates to is unit-tested in
``test_desktop_pet_edge_snap``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QGuiApplication

from Imervue.desktop_pet.edge_snap import (
    Rect,
    ScreenInfo,
    clamp_window_to_screen,
    resolve_screen,
    snap_to_screen_edges,
)

if TYPE_CHECKING:
    from Imervue.desktop_pet.pet_window import PetWindow

DEFAULT_CORNER_MARGIN = 16
"""Inset (px) from the screen's bottom-right when parking a fresh pet."""

DEFAULT_POSITION = [-1, -1]
"""Sentinel persisted position meaning "use the default corner"."""

POSITION_PAIR_LEN = 2


def screen_info(screen) -> ScreenInfo:   # pragma: no cover - Qt geometry
    """Snapshot a Qt :class:`QScreen` into a pure :class:`ScreenInfo`.

    Uses ``availableGeometry`` (excludes taskbar / menubar) so the pet
    snaps to the visible work area rather than into the taskbar — the
    same convention Windows uses for "Snap to right edge".
    """
    avail = screen.availableGeometry()
    return ScreenInfo(
        name=screen.name(),
        available=Rect(avail.x(), avail.y(), avail.width(), avail.height()),
    )


def collect_screens() -> list[ScreenInfo]:   # pragma: no cover - Qt geometry
    """Snapshot Qt's screen list as pure ``ScreenInfo`` records so the
    position-restoration helpers stay testable without a
    QGuiApplication."""
    screens: list[ScreenInfo] = []
    primary = QGuiApplication.primaryScreen()
    if primary is not None:
        screens.append(screen_info(primary))
    for screen in QGuiApplication.screens():
        if screen is primary:
            continue
        screens.append(screen_info(screen))
    return screens


def current_screen_name(window: PetWindow) -> str:   # pragma: no cover - Qt geometry
    """Name of the screen the pet's top-left currently sits on. Used
    when persisting position so the next launch puts the pet back on
    the same physical monitor."""
    screen = (
        QGuiApplication.screenAt(window.pos())
        or QGuiApplication.primaryScreen()
    )
    return screen.name() if screen is not None else ""


def screen_rect_for_detector(window: PetWindow):   # pragma: no cover - Qt geometry
    """Full geometry of the pet's current screen, for the fullscreen
    detector's per-monitor poll."""
    screen = (
        QGuiApplication.screenAt(window.pos())
        or QGuiApplication.primaryScreen()
    )
    return screen.geometry() if screen is not None else None


def apply_edge_snap(window: PetWindow) -> None:   # pragma: no cover - Qt geometry
    """Snap the pet to the nearest screen edge within its threshold."""
    screen = (
        QGuiApplication.screenAt(window.pos())
        or QGuiApplication.primaryScreen()
    )
    if screen is None:
        return
    avail = screen.availableGeometry()
    window_rect = Rect(window.x(), window.y(), window.width(), window.height())
    screen_rect = Rect(avail.x(), avail.y(), avail.width(), avail.height())
    new_x, new_y = snap_to_screen_edges(
        window_rect, screen_rect, threshold=window.snap_threshold(),
    )
    if (new_x, new_y) != (window.x(), window.y()):
        window.move(new_x, new_y)


def _preferred_screen(window: PetWindow):   # pragma: no cover - Qt geometry
    return resolve_screen(
        str(window.setting("screen_name", "") or ""), collect_screens(),
    )


def move_to_default_corner(window: PetWindow) -> None:   # pragma: no cover - Qt geometry
    """Park the pet at the bottom-right of the preferred screen (named
    in settings, falling back to primary) — the canonical desktop-pet
    spot on a fresh install."""
    screen = _preferred_screen(window)
    if screen is None:
        return
    avail = screen.available
    x = avail.right - window.width() - DEFAULT_CORNER_MARGIN
    y = avail.bottom - window.height() - DEFAULT_CORNER_MARGIN
    window.move(x, y)


def restore_position(window: PetWindow) -> None:   # pragma: no cover - Qt geometry
    """Restore the saved ``(x, y)`` on the saved screen.

    Two-stage lookup so multi-monitor users get sensible behaviour
    across hardware changes: :func:`resolve_screen` picks the monitor
    matching the persisted name, then :func:`clamp_window_to_screen`
    ensures the saved corner still fits inside it. Falls back to the
    default corner when the saved position is absent / sentinel / the
    named monitor is gone.
    """
    pos = window.setting("position", DEFAULT_POSITION)
    if not (isinstance(pos, list) and len(pos) == POSITION_PAIR_LEN):
        move_to_default_corner(window)
        return
    x, y = int(pos[0]), int(pos[1])
    if x == -1 and y == -1:
        move_to_default_corner(window)
        return
    screen = _preferred_screen(window)
    if screen is None:
        move_to_default_corner(window)
        return
    rect = Rect(x, y, window.width(), window.height())
    new_x, new_y = clamp_window_to_screen(rect, screen)
    window.move(new_x, new_y)
