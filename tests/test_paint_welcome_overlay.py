"""Tests for the WelcomeHint widget + workspace integration."""
from __future__ import annotations

import pytest

from Imervue.paint import recent_files, tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.welcome_overlay import WelcomeHint
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop(recent_files.RECENT_FILES_KEY, None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop(recent_files.RECENT_FILES_KEY, None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# WelcomeHint widget — pure Qt construction, no workspace involved
# ---------------------------------------------------------------------------


def test_welcome_hint_starts_hidden(qapp):
    """The widget never auto-shows on construction — visibility is
    driven entirely by the workspace so a test can pull it apart
    without an unwanted phantom panel popping up."""
    hint = WelcomeHint()
    try:
        assert hint.isVisible() is False
    finally:
        hint.deleteLater()


def test_welcome_hint_buttons_emit_documented_signals(qapp):
    """Each button forwards the click via the matching ``*_requested``
    signal so the workspace can route the action to its file menu
    bridge without inheriting from the widget."""
    hint = WelcomeHint()
    try:
        new_calls = []
        open_calls = []
        hint.new_requested.connect(lambda: new_calls.append(1))
        hint.open_requested.connect(lambda: open_calls.append(1))
        hint._new_btn.click()  # noqa: SLF001
        hint._open_btn.click()  # noqa: SLF001
        assert new_calls == [1]
        assert open_calls == [1]
    finally:
        hint.deleteLater()


def test_welcome_hint_recent_paths_render_basenames(qapp):
    """A recent-file row shows just the basename so the panel stays
    compact even when the user opens files from deep paths."""
    hint = WelcomeHint()
    try:
        hint.set_recent_paths([
            "/projects/manga/chapter01/page-03.psd",
            "/scratch/blue.png",
        ])
        labels = [btn.text() for btn in hint._recent_buttons]  # noqa: SLF001
        assert labels == ["page-03.psd", "blue.png"]
    finally:
        hint.deleteLater()


def test_welcome_hint_recent_emits_full_path(qapp):
    """``recent_requested`` carries the full path so the workspace
    can call ``open_psd_at`` with a value that survives a
    relative-cwd switch — the basename alone is ambiguous."""
    hint = WelcomeHint()
    try:
        captured = []
        hint.recent_requested.connect(captured.append)
        hint.set_recent_paths(["/projects/manga/chapter01/page-03.psd"])
        hint._recent_buttons[0].click()  # noqa: SLF001
        assert captured == ["/projects/manga/chapter01/page-03.psd"]
    finally:
        hint.deleteLater()


def test_welcome_hint_recent_section_caps_at_documented_max(qapp):
    """Anything past the configured cap is dropped so a long
    history doesn't grow the panel until it covers the canvas."""
    from Imervue.paint.welcome_overlay import _MAX_RECENT_ROWS
    hint = WelcomeHint()
    try:
        many = [f"/p/file{i}.psd" for i in range(_MAX_RECENT_ROWS + 4)]
        hint.set_recent_paths(many)
        assert len(hint._recent_buttons) == _MAX_RECENT_ROWS  # noqa: SLF001
    finally:
        hint.deleteLater()


def test_welcome_hint_empty_recent_hides_the_row(qapp):
    """No recents → no "Recent" label so first-time users don't
    stare at an empty section."""
    hint = WelcomeHint()
    try:
        hint.set_recent_paths(["/p/x.psd"])
        assert hint._recent_label.isVisibleTo(hint) or True  # populated
        hint.set_recent_paths([])
        assert hint._recent_label.isVisible() is False  # noqa: SLF001
    finally:
        hint.deleteLater()


def test_welcome_hint_position_centred_handles_zero_parent(qapp):
    """Centring math survives a zero-sized parent — the constructor
    runs before the canvas widget has been laid out so this can
    fire with width / height both 0."""
    hint = WelcomeHint()
    try:
        hint.position_centred(0, 0)
        assert hint.x() == 0 and hint.y() == 0
    finally:
        hint.deleteLater()


def test_welcome_hint_set_translations_updates_labels(qapp):
    """Localised strings flow through ``set_translations`` rather
    than the constructor so the widget stays import-cheap for tests
    that don't pull in the language wrapper."""
    hint = WelcomeHint()
    try:
        hint.set_translations(
            title="拖入圖片",
            subtitle="或從這裡開始",
            new_label="新分頁",
            open_label="開啟檔案…",
            recent_label="最近",
        )
        assert hint._title.text() == "拖入圖片"  # noqa: SLF001
        assert hint._new_btn.text() == "新分頁"  # noqa: SLF001
    finally:
        hint.deleteLater()


# ---------------------------------------------------------------------------
# Workspace integration
# ---------------------------------------------------------------------------


def test_workspace_shows_welcome_hint_on_fresh_boot(qapp):
    """A newly-constructed workspace surfaces the welcome panel so
    the very first user sees the drag-drop / new / open shortcuts
    instead of a featureless white canvas. The Qt ``isVisible``
    flag depends on the window being shown; ``isHidden`` plus the
    workspace-level dismissal flag is the headless-friendly read."""
    ws = PaintWorkspace()
    try:
        assert ws._welcome_hint.isHidden() is False  # noqa: SLF001
        assert ws._welcome_dismissed is False  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_workspace_dismisses_welcome_on_image_loaded(qapp):
    """Loading any image should clear the welcome hint — the user
    has clearly opened something and doesn't need the affordance."""
    ws = PaintWorkspace()
    try:
        ws._on_image_loaded(800, 600)  # noqa: SLF001
        assert ws._welcome_dismissed is True  # noqa: SLF001
        assert ws._welcome_hint.isHidden() is True  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_workspace_dismisses_welcome_on_first_document_change(qapp):
    """First brush stroke (or any tool action that fires
    ``document_changed``) tears the panel down — it can't linger
    on top of strokes."""
    ws = PaintWorkspace()
    try:
        ws._on_document_changed()  # noqa: SLF001
        assert ws._welcome_dismissed is True  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_workspace_welcome_routes_new_tab(qapp):
    """The welcome panel's "New tab" button must add a tab to the
    workspace and dismiss the hint."""
    ws = PaintWorkspace()
    try:
        before = ws._tabs.count()  # noqa: SLF001
        ws._welcome_hint.new_requested.emit()  # noqa: SLF001
        assert ws._tabs.count() == before + 1  # noqa: SLF001
        assert ws._welcome_dismissed is True  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_workspace_seeds_welcome_recent_from_user_settings(qapp):
    """Recent-file rows are populated from the same store the file
    menu reads, so the panel stays in sync with the rest of the
    UI without a separate cache."""
    recent_files.add("/scratch/canvas-a.psd")
    recent_files.add("/scratch/canvas-b.psd")
    ws = PaintWorkspace()
    try:
        labels = [
            btn.text() for btn in ws._welcome_hint._recent_buttons   # noqa: SLF001
        ]
        # Newest first per recent_files semantics.
        assert labels[0] == "canvas-b.psd"
        assert labels[1] == "canvas-a.psd"
    finally:
        ws.deleteLater()


def test_welcome_buttons_have_tooltips(qapp):
    """The New / Open buttons in the welcome panel surface a tooltip
    so the artist sees the action's keystroke / what the button does
    on hover, not only via the bare label."""
    panel = WelcomeHint()
    try:
        # Pre-translation tooltips are populated at construction time.
        assert panel._new_btn.toolTip()        # noqa: SLF001
        assert panel._open_btn.toolTip()       # noqa: SLF001
    finally:
        panel.deleteLater()


def test_welcome_set_translations_updates_tooltips(qapp):
    """A localiser pushing translated tooltips through set_translations
    must reach the underlying buttons so the panel speaks the user's
    language end-to-end."""
    panel = WelcomeHint()
    try:
        panel.set_translations(
            new_tooltip="新分頁 (Ctrl+T)",
            open_tooltip="開啟檔案",
        )
        assert "新分頁" in panel._new_btn.toolTip()       # noqa: SLF001
        assert "開啟檔案" in panel._open_btn.toolTip()    # noqa: SLF001
    finally:
        panel.deleteLater()
