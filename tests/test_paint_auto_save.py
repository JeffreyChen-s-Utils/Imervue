"""Tests for auto-save + crash recovery."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

from Imervue.paint.auto_save import (
    AUTOSAVE_KEEP_MAX,
    AUTOSAVE_STALE_AGE_S,
    AutoSaveSnapshot,
    clear_directory,
    default_autosave_dir,
    directory_size_bytes,
    discard_snapshot,
    list_snapshots,
    pending_recovery_snapshots,
    recover_snapshot,
    write_snapshot,
)
from Imervue.paint.document import PaintDocument


def _populated_document(h: int = 8, w: int = 8) -> PaintDocument:
    arr = np.full((h, w, 4), 200, dtype=np.uint8)
    doc = PaintDocument()
    doc.load_image(arr)
    return doc


# ---------------------------------------------------------------------------
# default_autosave_dir
# ---------------------------------------------------------------------------


def test_default_autosave_dir_under_home():
    """Default lives under the user's home directory so the snapshots
    aren't tied to the project working tree."""
    target = default_autosave_dir()
    assert target.name == ".imervue_autosave"
    assert target.parent.expanduser().exists()


# ---------------------------------------------------------------------------
# write_snapshot
# ---------------------------------------------------------------------------


def test_write_snapshot_creates_bundle_and_meta(tmp_path):
    snapshot = write_snapshot(
        _populated_document(),
        directory=tmp_path,
        project_name="My Comic",
        source_hint="/path/to/source.png",
    )
    assert snapshot is not None
    assert snapshot.bundle_path.exists()
    assert snapshot.meta_path.exists()
    assert snapshot.project_name == "My Comic"


def test_write_snapshot_skips_empty_document(tmp_path):
    """Empty docs have nothing to recover; they shouldn't create a
    snapshot file pair that would later prompt for restoration."""
    snapshot = write_snapshot(PaintDocument(), directory=tmp_path)
    assert snapshot is None
    assert list(tmp_path.iterdir()) == []


def test_write_snapshot_metadata_round_trips(tmp_path):
    snapshot = write_snapshot(
        _populated_document(), directory=tmp_path,
        project_name="Round", source_hint="hint",
    )
    raw = json.loads(snapshot.meta_path.read_text(encoding="utf-8"))
    assert raw["project_name"] == "Round"
    assert raw["source_hint"] == "hint"
    assert isinstance(raw["created_at"], (int, float))


def test_write_snapshot_creates_directory_if_missing(tmp_path):
    target = tmp_path / "fresh" / "nested"
    snapshot = write_snapshot(_populated_document(), directory=target)
    assert snapshot is not None
    assert target.is_dir()


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------


def test_rotation_caps_directory_at_keep_max(tmp_path):
    """Writing more than ``AUTOSAVE_KEEP_MAX`` snapshots must trim the
    oldest so the directory size stays bounded."""
    for i in range(AUTOSAVE_KEEP_MAX + 4):
        write_snapshot(
            _populated_document(), directory=tmp_path,
            project_name=f"Snap {i}",
        )
        time.sleep(0.002)   # ensure distinct millisecond timestamps
    snapshots = list_snapshots(tmp_path)
    assert len(snapshots) == AUTOSAVE_KEEP_MAX


# ---------------------------------------------------------------------------
# list_snapshots / pending_recovery_snapshots
# ---------------------------------------------------------------------------


def test_list_snapshots_empty_for_missing_directory(tmp_path):
    assert list_snapshots(tmp_path / "nope") == []


def test_list_snapshots_orders_newest_first(tmp_path):
    write_snapshot(_populated_document(), directory=tmp_path, project_name="old")
    time.sleep(0.005)
    write_snapshot(_populated_document(), directory=tmp_path, project_name="new")
    snaps = list_snapshots(tmp_path)
    assert [s.project_name for s in snaps] == ["new", "old"]


def test_list_snapshots_skips_orphan_meta(tmp_path):
    """A meta-file without a matching bundle must be ignored — no
    crash, no fake snapshot."""
    (tmp_path / "snapshot-001.json").write_text("{}", encoding="utf-8")
    assert list_snapshots(tmp_path) == []


def test_list_snapshots_skips_unparseable_meta(tmp_path):
    write_snapshot(_populated_document(), directory=tmp_path)
    # Corrupt the metadata so the JSON parser rejects it.
    bad = next(tmp_path.glob("snapshot-*.json"))
    bad.write_text("not json", encoding="utf-8")
    assert list_snapshots(tmp_path) == []


def test_pending_recovery_filters_out_stale(tmp_path):
    """Stale snapshots (>7 days old) are not offered for recovery."""
    snap = write_snapshot(_populated_document(), directory=tmp_path)
    # Rewrite the meta with an old timestamp.
    raw = json.loads(snap.meta_path.read_text(encoding="utf-8"))
    raw["created_at"] = time.time() - AUTOSAVE_STALE_AGE_S - 3600
    snap.meta_path.write_text(json.dumps(raw), encoding="utf-8")
    assert pending_recovery_snapshots(tmp_path) == []


