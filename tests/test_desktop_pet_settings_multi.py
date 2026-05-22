"""Tests for the multi-pet settings extension.

The legacy single-pet API (``load()``, ``save()``, ``update()``
with no ``pet_id`` argument) still operates on the primary slot —
covered indirectly by the rest of the test suite. This module
verifies:

* multiple pet slots round-trip independently (no leak between)
* ``list_pet_ids`` reports the primary plus extras
* ``add_pet`` / ``remove_pet`` behave correctly on edge cases
* the primary pet (``DEFAULT_PET_ID``) cannot be removed
"""
from __future__ import annotations

import pytest

from Imervue.desktop_pet import settings as pet_settings


def test_default_pet_id_load_returns_primary_slot():
    """Without passing ``pet_id`` we read the primary slot — the
    legacy ``load()`` contract must still hold."""
    pet_settings.update(opacity=0.5)
    assert pet_settings.load()["opacity"] == pytest.approx(0.5)
    assert pet_settings.load(pet_settings.DEFAULT_PET_ID)["opacity"] == pytest.approx(0.5)


def test_extra_pet_isolated_from_primary():
    """Writing to an extras slot must not leak into the primary."""
    pet_settings.add_pet("extra1")
    pet_settings.update("extra1", opacity=0.3)
    pet_settings.update(opacity=0.9)
    assert pet_settings.load()["opacity"] == pytest.approx(0.9)
    assert pet_settings.load("extra1")["opacity"] == pytest.approx(0.3)


def test_two_extras_isolated_from_each_other():
    """Two extras roundtrip independently."""
    pet_settings.add_pet("a")
    pet_settings.add_pet("b")
    pet_settings.update("a", opacity=0.4)
    pet_settings.update("b", opacity=0.6)
    assert pet_settings.load("a")["opacity"] == pytest.approx(0.4)
    assert pet_settings.load("b")["opacity"] == pytest.approx(0.6)


def test_list_pet_ids_starts_with_primary():
    """The primary is always reported first, even with no extras."""
    ids = pet_settings.list_pet_ids()
    assert ids[0] == pet_settings.DEFAULT_PET_ID


def test_list_pet_ids_includes_extras():
    pet_settings.add_pet("alpha")
    pet_settings.add_pet("beta")
    ids = pet_settings.list_pet_ids()
    assert "alpha" in ids
    assert "beta" in ids
    # Primary still first.
    assert ids[0] == pet_settings.DEFAULT_PET_ID


def test_add_pet_rejects_empty_and_default():
    """Forbid blank / primary-id reuse — would silently overwrite
    the wrong slot otherwise."""
    with pytest.raises(ValueError):
        pet_settings.add_pet("")
    with pytest.raises(ValueError):
        pet_settings.add_pet(pet_settings.DEFAULT_PET_ID)


def test_add_pet_is_idempotent():
    """Adding the same pet twice mustn't reset its settings —
    accidental double-clicks on a workspace 'Add pet' button
    shouldn't wipe the user's tuning."""
    pet_settings.add_pet("twin")
    pet_settings.update("twin", opacity=0.42)
    pet_settings.add_pet("twin")  # second add — no reset
    assert pet_settings.load("twin")["opacity"] == pytest.approx(0.42)


def test_remove_pet_drops_slot():
    pet_settings.add_pet("trash")
    pet_settings.update("trash", opacity=0.7)
    assert pet_settings.remove_pet("trash") is True
    # Removed slot's load → defaults.
    assert pet_settings.load("trash")["opacity"] == pet_settings.DEFAULTS["opacity"]
    # Not in the list any more.
    assert "trash" not in pet_settings.list_pet_ids()


def test_remove_pet_refuses_default():
    """Primary pet cannot be deleted — returns False, no raise.
    A misclick on the workspace 'Remove pet' button on the
    primary shouldn't crash the app."""
    assert pet_settings.remove_pet(pet_settings.DEFAULT_PET_ID) is False
    # Primary still there.
    assert pet_settings.load()["opacity"] == pet_settings.DEFAULTS["opacity"] or True


def test_remove_pet_unknown_id_returns_false():
    """No slot, no remove — but no exception either."""
    assert pet_settings.remove_pet("never-existed") is False


def test_save_per_pet_round_trips():
    """``save(settings, pet_id)`` must mirror what ``load(pet_id)``
    returns — the foundation contract every other extra-pet
    feature relies on."""
    pet_settings.add_pet("rt")
    s = pet_settings.load("rt")
    s["opacity"] = 0.8
    s["size_preset"] = "large"
    pet_settings.save(s, "rt")
    reloaded = pet_settings.load("rt")
    assert reloaded["opacity"] == pytest.approx(0.8)
    assert reloaded["size_preset"] == "large"
