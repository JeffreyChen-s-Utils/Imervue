"""Tests for workspace-preset CRUD verbs + dialog."""
from __future__ import annotations

import pytest

from Imervue.paint.workspace_preset_dialog import (
    add_user_preset,
    apply_workspace_preset,
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


# ---------------------------------------------------------------------------
# apply_workspace_preset
# ---------------------------------------------------------------------------


class _StubDock:
    """Minimal stand-in for QDockWidget that records visibility + raises.

    Avoids the cost of a real Qt main window when the only thing the
    apply path touches is ``isVisible`` / ``setVisible`` / ``raise_``.
    """

    def __init__(self, visible: bool = True):
        self._visible = visible
        self.raise_calls = 0

    def isVisible(self) -> bool:
        return self._visible

    def setVisible(self, value: bool) -> None:
        self._visible = bool(value)

    def raise_(self) -> None:
        self.raise_calls += 1


class _StubWorkspace:
    """Plain object with the dock attributes ``apply_workspace_preset``
    expects — keeps the test free of Qt main-window setup."""

    def __init__(self):
        self._layer_dock = _StubDock(visible=True)
        self._color_dock = _StubDock(visible=True)
        self._brush_dock = _StubDock(visible=True)
        self._navigator_dock = _StubDock(visible=True)
        self._history_dock = _StubDock(visible=True)
        self._reference_dock = _StubDock(visible=False)


def test_apply_preset_toggles_visibility_to_match_state():
    """A "Drawing" preset hides navigator / history / reference; the
    apply call must flip those docks invisible without touching the
    others."""
    ws = _StubWorkspace()
    drawing = next(p for p in BUILT_IN_PRESETS if p.name == "Drawing")
    changed = apply_workspace_preset(ws, drawing)
    assert changed
    assert ws._brush_dock.isVisible() is True   # noqa: SLF001
    assert ws._color_dock.isVisible() is True   # noqa: SLF001
    assert ws._layer_dock.isVisible() is True   # noqa: SLF001
    assert ws._navigator_dock.isVisible() is False   # noqa: SLF001
    assert ws._history_dock.isVisible() is False   # noqa: SLF001
    assert ws._reference_dock.isVisible() is False   # noqa: SLF001


def test_apply_preset_returns_false_when_state_already_matches():
    """No-op apply: dock visibility matches the preset, so ``raise_``
    still fires (the user explicitly requested the layout) but the
    return value reports no change."""
    ws = _StubWorkspace()
    default = next(p for p in BUILT_IN_PRESETS if p.name == "Default")
    # Match the Default preset's visibility manually.
    ws._reference_dock._visible = False  # noqa: SLF001
    changed = apply_workspace_preset(ws, default)
    assert changed is False


def test_apply_preset_raises_first_visible_dock_listed():
    """The first visible dock in the preset's ``docks`` becomes the
    surfaced tab. For "Comic" that's the reference dock — applying
    the preset must call ``raise_`` on it."""
    ws = _StubWorkspace()
    comic = next(p for p in BUILT_IN_PRESETS if p.name == "Comic")
    apply_workspace_preset(ws, comic)
    # Reference is the first visible dock listed in the Comic preset
    # (see workspace_presets.py).
    assert ws._reference_dock.raise_calls >= 1   # noqa: SLF001


def test_apply_preset_skips_unknown_dock_names():
    """An unknown dock name in the preset must not raise — keeps the
    preset format forward-compatible with future docks the workspace
    doesn't know about yet."""
    ws = _StubWorkspace()
    custom = WorkspacePreset(
        name="Custom",
        docks=(
            DockState("brush", visible=True),
            DockState("widget_added_in_future", visible=True),
        ),
    )
    # Should not raise even though "widget_added_in_future" is not in
    # _DOCK_NAME_TO_ATTR.
    apply_workspace_preset(ws, custom)


def test_each_built_in_preset_lists_distinct_first_visible_dock():
    """Built-in presets surface a different primary dock so the user
    sees an immediate visual change when applying. Same primary dock
    for two presets means the user can't tell them apart at a
    glance — the original "they all look the same" complaint."""
    primaries = []
    for preset in BUILT_IN_PRESETS:
        first = next((d for d in preset.docks if d.visible), None)
        assert first is not None, f"preset {preset.name} has no visible dock"
        primaries.append(first.name)
    # At least 3 of the 4 built-ins should differ on first-visible
    # (Default + Compact both surface layers because layers is the
    # universal anchor; Drawing surfaces brush, Comic surfaces
    # reference). Allow that one overlap, refuse a full collapse.
    assert len(set(primaries)) >= 3
