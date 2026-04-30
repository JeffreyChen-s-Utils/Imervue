"""Tests for workspace-preset CRUD verbs + dialog."""
from __future__ import annotations

import pytest

from Imervue.paint.workspace_preset_dialog import (
    add_user_preset,
    delete_user_preset,
    is_built_in,
    rename_user_preset,
)
from Imervue.paint.workspace_presets import (
    BUILT_IN_PRESETS,
    DockState,
    WorkspacePreset,
    all_workspace_presets,
    load_workspace_presets,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _isolated_storage():
    user_setting_dict.pop("paint_workspace_presets", None)
    yield
    user_setting_dict.pop("paint_workspace_presets", None)


def _custom_preset(name: str = "My Layout") -> WorkspacePreset:
    return WorkspacePreset(
        name=name,
        docks=(
            DockState("layers", area="right", order=0),
            DockState("color", area="left", order=0),
        ),
    )


# ---------------------------------------------------------------------------
# is_built_in
# ---------------------------------------------------------------------------


def test_is_built_in_recognises_canonical_presets():
    assert is_built_in(BUILT_IN_PRESETS[0].name)


def test_is_built_in_false_for_custom():
    assert not is_built_in("My Layout")


# ---------------------------------------------------------------------------
# add_user_preset
# ---------------------------------------------------------------------------


def test_add_user_preset_persists_to_storage():
    add_user_preset(_custom_preset())
    persisted = load_workspace_presets()
    assert any(p.name == "My Layout" for p in persisted)


def test_add_user_preset_replaces_same_name():
    """Re-saving under the same name overwrites — that's what the
    "Save current" UX expects."""
    add_user_preset(_custom_preset())
    first_count = len(load_workspace_presets())
    add_user_preset(_custom_preset())
    assert len(load_workspace_presets()) == first_count


def test_add_user_preset_rejects_built_in_name():
    with pytest.raises(ValueError, match="reserved by a built-in"):
        add_user_preset(_custom_preset(name=BUILT_IN_PRESETS[0].name))


# ---------------------------------------------------------------------------
# delete_user_preset
# ---------------------------------------------------------------------------


def test_delete_user_preset_removes_from_storage():
    add_user_preset(_custom_preset())
    assert delete_user_preset("My Layout") is True
    assert not any(
        p.name == "My Layout"
        for p in load_workspace_presets()
    )


def test_delete_returns_false_for_unknown_name():
    assert delete_user_preset("does-not-exist") is False


def test_delete_returns_false_for_built_in():
    """Built-ins can't be deleted; the verb must report False rather
    than mutate the list."""
    assert delete_user_preset(BUILT_IN_PRESETS[0].name) is False


# ---------------------------------------------------------------------------
# rename_user_preset
# ---------------------------------------------------------------------------


def test_rename_user_preset_updates_storage():
    add_user_preset(_custom_preset())
    assert rename_user_preset("My Layout", "Renamed") is True
    persisted = load_workspace_presets()
    assert any(p.name == "Renamed" for p in persisted)
    assert not any(p.name == "My Layout" for p in persisted)


def test_rename_returns_false_for_unknown_source():
    assert rename_user_preset("absent", "Other") is False


def test_rename_rejects_collision_with_existing():
    add_user_preset(_custom_preset(name="A"))
    add_user_preset(_custom_preset(name="B"))
    with pytest.raises(ValueError, match="already exists"):
        rename_user_preset("A", "B")


def test_rename_rejects_built_in_target():
    add_user_preset(_custom_preset())
    with pytest.raises(ValueError, match="reserved"):
        rename_user_preset("My Layout", BUILT_IN_PRESETS[0].name)


def test_rename_rejects_blank_target():
    add_user_preset(_custom_preset())
    with pytest.raises(ValueError, match="non-empty"):
        rename_user_preset("My Layout", "  ")


# ---------------------------------------------------------------------------
# all_workspace_presets shows user + built-in
# ---------------------------------------------------------------------------


def test_all_workspace_presets_includes_added_user_preset():
    add_user_preset(_custom_preset())
    names = [p.name for p in all_workspace_presets()]
    assert "My Layout" in names
    # Built-ins still present and ordered first.
    assert names[: len(BUILT_IN_PRESETS)] == [
        b.name for b in BUILT_IN_PRESETS
    ]


# ---------------------------------------------------------------------------
# Dialog smoke tests
# ---------------------------------------------------------------------------


def test_dialog_lists_built_in_presets(qapp):
    from Imervue.paint.workspace_preset_dialog import WorkspacePresetDialog
    dialog = WorkspacePresetDialog()
    try:
        # Built-ins all listed; the count is at least len(BUILT_IN_PRESETS).
        assert dialog._list.count() >= len(BUILT_IN_PRESETS)  # noqa: SLF001
    finally:
        dialog.deleteLater()


def test_dialog_includes_user_preset_after_save(qapp):
    """The UI helper updates the list after a save — adding directly
    via the verb then asking the dialog to re-populate must surface
    the new entry."""
    from Imervue.paint.workspace_preset_dialog import WorkspacePresetDialog
    dialog = WorkspacePresetDialog()
    try:
        before = dialog._list.count()  # noqa: SLF001
        add_user_preset(_custom_preset())
        dialog._refresh_list()  # noqa: SLF001
        assert dialog._list.count() == before + 1  # noqa: SLF001
    finally:
        dialog.deleteLater()


def test_dialog_apply_emits_selected_name(qapp):
    from Imervue.paint.workspace_preset_dialog import WorkspacePresetDialog
    dialog = WorkspacePresetDialog()
    try:
        emitted: list[str] = []
        dialog.apply_requested.connect(emitted.append)
        # Select the first row (a built-in).
        dialog._list.setCurrentRow(0)  # noqa: SLF001
        dialog._on_apply()  # noqa: SLF001
        assert emitted == [BUILT_IN_PRESETS[0].name]
    finally:
        dialog.deleteLater()


def test_dialog_delete_button_skips_built_in(qapp):
    from Imervue.paint.workspace_preset_dialog import WorkspacePresetDialog
    dialog = WorkspacePresetDialog()
    try:
        dialog._list.setCurrentRow(0)  # built-in row  # noqa: SLF001
        before = dialog._list.count()  # noqa: SLF001
        dialog._on_delete()  # noqa: SLF001
        # Built-in survived — count unchanged.
        assert dialog._list.count() == before  # noqa: SLF001
    finally:
        dialog.deleteLater()
