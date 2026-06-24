"""Tests for session validation / migration / merge helpers."""
from __future__ import annotations

from Imervue.sessions.session_manager import SESSION_VERSION
from Imervue.sessions.session_migration import (
    merge_sessions,
    migrate_session,
    validate_session,
)


def _valid_session() -> dict:
    return {
        "version": SESSION_VERSION,
        "tabs": [{"path": "/a.png", "title": "a"}],
        "active_tab": 0,
        "current_image": "/a.png",
        "selection": ["/a.png"],
        "tile_grid_mode": False,
        "folder": "/",
    }


# ---------------------------------------------------------------------------
# validate_session
# ---------------------------------------------------------------------------


def test_valid_session_has_no_errors():
    assert validate_session(_valid_session()) == []


def test_non_dict_is_rejected():
    assert validate_session(["not", "a", "dict"]) == ["session must be a JSON object"]


def test_missing_version_reported():
    data = _valid_session()
    del data["version"]
    assert any("version" in e for e in validate_session(data))


def test_bool_version_is_not_an_int():
    data = _valid_session()
    data["version"] = True  # bool is an int subclass — must still be rejected.
    assert any("version" in e for e in validate_session(data))


def test_newer_version_reported():
    data = _valid_session()
    data["version"] = SESSION_VERSION + 1
    errors = validate_session(data)
    assert any("newer than supported" in e for e in errors)


def test_malformed_tab_reported():
    data = _valid_session()
    data["tabs"] = [{"path": "/a.png"}, {"path": 123}, "nope"]
    errors = validate_session(data)
    assert any("tab 1" in e for e in errors)
    assert any("tab 2" in e for e in errors)


def test_tabs_must_be_a_list():
    data = _valid_session()
    data["tabs"] = {"path": "/a.png"}
    assert any("'tabs' must be a list" in e for e in validate_session(data))


def test_active_tab_out_of_range_reported():
    data = _valid_session()
    data["active_tab"] = 5
    assert any("out of range" in e for e in validate_session(data))


def test_active_tab_must_be_int():
    data = _valid_session()
    data["active_tab"] = "0"
    assert any("'active_tab' must be an integer" in e for e in validate_session(data))


def test_selection_must_be_a_list():
    data = _valid_session()
    data["selection"] = "a.png"
    assert any("'selection' must be a list" in e for e in validate_session(data))


# ---------------------------------------------------------------------------
# migrate_session
# ---------------------------------------------------------------------------


def test_migrate_fills_missing_keys():
    out = migrate_session({"tabs": [{"path": "/a.png", "title": "a"}]})
    assert out["version"] == SESSION_VERSION
    assert out["active_tab"] == 0
    assert out["selection"] == []
    assert out["current_image"] == ""
    assert out["folder"] == ""
    assert out["tile_grid_mode"] is False


def test_migrate_stamps_older_version():
    out = migrate_session({"version": 0, "tabs": []})
    assert out["version"] == SESSION_VERSION


def test_migrate_current_session_unchanged():
    data = _valid_session()
    assert migrate_session(data) == data


def test_migrate_preserves_future_version():
    out = migrate_session({"version": SESSION_VERSION + 9})
    assert out["version"] == SESSION_VERSION + 9


def test_migrate_non_dict_returns_defaults():
    out = migrate_session(None)
    assert out["version"] == SESSION_VERSION
    assert out["tabs"] == []


def test_migrate_does_not_alias_default_lists():
    one = migrate_session({})
    two = migrate_session({})
    one["tabs"].append({"path": "/x.png", "title": ""})
    assert two["tabs"] == []


def test_migrate_passes_validation():
    assert validate_session(migrate_session({"tabs": []})) == []


# ---------------------------------------------------------------------------
# merge_sessions
# ---------------------------------------------------------------------------


def test_merge_unions_and_dedupes_tabs():
    a = {"tabs": [{"path": "/a.png", "title": "a"}], "selection": ["/a.png"]}
    b = {"tabs": [{"path": "/a.png", "title": "dup"}, {"path": "/b.png", "title": "b"}]}
    merged = merge_sessions([a, b])
    assert [t["path"] for t in merged["tabs"]] == ["/a.png", "/b.png"]


def test_merge_dedupes_selection():
    a = {"selection": ["/a.png", "/b.png"]}
    b = {"selection": ["/b.png", "/c.png"]}
    assert merge_sessions([a, b])["selection"] == ["/a.png", "/b.png", "/c.png"]


def test_merge_carries_first_active_and_folder():
    a = {"tabs": [{"path": "/a.png", "title": "a"}], "active_tab": 0, "folder": "/trip"}
    b = {"tabs": [{"path": "/b.png", "title": "b"}], "active_tab": 0, "folder": "/home"}
    merged = merge_sessions([a, b])
    assert merged["folder"] == "/trip"


def test_merge_ignores_non_dict_entries():
    merged = merge_sessions(["nope", {"tabs": [{"path": "/a.png", "title": "a"}]}, None])
    assert [t["path"] for t in merged["tabs"]] == ["/a.png"]


def test_merge_empty_returns_defaults():
    merged = merge_sessions([])
    assert merged["tabs"] == []
    assert merged["selection"] == []
    assert merged["version"] == SESSION_VERSION


def test_merge_skips_malformed_tabs_and_blank_paths():
    a = {"tabs": ["bad", {"path": ""}, {"path": "/ok.png", "title": "ok"}]}
    merged = merge_sessions([a])
    assert [t["path"] for t in merged["tabs"]] == ["/ok.png"]
