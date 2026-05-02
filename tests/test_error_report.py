"""Tests for the support-bundle generator."""
from __future__ import annotations

import json
import zipfile

from Imervue.system.error_report import (
    _SENSITIVE_KEYS,
    _next_free_path,
    build_report,
    collect_system_info,
    sanitise_settings,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------


def test_sanitise_strips_personal_data():
    raw = {
        "language": "English",
        "user_recent_folders": ["/home/me/secret"],
        "bookmarks": ["/home/me/photo.jpg"],
        "image_ratings": {"/some/path": 5},
        "macros": [{"name": "fast"}],
        "window_geometry": "AAAAAA==",
    }
    out = sanitise_settings(raw)
    assert out == {"language": "English"}


def test_sanitise_passes_through_safe_keys():
    """Anything not in the sensitive set is preserved verbatim."""
    raw = {
        "language": "English",
        "theme": "dracula",
        "ui_scale_percent": 120,
        "vram_limit_mb": 4096,
        "stack_raw_jpeg_pairs": True,
    }
    assert sanitise_settings(raw) == raw


def test_sensitive_keyset_is_frozen():
    """_SENSITIVE_KEYS is the contract — assert its members so accidental
    deletes show up as a test failure."""
    expected = {
        "user_recent_folders",
        "user_recent_images",
        "user_last_folder",
        "bookmarks",
        "image_ratings",
        "image_favorites",
        "image_color_labels",
        "macros",
        "macro_last_name",
        "external_editors",
        "window_geometry",
        "window_state",
    }
    assert expected.issubset(_SENSITIVE_KEYS)


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------


def test_collect_system_info_has_required_keys():
    info = collect_system_info()
    for key in (
        "imervue_version", "python", "platform",
        "is_frozen", "report_generated_at",
    ):
        assert key in info


def test_collect_system_info_is_jsonable():
    info = collect_system_info()
    # Must round-trip through JSON without TypeError
    text = json.dumps(info)
    assert json.loads(text) == info


# ---------------------------------------------------------------------------
# Filename collision handling
# ---------------------------------------------------------------------------


def test_next_free_path_returns_input_when_not_taken(tmp_path):
    path = tmp_path / "report.zip"
    assert _next_free_path(path) == path


def test_next_free_path_appends_counter_on_collision(tmp_path):
    path = tmp_path / "report.zip"
    path.write_bytes(b"x")
    out = _next_free_path(path)
    assert out == tmp_path / "report-1.zip"


def test_next_free_path_skips_existing_counters(tmp_path):
    (tmp_path / "report.zip").write_bytes(b"x")
    (tmp_path / "report-1.zip").write_bytes(b"x")
    (tmp_path / "report-2.zip").write_bytes(b"x")
    out = _next_free_path(tmp_path / "report.zip")
    assert out == tmp_path / "report-3.zip"


# ---------------------------------------------------------------------------
# Bundle builder (end-to-end)
# ---------------------------------------------------------------------------


def test_build_report_produces_zip_with_expected_files(tmp_path):
    user_setting_dict["language"] = "English"
    user_setting_dict["bookmarks"] = ["/secret/path"]
    user_setting_dict["image_favorites"] = {"/secret/photo.jpg"}

    out_path = tmp_path / "bundle.zip"
    result = build_report(out_path)
    assert result == out_path
    assert out_path.exists()

    with zipfile.ZipFile(out_path) as zf:
        names = set(zf.namelist())
        assert "system_info.json" in names
        assert "user_settings_sanitised.json" in names
        # Personal data must NOT be in the bundle
        settings_text = zf.read("user_settings_sanitised.json").decode("utf-8")
    assert "/secret/path" not in settings_text
    assert "/secret/photo.jpg" not in settings_text


def test_build_report_handles_set_in_settings(tmp_path):
    """``set`` values used internally must not crash the JSON encoder."""
    user_setting_dict["theme"] = "nord"
    user_setting_dict["image_favorites"] = {"a", "b"}  # set, not list

    out_path = tmp_path / "bundle.zip"
    build_report(out_path)
    # Just opening the zip without raising is enough — the sanitise pass
    # drops `image_favorites` anyway, but the coercion path runs first.
    with zipfile.ZipFile(out_path) as zf:
        zf.namelist()


def test_build_report_does_not_overwrite_existing(tmp_path):
    target = tmp_path / "bundle.zip"
    target.write_bytes(b"existing")
    out = build_report(target)
    # Build should land at bundle-1.zip, leaving the existing untouched
    assert out != target
    assert target.read_bytes() == b"existing"
