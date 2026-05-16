"""Tray-icon plumbing.

Constructing :class:`QSystemTrayIcon` in this test environment
segfaults the GL test runner (no real tray daemon, fallback icon
draws against a missing display style cache). Restrict the tests
to the static availability check and the import surface — the
behavioural sync paths are tested through the workspace, which
mocks the tray with a sentinel object.
"""
from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon

from Imervue.desktop_pet.tray_icon import PetTrayIcon


def test_is_available_matches_qt_runtime(qapp):
    """The static availability check has to round-trip whatever
    Qt's own ``isSystemTrayAvailable`` decides — we're a thin
    wrapper, not a substitute. Main-window code branches on this
    helper so a divergent answer would silently skip tray
    construction even when the platform supports it."""
    assert PetTrayIcon.is_available() == bool(
        QSystemTrayIcon.isSystemTrayAvailable(),
    )


def test_tray_icon_class_importable():
    """Smoke test — the class must be importable from the
    package's public surface so the main-window wire-up doesn't
    crash on launch."""
    from Imervue.desktop_pet import PetTrayIcon as PublicAlias
    assert PublicAlias is PetTrayIcon
