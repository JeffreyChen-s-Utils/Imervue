"""Tests for autosave snapshot lifecycle + workspace integration."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.autosave import (
    AUTOSAVE_DIR_NAME,
    AUTOSAVE_PREFIX,
    AUTOSAVE_SUFFIX,
    DEFAULT_INTERVAL_SEC,
    MAX_RETAINED_SNAPSHOTS,
    autosave_dir,
    clear_snapshots,
    latest_snapshot,
    list_snapshots,
    load_snapshot,
    prune_snapshots,
    take_snapshot,
)
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _composite(h: int = 8, w: int = 8, c: tuple[int, int, int] = (200, 100, 50)):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = c[0]
    arr[..., 1] = c[1]
    arr[..., 2] = c[2]
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# autosave_dir + take_snapshot basics
# ---------------------------------------------------------------------------


def test_autosave_dir_created_under_app_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "Imervue.paint.autosave.app_dir", lambda: tmp_path,
    )
    out = autosave_dir()
    assert out.is_dir()
    assert out.name == AUTOSAVE_DIR_NAME


def test_take_snapshot_writes_png(tmp_path):
    arr = _composite()
    path = take_snapshot(arr, target_dir=tmp_path, now=1700000000.0)
    assert path.exists()
    assert path.suffix == AUTOSAVE_SUFFIX
    assert path.name.startswith(AUTOSAVE_PREFIX)


def test_take_snapshot_round_trip(tmp_path):
    arr = _composite(c=(50, 100, 200))
    path = take_snapshot(arr, target_dir=tmp_path, now=1700000001.0)
    reloaded = load_snapshot(path)
    np.testing.assert_array_equal(reloaded, arr)


def test_take_snapshot_rejects_non_rgba(tmp_path):
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        take_snapshot(bad, target_dir=tmp_path)


def test_take_snapshot_filename_sortable_chronologically(tmp_path):
    """Names must sort lexically into the same order they were taken
    so latest_snapshot can pick the most recent by string comparison.
    """
    arr = _composite(2, 2)
    p_old = take_snapshot(arr, target_dir=tmp_path, now=1700000000.0)
    p_new = take_snapshot(arr, target_dir=tmp_path, now=1700001000.0)
    assert p_old.name < p_new.name


def test_default_interval_documented():
    assert DEFAULT_INTERVAL_SEC > 0


# ---------------------------------------------------------------------------
# list_snapshots / latest_snapshot
# ---------------------------------------------------------------------------


def test_list_returns_sorted_oldest_first(tmp_path):
    arr = _composite(2, 2)
    take_snapshot(arr, target_dir=tmp_path, now=1700000000.5)
    take_snapshot(arr, target_dir=tmp_path, now=1700000001.5)
    take_snapshot(arr, target_dir=tmp_path, now=1700000002.5)
    files = list_snapshots(target_dir=tmp_path)
    assert len(files) == 3
    assert all(files[i].name <= files[i + 1].name for i in range(2))


def test_list_skips_unrelated_files(tmp_path):
    arr = _composite(2, 2)
    take_snapshot(arr, target_dir=tmp_path, now=1700000000.0)
    (tmp_path / "stray.txt").write_text("not a snapshot")
    (tmp_path / "preview.png").write_bytes(b"")  # not the right name pattern
    files = list_snapshots(target_dir=tmp_path)
    assert all(f.name.startswith(AUTOSAVE_PREFIX) for f in files)


def test_latest_returns_newest(tmp_path):
    arr = _composite(2, 2)
    take_snapshot(arr, target_dir=tmp_path, now=1700000000.0)
    new = take_snapshot(arr, target_dir=tmp_path, now=1700001000.0)
    assert latest_snapshot(target_dir=tmp_path) == new


def test_latest_with_no_snapshots_returns_none(tmp_path):
    assert latest_snapshot(target_dir=tmp_path) is None


def test_list_with_missing_dir_returns_empty(tmp_path):
    files = list_snapshots(target_dir=tmp_path / "no_such_dir")
    assert files == []


# ---------------------------------------------------------------------------
# Pruning + clearing
# ---------------------------------------------------------------------------


def test_prune_keeps_documented_count(tmp_path):
    arr = _composite(2, 2)
    for i in range(MAX_RETAINED_SNAPSHOTS + 5):
        take_snapshot(arr, target_dir=tmp_path, now=1700000000.0 + i)
    files = list_snapshots(target_dir=tmp_path)
    assert len(files) == MAX_RETAINED_SNAPSHOTS


def test_prune_drops_oldest_first(tmp_path):
    arr = _composite(2, 2)
    paths = [
        take_snapshot(arr, target_dir=tmp_path, now=1700000000.0 + i)
        for i in range(MAX_RETAINED_SNAPSHOTS + 3)
    ]
    surviving = {p.name for p in list_snapshots(target_dir=tmp_path)}
    # The oldest 3 must be gone; the newest MAX_RETAINED must survive.
    for old in paths[:3]:
        assert old.name not in surviving
    for keep in paths[-MAX_RETAINED_SNAPSHOTS:]:
        assert keep.name in surviving


def test_prune_with_keep_below_one_clamps(tmp_path):
    arr = _composite(2, 2)
    for i in range(3):
        take_snapshot(arr, target_dir=tmp_path, now=1700000000.0 + i)
    # keep=0 should clamp up to 1 to avoid wiping the directory entirely.
    prune_snapshots(target_dir=tmp_path, keep=0)
    assert len(list_snapshots(target_dir=tmp_path)) == 1


def test_clear_wipes_all_snapshots(tmp_path):
    arr = _composite(2, 2)
    for i in range(3):
        take_snapshot(arr, target_dir=tmp_path, now=1700000000.0 + i)
    deleted = clear_snapshots(target_dir=tmp_path)
    assert deleted == 3
    assert list_snapshots(target_dir=tmp_path) == []


# ---------------------------------------------------------------------------
# Workspace integration
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.stop_autosave()
    ws.deleteLater()


def test_take_snapshot_now_writes_file(workspace, tmp_path):
    layer = workspace.canvas().document().active_layer()
    layer.image[..., :3] = (123, 45, 67)
    workspace._autosave_target_dir = tmp_path  # noqa: SLF001
    out = workspace.take_autosave_snapshot_now()
    assert out is not None
    assert Path(out).exists()


def test_take_snapshot_now_returns_none_for_blank_document(workspace, tmp_path):
    document = workspace.canvas().document()
    document._layers.clear()  # noqa: SLF001
    document._composite_cache = None  # noqa: SLF001
    workspace._autosave_target_dir = tmp_path  # noqa: SLF001
    assert workspace.take_autosave_snapshot_now() is None


def test_restore_latest_pastes_into_canvas(workspace, tmp_path):
    arr = _composite(workspace.canvas().document().shape[0],
                     workspace.canvas().document().shape[1],
                     c=(180, 90, 45))
    take_snapshot(arr, target_dir=tmp_path, now=1700000000.0)
    ok = workspace.restore_latest_autosave(target_dir=tmp_path)
    assert ok is True
    layer = workspace.canvas().document().active_layer()
    # The active layer's pixels now match the autosaved image.
    assert int(layer.image[0, 0, 0]) == 180


def test_restore_latest_with_no_snapshot_returns_false(workspace, tmp_path):
    ok = workspace.restore_latest_autosave(target_dir=tmp_path)
    assert ok is False


def test_start_autosave_creates_timer(workspace, tmp_path):
    workspace.start_autosave(interval_sec=60, target_dir=tmp_path)
    assert hasattr(workspace, "_autosave_timer")
    assert workspace._autosave_timer.isActive()  # noqa: SLF001
    workspace.stop_autosave()
    assert not workspace._autosave_timer.isActive()  # noqa: SLF001


def test_start_autosave_replaces_existing_timer_interval(workspace, tmp_path):
    workspace.start_autosave(interval_sec=60, target_dir=tmp_path)
    first_interval = workspace._autosave_timer.interval()  # noqa: SLF001
    workspace.start_autosave(interval_sec=30, target_dir=tmp_path)
    second_interval = workspace._autosave_timer.interval()  # noqa: SLF001
    assert second_interval != first_interval
