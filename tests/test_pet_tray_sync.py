"""External pet visibility / click-through changes must keep the tray in sync.

sync_visibility / sync_click_through existed but were never called, so the tray's
checkable menu state went stale and its next click toggled from the wrong value.
Driven on the workspace handlers unbound with fakes -- no widget constructed.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.desktop_pet.pet_workspace import PetWorkspace


def _show_check():
    return SimpleNamespace(blockSignals=lambda _b: None, setChecked=lambda _v: None)


def test_visibility_change_syncs_the_tray():
    synced: list = []
    fake = SimpleNamespace(
        _show_check=_show_check(),
        _tray=SimpleNamespace(sync_visibility=synced.append),
    )
    PetWorkspace._on_pet_visibility_changed(fake, True)
    assert synced == [True]


def test_visibility_change_is_safe_without_a_tray():
    fake = SimpleNamespace(_show_check=_show_check(), _tray=None)
    PetWorkspace._on_pet_visibility_changed(fake, False)   # must not raise


def test_click_through_toggle_syncs_the_tray():
    synced: list = []
    fake = SimpleNamespace(
        _tray=SimpleNamespace(sync_click_through=synced.append),
        _ensure_pet_window=lambda: SimpleNamespace(set_click_through=lambda _v: None),
    )
    PetWorkspace._on_click_through_toggled(fake, True)
    assert synced == [True]


def test_click_through_toggle_is_safe_without_a_tray():
    fake = SimpleNamespace(
        _tray=None,
        _ensure_pet_window=lambda: SimpleNamespace(set_click_through=lambda _v: None),
    )
    PetWorkspace._on_click_through_toggled(fake, True)   # must not raise
