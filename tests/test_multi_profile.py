"""Tests for the multi-profile settings system."""
from __future__ import annotations

import json

import pytest

from Imervue.user_settings.user_setting_dict import (
    DEFAULT_PROFILE,
    create_profile,
    current_profile,
    delete_profile,
    list_profiles,
    read_user_setting,
    rename_profile,
    switch_profile,
    user_setting_dict,
    write_user_setting,
    _profile_state,
)


@pytest.fixture
def fresh_profile_state():
    """Reset _profile_state before each test for predictable starting conditions.

    The autouse ``_isolate_user_settings`` fixture in conftest already
    redirects the on-disk file, but it doesn't touch the module-level
    profile state. We do that here so each test starts from a clean
    "default profile only" baseline.
    """
    _profile_state["current"] = DEFAULT_PROFILE
    _profile_state["available"] = [DEFAULT_PROFILE]
    user_setting_dict.clear()
    user_setting_dict["language"] = "English"
    yield


# ---------------------------------------------------------------------------
# v2 round-trip
# ---------------------------------------------------------------------------


def test_default_profile_round_trip(fresh_profile_state):
    user_setting_dict["language"] = "Japanese"
    path = write_user_setting()
    data = json.loads(path.read_text())
    assert data["current_profile"] == DEFAULT_PROFILE
    assert "default" in data["profiles"]
    assert data["profiles"]["default"]["language"] == "Japanese"


def test_round_trip_through_read(fresh_profile_state):
    user_setting_dict["language"] = "Japanese"
    write_user_setting()

    user_setting_dict.clear()
    read_user_setting()
    assert user_setting_dict["language"] == "Japanese"
    assert current_profile() == DEFAULT_PROFILE


# ---------------------------------------------------------------------------
# v1 → v2 migration
# ---------------------------------------------------------------------------


def test_legacy_v1_file_migrates_on_read(fresh_profile_state, tmp_path, monkeypatch):
    from Imervue.user_settings import user_setting_dict as mod

    legacy_payload = {
        "language": "Japanese",
        "user_recent_folders": ["/legacy/path"],
    }
    legacy_path = tmp_path / "user_setting.json"
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")
    monkeypatch.setattr(mod, "_user_settings_path", lambda: legacy_path)

    read_user_setting()
    assert current_profile() == DEFAULT_PROFILE
    assert list_profiles() == [DEFAULT_PROFILE]
    assert user_setting_dict["language"] == "Japanese"
    assert user_setting_dict["user_recent_folders"] == ["/legacy/path"]


def test_subsequent_write_emits_v2_format(fresh_profile_state, tmp_path, monkeypatch):
    """After a legacy read, the next write should produce v2 on disk."""
    from Imervue.user_settings import user_setting_dict as mod

    legacy = tmp_path / "user_setting.json"
    legacy.write_text(json.dumps({"language": "Japanese"}), encoding="utf-8")
    monkeypatch.setattr(mod, "_user_settings_path", lambda: legacy)

    read_user_setting()
    write_user_setting()

    data = json.loads(legacy.read_text())
    assert "current_profile" in data
    assert "profiles" in data


# ---------------------------------------------------------------------------
# create_profile
# ---------------------------------------------------------------------------


def test_create_profile_appends_to_list(fresh_profile_state):
    assert create_profile("client_a") is True
    assert "client_a" in list_profiles()


def test_create_profile_rejects_empty_name(fresh_profile_state):
    assert create_profile("") is False
    assert create_profile("   ") is False


def test_create_profile_rejects_duplicate(fresh_profile_state):
    create_profile("client_a")
    assert create_profile("client_a") is False


def test_create_profile_blank_starts_empty(fresh_profile_state):
    user_setting_dict["language"] = "Japanese"
    create_profile("client_a")
    switch_profile("client_a")
    # Default-empty profile means the language key was not copied
    assert "language" not in user_setting_dict


