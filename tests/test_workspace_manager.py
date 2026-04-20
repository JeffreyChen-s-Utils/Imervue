"""Tests for the workspace preset manager and its helpers."""
from __future__ import annotations

import pytest

from Imervue.gui.workspace_manager import (
    Workspace,
    WorkspaceManager,
    decode_bytes,
    encode_bytes,
)


@pytest.fixture
def isolated_store(monkeypatch):
    """Back the manager with a throw-away dict so tests never touch disk."""
    from Imervue.gui import workspace_manager as wm

    store: dict = {}
    monkeypatch.setattr(wm, "user_setting_dict", store, raising=True)
    monkeypatch.setattr(wm, "schedule_save", lambda: None, raising=True)
    return store


@pytest.fixture
def manager(isolated_store):
    return WorkspaceManager()


class TestWorkspaceDataclass:
    def test_to_from_dict_roundtrip(self):
        ws = Workspace(
            name="Develop",
            geometry_b64="AA==",
            state_b64="BB==",
            maximized=False,
            root_folder="/photos",
            splitter_sizes=[120, 480, 240],
        )
        restored = Workspace.from_dict(ws.to_dict())
        assert restored == ws

    def test_from_dict_requires_name(self):
        with pytest.raises(ValueError):
            Workspace.from_dict({"name": "   "})

    def test_from_dict_clamps_long_name(self):
        restored = Workspace.from_dict({"name": "x" * 500})
        assert len(restored.name) == 64

    def test_from_dict_coerces_splitter_sizes(self):
        restored = Workspace.from_dict({
            "name": "ok",
            "splitter_sizes": ["10", 20, 30.7],
        })
        assert restored.splitter_sizes == [10, 20, 30]

    def test_from_dict_defaults_missing_fields(self):
        restored = Workspace.from_dict({"name": "min"})
        assert restored.geometry_b64 == ""
        assert restored.state_b64 == ""
        assert restored.maximized is True
        assert restored.root_folder == ""
        assert restored.splitter_sizes == []


class TestSaveGetList:
    def test_save_then_get(self, manager):
        ws = Workspace(name="A")
        manager.save(ws)
        assert manager.get("A") is ws

    def test_save_rejects_blank_name(self, manager):
        with pytest.raises(ValueError):
            manager.save(Workspace(name="   "))

    def test_save_trims_whitespace(self, manager):
        manager.save(Workspace(name="  Browse  "))
        assert manager.get("Browse") is not None
        assert manager.get("  Browse  ") is None

    def test_save_clamps_long_name(self, manager):
        manager.save(Workspace(name="n" * 500))
        names = [ws.name for ws in manager.list_all()]
        assert names == ["n" * 64]

    def test_list_all_sorted_case_insensitive(self, manager):
        for n in ["zulu", "alpha", "Bravo"]:
            manager.save(Workspace(name=n))
        assert [w.name for w in manager.list_all()] == ["alpha", "Bravo", "zulu"]

    def test_get_missing_returns_none(self, manager):
        assert manager.get("nope") is None


class TestDeleteRename:
    def test_delete_removes_entry(self, manager):
        manager.save(Workspace(name="A"))
        assert manager.delete("A") is True
        assert manager.get("A") is None

    def test_delete_missing_returns_false(self, manager):
        assert manager.delete("ghost") is False

    def test_rename_moves_entry(self, manager):
        manager.save(Workspace(name="old"))
        assert manager.rename("old", "new") is True
        assert manager.get("old") is None
        assert manager.get("new") is not None

    def test_rename_refuses_collision(self, manager):
        manager.save(Workspace(name="A"))
        manager.save(Workspace(name="B"))
        assert manager.rename("A", "B") is False
        assert manager.get("A") is not None

    def test_rename_missing_source_returns_false(self, manager):
        assert manager.rename("missing", "target") is False

    def test_rename_blank_target_raises(self, manager):
        manager.save(Workspace(name="A"))
        with pytest.raises(ValueError):
            manager.rename("A", "   ")


class TestPersistence:
    def test_save_writes_plain_dicts_to_settings(self, manager, isolated_store):
        manager.save(Workspace(name="A", root_folder="/p"))
        raw = isolated_store["workspaces"]
        assert isinstance(raw, list)
        assert raw[0]["name"] == "A"
        assert raw[0]["root_folder"] == "/p"

    def test_load_skips_malformed_entries(self, isolated_store):
        isolated_store["workspaces"] = [
            {"name": "Good"},
            "not a dict",
            {"name": ""},
            {},
        ]
        mgr = WorkspaceManager()
        assert [w.name for w in mgr.list_all()] == ["Good"]

    def test_invalidate_rereads_settings(self, manager, isolated_store):
        manager.save(Workspace(name="A"))
        isolated_store["workspaces"] = [{"name": "External"}]
        assert manager.get("External") is None
        manager.invalidate()
        assert manager.get("External") is not None
        assert manager.get("A") is None

    def test_empty_settings_means_empty_list(self, isolated_store):
        mgr = WorkspaceManager()
        assert mgr.list_all() == []


class TestBytesHelpers:
    def test_roundtrip_bytes(self):
        raw = b"\x00\x01\x02QTstate\xff"
        assert decode_bytes(encode_bytes(raw)) == raw

    def test_decode_empty_string(self):
        assert decode_bytes("") == b""

    def test_decode_invalid_base64_returns_empty(self):
        # length 3 triggers a padding error (binascii.Error -> ValueError)
        assert decode_bytes("abc") == b""

    def test_decode_non_ascii_returns_empty(self):
        assert decode_bytes("caf\u00e9") == b""
