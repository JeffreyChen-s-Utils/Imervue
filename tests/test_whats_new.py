"""Tests for the release-notes registry and What's New dialog."""
from __future__ import annotations

import pytest

from Imervue.system.release_notes import (
    RELEASE_HISTORY,
    ReleaseEntry,
    _parse_version_key,
    current_app_version,
    latest_release,
    releases_since,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


# ---------------------------------------------------------------------------
# Version key parsing
# ---------------------------------------------------------------------------


def test_parse_version_key_orders_numeric_segments():
    assert _parse_version_key("1.0.10") > _parse_version_key("1.0.9")
    assert _parse_version_key("2.0.0") > _parse_version_key("1.99.99")


def test_parse_version_key_handles_empty():
    assert _parse_version_key("") == ()
    # Empty key compares less than any populated key
    assert _parse_version_key("") < _parse_version_key("0.0.1")


def test_parse_version_key_handles_pre_release():
    """Tagged segments still sort lexicographically as a fallback."""
    rc = _parse_version_key("1.0.0-rc1")
    final = _parse_version_key("1.0.0")
    # Both should produce a key — exact ordering is not contract,
    # but we shouldn't raise.
    assert isinstance(rc, tuple)
    assert isinstance(final, tuple)


# ---------------------------------------------------------------------------
# releases_since
# ---------------------------------------------------------------------------


def test_releases_since_empty_seen_returns_full_history():
    assert releases_since("") == RELEASE_HISTORY


def test_releases_since_current_returns_nothing():
    if not RELEASE_HISTORY:
        pytest.skip("Release history is empty in this build")
    latest = RELEASE_HISTORY[0].version
    assert releases_since(latest) == []


def test_releases_since_old_version_returns_all_newer():
    if not RELEASE_HISTORY:
        pytest.skip("Release history is empty in this build")
    # Anything older than the oldest version → full history
    assert releases_since("0.0.1") == RELEASE_HISTORY


def test_latest_release_is_first_entry():
    assert latest_release() == (RELEASE_HISTORY[0] if RELEASE_HISTORY else None)


def test_release_entry_has_bullets():
    if not RELEASE_HISTORY:
        pytest.skip("Release history is empty in this build")
    for entry in RELEASE_HISTORY:
        assert entry.version
        assert isinstance(entry.bullets, list)


def test_current_app_version_is_string():
    v = current_app_version()
    assert isinstance(v, str)
    assert v


# ---------------------------------------------------------------------------
# Dialog (Qt)
# ---------------------------------------------------------------------------


def test_dialog_renders_provided_entries(qapp):
    from Imervue.gui.whats_new_dialog import WhatsNewDialog
    entries = [
        ReleaseEntry(version="9.9.9", bullets=["alpha", "beta"]),
        ReleaseEntry(version="9.9.8", bullets=["only-one"]),
    ]
    dlg = WhatsNewDialog(entries)
    # The dialog has been built — title set, layout populated. We don't
    # assert on inner widget tree to keep the test resilient against
    # cosmetic refactors; the smoke is "constructed without raising".
    assert dlg.windowTitle()


def test_dialog_renders_html_safely(qapp):
    """Bullets containing < / > are not interpreted as HTML tags."""
    from Imervue.gui.whats_new_dialog import _escape
    safe = _escape("a <b>bold</b> & quote")
    assert "&lt;b&gt;" in safe
    assert "&amp;" in safe
    assert "<b>" not in safe


# ---------------------------------------------------------------------------
# Auto-popup persistence
# ---------------------------------------------------------------------------


def test_show_whats_new_skipped_when_already_seen(qapp, monkeypatch):
    from Imervue.gui import whats_new_dialog as mod
    if not RELEASE_HISTORY:
        pytest.skip("Release history is empty in this build")

    user_setting_dict[mod._LAST_SEEN_KEY] = RELEASE_HISTORY[0].version
    # exec() must NOT be called when there are no fresh entries
    called = {"value": False}

    def fail_exec(self):
        called["value"] = True
        return 1

    monkeypatch.setattr(mod.WhatsNewDialog, "exec", fail_exec)
    shown = mod.show_whats_new_if_upgraded(parent=None)
    assert shown is False
    assert called["value"] is False


def test_show_whats_new_runs_on_upgrade(qapp, monkeypatch):
    from Imervue.gui import whats_new_dialog as mod
    if not RELEASE_HISTORY:
        pytest.skip("Release history is empty in this build")

    user_setting_dict[mod._LAST_SEEN_KEY] = "0.0.1"
    monkeypatch.setattr(mod.WhatsNewDialog, "exec", lambda self: 1)
    shown = mod.show_whats_new_if_upgraded(parent=None)
    assert shown is True
    # And the seen-version is updated so we don't nag again
    assert user_setting_dict[mod._LAST_SEEN_KEY] == mod.current_app_version()


def test_open_whats_new_dialog_shows_full_history(qapp, monkeypatch):
    """Manual entry point always opens the dialog regardless of last-seen."""
    from Imervue.gui import whats_new_dialog as mod
    user_setting_dict[mod._LAST_SEEN_KEY] = mod.current_app_version()
    called = {"value": 0}
    monkeypatch.setattr(mod.WhatsNewDialog, "exec",
                        lambda self: called.update(value=1) or 1)
    mod.open_whats_new_dialog(parent=None)
    assert called["value"] == 1