def test_create_profile_copy_from_current(fresh_profile_state):
    user_setting_dict["language"] = "Japanese"
    create_profile("clone", copy_from_current=True)
    switch_profile("clone")
    assert user_setting_dict["language"] == "Japanese"


# ---------------------------------------------------------------------------
# switch_profile
# ---------------------------------------------------------------------------


def test_switch_profile_swaps_in_memory_dict(fresh_profile_state):
    user_setting_dict["language"] = "Japanese"
    create_profile("client_b")
    switch_profile("client_b")

    user_setting_dict["language"] = "Korean"
    switch_profile(DEFAULT_PROFILE)
    assert user_setting_dict["language"] == "Japanese"


def test_switch_profile_unknown_returns_false(fresh_profile_state):
    assert switch_profile("does_not_exist") is False


def test_switch_to_current_is_noop(fresh_profile_state):
    assert switch_profile(DEFAULT_PROFILE) is True
    assert current_profile() == DEFAULT_PROFILE


def test_switch_persists_each_profile_independently(fresh_profile_state):
    user_setting_dict["language"] = "Japanese"
    create_profile("client_a")
    switch_profile("client_a")
    user_setting_dict["language"] = "Korean"

    # Round-trip through disk
    write_user_setting()
    user_setting_dict.clear()
    _profile_state["current"] = DEFAULT_PROFILE
    _profile_state["available"] = [DEFAULT_PROFILE]
    read_user_setting()

    # Re-loading should restore the active profile (client_a) with Korean
    assert current_profile() == "client_a"
    assert user_setting_dict["language"] == "Korean"

    switch_profile(DEFAULT_PROFILE)
    assert user_setting_dict["language"] == "Japanese"


# ---------------------------------------------------------------------------
# delete_profile
# ---------------------------------------------------------------------------


def test_delete_default_profile_rejected(fresh_profile_state):
    assert delete_profile(DEFAULT_PROFILE) is False
    assert DEFAULT_PROFILE in list_profiles()


def test_delete_active_profile_rejected(fresh_profile_state):
    create_profile("alt")
    switch_profile("alt")
    assert delete_profile("alt") is False
    assert "alt" in list_profiles()


def test_delete_inactive_profile_succeeds(fresh_profile_state):
    create_profile("alt")
    assert delete_profile("alt") is True
    assert "alt" not in list_profiles()


def test_delete_unknown_profile_returns_false(fresh_profile_state):
    assert delete_profile("nothing_here") is False


# ---------------------------------------------------------------------------
# rename_profile
# ---------------------------------------------------------------------------


def test_rename_profile_updates_list(fresh_profile_state):
    create_profile("alt")
    assert rename_profile("alt", "renamed") is True
    assert "renamed" in list_profiles()
    assert "alt" not in list_profiles()


def test_rename_active_profile_updates_current(fresh_profile_state):
    create_profile("alt")
    switch_profile("alt")
    rename_profile("alt", "alt2")
    assert current_profile() == "alt2"


def test_rename_to_existing_name_fails(fresh_profile_state):
    create_profile("alt")
    create_profile("other")
    assert rename_profile("alt", "other") is False


def test_rename_unknown_profile_fails(fresh_profile_state):
    assert rename_profile("ghost", "phantom") is False


def test_rename_to_empty_name_fails(fresh_profile_state):
    create_profile("alt")
    assert rename_profile("alt", "  ") is False


# ---------------------------------------------------------------------------
# Dialog smoke (Qt)
# ---------------------------------------------------------------------------


def test_dialog_lists_all_profiles(qapp, fresh_profile_state):
    from Imervue.gui.profiles_dialog import ProfilesDialog
    create_profile("alt")
    dlg = ProfilesDialog()
    names = [
        dlg._list.item(i).data(0x0100)  # Qt.ItemDataRole.UserRole
        for i in range(dlg._list.count())
    ]
    assert DEFAULT_PROFILE in names
    assert "alt" in names
