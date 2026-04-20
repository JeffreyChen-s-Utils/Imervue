"""End-to-end integration tests for the workspace preset feature.

Exercises the full chain that an end user experiences when clicking
``File > Workspaces…`` — capture the live layout, persist it through
``user_setting_dict``, restart the manager (simulating an app relaunch), and
apply the preset to a fresh UI. Uses a headless fake UI plus real
``QByteArray`` round-tripping so we cover the actual bytes path without
needing a live QMainWindow.
"""
from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtCore import QByteArray

from Imervue.gui.workspace_dialog import apply_workspace, capture_current_workspace
from Imervue.gui.workspace_manager import (
    Workspace,
    WorkspaceManager,
    decode_bytes,
    encode_bytes,
)


# ---------------------------------------------------------------------------
# Fake Qt-ish scaffolding — narrow stubs matching only what the two helpers touch.
# ---------------------------------------------------------------------------


class _FakeSplitter:
    def __init__(self, sizes):
        self._sizes = list(sizes)
        self.set_calls: list[list[int]] = []

    def sizes(self):
        return list(self._sizes)

    def setSizes(self, sizes):  # noqa: N802  # NOSONAR mirrors Qt QSplitter API
        self.set_calls.append(list(sizes))
        self._sizes = list(sizes)


class _FakeIndex:
    def __init__(self, path: str, valid: bool = True):
        self._path = path
        self._valid = valid

    def isValid(self):  # noqa: N802  # NOSONAR mirrors Qt QModelIndex API
        return self._valid


class _FakeModel:
    def __init__(self, initial_root: str):
        self._root = initial_root
        self.set_root_calls: list[str] = []

    def filePath(self, index):  # noqa: N802  # NOSONAR mirrors Qt QFileSystemModel API
        return getattr(index, "_path", "") if index is not None else ""

    def setRootPath(self, root):  # noqa: N802  # NOSONAR mirrors Qt API
        self.set_root_calls.append(root)
        self._root = root

    def index(self, root):
        return _FakeIndex(root)


class _FakeTree:
    def __init__(self, root: str):
        self._model = _FakeModel(root)
        self._root_index = _FakeIndex(root, valid=bool(root))
        self.set_root_index_calls: list[_FakeIndex] = []

    def model(self):
        return self._model

    def rootIndex(self):  # noqa: N802  # NOSONAR mirrors Qt QTreeView API
        return self._root_index

    def setRootIndex(self, index):  # noqa: N802  # NOSONAR mirrors Qt API
        self.set_root_index_calls.append(index)
        self._root_index = index


class _FakeMainWindow:
    """Headless stand-in for ``ImervueMainWindow`` — just enough surface area."""

    def __init__(
        self,
        *,
        geometry: bytes = b"GEOM-v1",
        state: bytes = b"STATE-v1",
        maximized: bool = True,
        splitter_sizes=(200, 800, 300),
        root_folder: str = "/photos/shoot",
    ):
        self._geometry = geometry
        self._state = state
        self._maximized = maximized
        self._main_splitter = _FakeSplitter(splitter_sizes)
        self.tree = _FakeTree(root_folder)

        self.show_maximized_count = 0
        self.show_normal_count = 0
        self.restored_geometry: bytes | None = None
        self.restored_state: bytes | None = None

    def saveGeometry(self):  # noqa: N802  # NOSONAR mirrors Qt QMainWindow API
        return bytes(self._geometry)

    def saveState(self):  # noqa: N802  # NOSONAR mirrors Qt API
        return bytes(self._state)

    def isMaximized(self):  # noqa: N802  # NOSONAR mirrors Qt API
        return self._maximized

    def restoreGeometry(self, qba):  # noqa: N802  # NOSONAR mirrors Qt API
        self.restored_geometry = bytes(qba.data() if hasattr(qba, "data") else qba)

    def restoreState(self, qba):  # noqa: N802  # NOSONAR mirrors Qt API
        self.restored_state = bytes(qba.data() if hasattr(qba, "data") else qba)

    def showMaximized(self):  # noqa: N802  # NOSONAR mirrors Qt API
        self.show_maximized_count += 1

    def showNormal(self):  # noqa: N802  # NOSONAR mirrors Qt API
        self.show_normal_count += 1


@pytest.fixture
def fresh_store(monkeypatch):
    """Redirect the manager's backing dict to a private per-test store."""
    from Imervue.gui import workspace_manager as wm

    store: dict = {}
    monkeypatch.setattr(wm, "user_setting_dict", store, raising=True)
    monkeypatch.setattr(wm, "schedule_save", lambda: None, raising=True)
    return store


# ---------------------------------------------------------------------------
# End-to-end workflows
# ---------------------------------------------------------------------------


