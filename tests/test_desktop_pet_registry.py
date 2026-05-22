"""Tests for the :class:`PetRegistry`.

Lifecycle checks (spawn / despawn idempotence, signal emissions)
plus a settings-isolation smoke test that two spawned pets really
write to separate slots — the whole point of the registry.
"""
from __future__ import annotations

import pytest

from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.pet_registry import PetRegistry

from _qt_skip import pytestmark  # noqa: E402,F401


def test_primary_spawns_default_pet(qapp):
    reg = PetRegistry()
    try:
        primary = reg.primary()
        assert primary is not None
        assert primary.pet_id() == pet_settings.DEFAULT_PET_ID
        assert pet_settings.DEFAULT_PET_ID in reg
    finally:
        reg.despawn_all()


def test_spawn_is_idempotent(qapp):
    """Two spawns of the same id must return the same window —
    parallel callers (tray + workspace) mustn't end up with
    duplicate pets pointing at the same settings slot."""
    reg = PetRegistry()
    try:
        a = reg.spawn("twin")
        b = reg.spawn("twin")
        assert a is b
        assert len(reg) == 1
    finally:
        reg.despawn_all()


def test_spawn_signal_fires_once_per_create(qapp):
    """``pet_spawned`` fires on real creation, not on idempotent
    no-op spawns."""
    reg = PetRegistry()
    fired: list[str] = []
    reg.pet_spawned.connect(fired.append)
    try:
        reg.spawn("first")
        reg.spawn("first")   # idempotent
        reg.spawn("second")
        assert fired == ["first", "second"]
    finally:
        reg.despawn_all()


def test_despawn_removes_from_registry(qapp):
    reg = PetRegistry()
    try:
        reg.spawn("buddy")
        assert "buddy" in reg
        assert reg.despawn("buddy") is True
        assert "buddy" not in reg
        # Re-despawn is False (nothing to remove) but doesn't raise.
        assert reg.despawn("buddy") is False
    finally:
        reg.despawn_all()


def test_despawn_signal_fires(qapp):
    reg = PetRegistry()
    fired: list[str] = []
    reg.pet_despawned.connect(fired.append)
    try:
        reg.spawn("goner")
        reg.despawn("goner")
        assert fired == ["goner"]
    finally:
        reg.despawn_all()


def test_spawn_with_empty_id_rejected(qapp):
    """Blank pet_id is meaningless — it would shadow the primary
    or end up as a key collision."""
    reg = PetRegistry()
    try:
        with pytest.raises(ValueError):
            reg.spawn("")
    finally:
        reg.despawn_all()


def test_extras_get_a_settings_slot_on_spawn(qapp):
    """Spawning a brand-new extra must create its settings slot so
    subsequent ``_persist`` calls land somewhere. Otherwise the
    first window-state change would silently drop on the floor."""
    reg = PetRegistry()
    try:
        reg.spawn("fresh-extra")
        assert "fresh-extra" in pet_settings.list_pet_ids()
    finally:
        reg.despawn_all()


def test_pet_ids_primary_first(qapp):
    """Even if extras were spawned first, primary leads the order
    when present. UI consumers iterate this for the workspace's
    pet list."""
    reg = PetRegistry()
    try:
        reg.spawn("extra_a")
        reg.spawn("extra_b")
        reg.primary()
        ids = reg.pet_ids()
        assert ids[0] == pet_settings.DEFAULT_PET_ID
        assert set(ids[1:]) == {"extra_a", "extra_b"}
    finally:
        reg.despawn_all()


def test_two_pets_write_to_isolated_slots(qapp):
    """Settings isolation smoke test — the whole point of the
    refactor. Toggle a flag on one pet, the other's stays put."""
    reg = PetRegistry()
    try:
        a = reg.spawn("isolation_a")
        b = reg.spawn("isolation_b")
        a.set_click_through(True)
        b.set_click_through(False)
        a_settings = pet_settings.load("isolation_a")
        b_settings = pet_settings.load("isolation_b")
        assert a_settings["click_through"] is True
        assert b_settings["click_through"] is False
    finally:
        reg.despawn_all()


def test_iter_yields_live_windows(qapp):
    reg = PetRegistry()
    try:
        reg.spawn("iter_a")
        reg.spawn("iter_b")
        windows = list(reg)
        assert len(windows) == 2
        assert all(w.pet_id() in ("iter_a", "iter_b") for w in windows)
    finally:
        reg.despawn_all()


def test_despawn_all_clears_registry(qapp):
    reg = PetRegistry()
    reg.spawn("a")
    reg.spawn("b")
    reg.spawn("c")
    reg.despawn_all()
    assert len(reg) == 0
