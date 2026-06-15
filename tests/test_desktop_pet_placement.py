"""Unit tests for the desktop-pet placement decision logic.

The Qt-geometry glue can't run headless, but ``restore_position`` and
``move_to_default_corner`` contain the branch logic that matters
(sentinel / malformed position → default corner; resolved screen →
clamp). Those are exercised here against a fake window with the screen
lookup monkeypatched, so no QGuiApplication is needed.
"""
from __future__ import annotations

from Imervue.desktop_pet import pet_placement
from Imervue.desktop_pet.edge_snap import Rect, ScreenInfo


class _FakeWindow:
    def __init__(self, settings: dict) -> None:
        self._settings = settings
        self.moved_to: tuple[int, int] | None = None

    def setting(self, key: str, default: object) -> object:
        return self._settings.get(key, default)

    def width(self) -> int:
        return 100

    def height(self) -> int:
        return 200

    def move(self, x: int, y: int) -> None:
        self.moved_to = (x, y)


_SCREEN = ScreenInfo(name="DISPLAY1", available=Rect(0, 0, 1920, 1080))


def _patch_screen(monkeypatch, screen):
    monkeypatch.setattr(pet_placement, "collect_screens", lambda: [screen])
    monkeypatch.setattr(
        pet_placement, "resolve_screen", lambda name, screens: screen,
    )


def test_restore_default_corner_on_sentinel(monkeypatch):
    _patch_screen(monkeypatch, _SCREEN)
    win = _FakeWindow({"position": [-1, -1], "screen_name": "DISPLAY1"})
    pet_placement.restore_position(win)
    # bottom-right minus margin: x = 1920-100-16, y = 1080-200-16
    assert win.moved_to == (1804, 864)


def test_restore_default_corner_on_malformed_position(monkeypatch):
    _patch_screen(monkeypatch, _SCREEN)
    win = _FakeWindow({"position": "bogus"})
    pet_placement.restore_position(win)
    assert win.moved_to == (1804, 864)


def test_restore_clamps_saved_position(monkeypatch):
    _patch_screen(monkeypatch, _SCREEN)
    win = _FakeWindow({"position": [500, 400], "screen_name": "DISPLAY1"})
    pet_placement.restore_position(win)
    # Inside the screen → unchanged.
    assert win.moved_to == (500, 400)


def test_restore_clamps_offscreen_position(monkeypatch):
    _patch_screen(monkeypatch, _SCREEN)
    win = _FakeWindow({"position": [5000, 5000], "screen_name": "DISPLAY1"})
    pet_placement.restore_position(win)
    # Pushed back inside: max x = 1920-100, max y = 1080-200.
    assert win.moved_to == (1820, 880)


def test_restore_no_screen_falls_back_without_move(monkeypatch):
    monkeypatch.setattr(pet_placement, "collect_screens", lambda: [])
    monkeypatch.setattr(
        pet_placement, "resolve_screen", lambda name, screens: None,
    )
    win = _FakeWindow({"position": [10, 10]})
    pet_placement.restore_position(win)
    # resolve_screen None → default corner, which also finds no screen.
    assert win.moved_to is None


def test_default_corner_no_screen_is_noop(monkeypatch):
    monkeypatch.setattr(pet_placement, "collect_screens", lambda: [])
    monkeypatch.setattr(
        pet_placement, "resolve_screen", lambda name, screens: None,
    )
    win = _FakeWindow({})
    pet_placement.move_to_default_corner(win)
    assert win.moved_to is None