class TestCaptureSaveLoadApplyRoundtrip:
    def test_full_roundtrip_matches_original_layout(self, fresh_store):
        ui = _FakeMainWindow(
            geometry=b"G-SESSION-01",
            state=b"S-DOCKSTATE-01",
            maximized=False,
            splitter_sizes=[250, 900, 320],
            root_folder="/library/A",
        )
        manager = WorkspaceManager()

        captured = capture_current_workspace(cast(Any, ui), "Develop")
        manager.save(captured)

        # Fresh manager reads settings back from disk-equivalent (the dict).
        reloaded = WorkspaceManager()
        names = [w.name for w in reloaded.list_all()]
        assert names == ["Develop"]

        preset = reloaded.get("Develop")
        assert preset is not None
        assert decode_bytes(preset.geometry_b64) == b"G-SESSION-01"
        assert decode_bytes(preset.state_b64) == b"S-DOCKSTATE-01"
        assert preset.splitter_sizes == [250, 900, 320]
        assert preset.root_folder == "/library/A"
        assert preset.maximized is False

        # Apply to a brand-new window and confirm every surface was poked.
        target = _FakeMainWindow(
            geometry=b"OTHER", state=b"OTHER",
            maximized=True, splitter_sizes=[1, 1, 1],
            root_folder="/somewhere/else",
        )
        apply_workspace(cast(Any, target), preset)

        assert target.restored_geometry == b"G-SESSION-01"
        assert target.restored_state == b"S-DOCKSTATE-01"
        assert target.show_normal_count == 1
        assert target.show_maximized_count == 0
        assert target._main_splitter.set_calls[-1] == [250, 900, 320]
        assert target.tree.model().set_root_calls == ["/library/A"]

    def test_roundtrip_preserves_maximized_flag(self, fresh_store):
        ui = _FakeMainWindow(maximized=True)
        manager = WorkspaceManager()
        manager.save(capture_current_workspace(cast(Any, ui), "Browse"))

        target = _FakeMainWindow(maximized=False)
        apply_workspace(cast(Any, target), WorkspaceManager().get("Browse"))
        assert target.show_maximized_count == 1
        assert target.show_normal_count == 0

    def test_apply_skips_splitter_when_no_sizes(self, fresh_store):
        manager = WorkspaceManager()
        manager.save(Workspace(
            name="NoSplit",
            geometry_b64=encode_bytes(b"G"),
            state_b64=encode_bytes(b"S"),
            maximized=False,
            root_folder="",
            splitter_sizes=[],
        ))

        target = _FakeMainWindow(splitter_sizes=[10, 20, 30])
        apply_workspace(cast(Any, target), manager.get("NoSplit"))
        # Nothing should have reached the splitter — only original value stands.
        assert target._main_splitter.set_calls == []

    def test_apply_skips_tree_when_root_empty(self, fresh_store):
        manager = WorkspaceManager()
        manager.save(Workspace(name="NoRoot", root_folder=""))

        target = _FakeMainWindow(root_folder="/already/here")
        apply_workspace(cast(Any, target), manager.get("NoRoot"))
        assert target.tree.model().set_root_calls == []
        assert target.tree.set_root_index_calls == []

    def test_bytes_survive_qbytearray_roundtrip(self, fresh_store):
        # QByteArray carries the payload from decode → restoreGeometry; make
        # sure every byte (including NULs and 0xFF) passes through unharmed.
        raw = bytes(range(256))
        manager = WorkspaceManager()
        manager.save(Workspace(
            name="Bytes",
            geometry_b64=encode_bytes(raw),
            state_b64=encode_bytes(raw[::-1]),
        ))

        target = _FakeMainWindow()
        apply_workspace(cast(Any, target), manager.get("Bytes"))
        assert target.restored_geometry == raw
        assert target.restored_state == raw[::-1]

    def test_qbytearray_constructor_matches_decoded_payload(self):
        # Guard against a future refactor silently stripping bytes via
        # QByteArray — ensure the Qt path produces the same payload bytes.
        raw = b"\x00\x01\xff\xfe\x7fHELLO"
        qba = QByteArray(raw)
        assert bytes(qba.data()) == raw


class TestManagerPersistenceAcrossInstances:
    def test_rename_visible_in_new_manager(self, fresh_store):
        m1 = WorkspaceManager()
        m1.save(Workspace(name="OldName"))
        assert m1.rename("OldName", "NewName") is True

        m2 = WorkspaceManager()
        assert m2.get("OldName") is None
        assert m2.get("NewName") is not None

    def test_delete_visible_in_new_manager(self, fresh_store):
        m1 = WorkspaceManager()
        m1.save(Workspace(name="Gone"))
        m1.save(Workspace(name="Kept"))
        m1.delete("Gone")

        m2 = WorkspaceManager()
        assert [w.name for w in m2.list_all()] == ["Kept"]

    def test_overwrite_keeps_single_entry(self, fresh_store):
        m1 = WorkspaceManager()
        m1.save(Workspace(name="X", root_folder="/v1"))
        m1.save(Workspace(name="X", root_folder="/v2"))

        m2 = WorkspaceManager()
        assert len(m2.list_all()) == 1
        assert m2.get("X").root_folder == "/v2"

    def test_settings_payload_is_plain_dicts(self, fresh_store):
        manager = WorkspaceManager()
        manager.save(Workspace(name="Plain", root_folder="/pics"))
        raw = fresh_store["workspaces"]
        assert isinstance(raw, list)
        assert isinstance(raw[0], dict)
        assert raw[0]["name"] == "Plain"
        assert raw[0]["root_folder"] == "/pics"
        # Should NOT leak any Qt / PySide objects into the settings file.
        for value in raw[0].values():
            assert not type(value).__module__.startswith("PySide")


class TestCaptureOmittedAttributes:
    """Older windows may not expose every attribute — capture must not crash."""

    def test_capture_without_splitter(self, fresh_store):
        ui = _FakeMainWindow()
        del ui._main_splitter
        captured = capture_current_workspace(cast(Any, ui), "Minimal")
        assert captured.splitter_sizes == []

    def test_capture_with_invalid_root_index(self, fresh_store):
        ui = _FakeMainWindow(root_folder="/photos")
        ui.tree._root_index = _FakeIndex("/photos", valid=False)
        captured = capture_current_workspace(cast(Any, ui), "NoRoot")
        assert captured.root_folder == ""