# ---------------------------------------------------------------------------
# AutoSaveSnapshot.is_stale
# ---------------------------------------------------------------------------


def test_is_stale_true_when_older_than_retention():
    snap = AutoSaveSnapshot(
        bundle_path=Path("ignored"),
        meta_path=Path("ignored"),
        created_at=time.time() - AUTOSAVE_STALE_AGE_S - 1,
        project_name="x", source_hint="",
    )
    assert snap.is_stale


def test_is_stale_false_when_recent():
    snap = AutoSaveSnapshot(
        bundle_path=Path("ignored"),
        meta_path=Path("ignored"),
        created_at=time.time(),
        project_name="x", source_hint="",
    )
    assert not snap.is_stale


# ---------------------------------------------------------------------------
# recover_snapshot
# ---------------------------------------------------------------------------


def test_recover_snapshot_round_trips_pixels(tmp_path):
    src = _populated_document()
    snap = write_snapshot(src, directory=tmp_path)
    rebuilt = recover_snapshot(snap)
    np.testing.assert_array_equal(
        rebuilt.active_layer().image,
        src.active_layer().image,
    )


# ---------------------------------------------------------------------------
# discard_snapshot
# ---------------------------------------------------------------------------


def test_discard_removes_both_files(tmp_path):
    snap = write_snapshot(_populated_document(), directory=tmp_path)
    assert discard_snapshot(snap) is True
    assert not snap.bundle_path.exists()
    assert not snap.meta_path.exists()


def test_discard_returns_false_when_nothing_to_remove(tmp_path):
    """Calling discard on a snapshot whose files were already cleared
    must return False rather than raising — the workspace can use
    this as a 'were you the one who removed it?' check."""
    snap = AutoSaveSnapshot(
        bundle_path=tmp_path / "ghost.imervue",
        meta_path=tmp_path / "ghost.json",
        created_at=time.time(),
        project_name="ghost", source_hint="",
    )
    assert discard_snapshot(snap) is False


# ---------------------------------------------------------------------------
# clear_directory
# ---------------------------------------------------------------------------


def test_clear_directory_removes_all_pairs(tmp_path):
    write_snapshot(_populated_document(), directory=tmp_path, project_name="a")
    time.sleep(0.005)
    write_snapshot(_populated_document(), directory=tmp_path, project_name="b")
    removed = clear_directory(tmp_path)
    assert removed == 2
    assert list_snapshots(tmp_path) == []


def test_clear_directory_returns_zero_for_missing(tmp_path):
    assert clear_directory(tmp_path / "absent") == 0


# ---------------------------------------------------------------------------
# directory_size_bytes
# ---------------------------------------------------------------------------


def test_directory_size_returns_zero_for_missing(tmp_path):
    assert directory_size_bytes(tmp_path / "absent") == 0


def test_directory_size_grows_with_snapshots(tmp_path):
    before = directory_size_bytes(tmp_path)
    write_snapshot(_populated_document(64, 64), directory=tmp_path)
    after = directory_size_bytes(tmp_path)
    assert after > before


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_keep_max_is_at_least_two():
    """The rotation cap must leave at least one previous snapshot in
    place after the rolling cleanup so a crash mid-write doesn't
    drop the only recoverable state."""
    assert AUTOSAVE_KEEP_MAX >= 2


def test_stale_age_is_a_meaningful_window():
    """At least a day so a user who returns after a long weekend
    still sees their work in the recovery prompt."""
    assert AUTOSAVE_STALE_AGE_S >= 86400


# ---------------------------------------------------------------------------
# Integration: rotation + recovery
# ---------------------------------------------------------------------------


def test_recovery_after_rotation_loads_most_recent_pixels(tmp_path):
    """After rotation only the latest snapshots survive; recovering
    the newest must give back the most-recent pixel state."""
    last_doc = None
    for i in range(AUTOSAVE_KEEP_MAX + 2):
        last_doc = _populated_document()
        last_doc.active_layer().image[0, 0] = (i, i, i, 255)
        write_snapshot(last_doc, directory=tmp_path)
        time.sleep(0.002)
    pending = pending_recovery_snapshots(tmp_path)
    assert pending
    # Newest is first; recovering it must give back the i=last colour.
    expected = last_doc.active_layer().image[0, 0]
    rebuilt = recover_snapshot(pending[0])
    np.testing.assert_array_equal(rebuilt.active_layer().image[0, 0], expected)


# ---------------------------------------------------------------------------
# Sanity: empty document path returns None
# ---------------------------------------------------------------------------


def test_empty_document_emits_no_pending_recovery(tmp_path):
    write_snapshot(PaintDocument(), directory=tmp_path)
    assert pending_recovery_snapshots(tmp_path) == []


# ---------------------------------------------------------------------------
# Pytest hygiene — make sure the autouse user-settings fixture
# (which writes nothing here) doesn't interfere.
# ---------------------------------------------------------------------------


def test_marker_used_only_for_collection(tmp_path):
    """Sanity check that the test file itself imports and runs."""
    assert tmp_path.is_dir()


@pytest.fixture
def _autosave_dir(tmp_path):
    return tmp_path / "autosaves"
