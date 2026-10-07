"""Auto-save + crash recovery for the Paint workspace.

The workspace queues immutable committed versions on background workers that
periodically write snapshots to a hidden
directory (``~/.imervue_autosave/`` by default). On the next
workspace open, :func:`pending_recovery_snapshots` returns any
snapshot not paired with a clean shutdown — those are the candidates
the workspace prompts the user to recover.

The serialisation format is the same NPZ bundle used by
:mod:`document_io` so a recovered snapshot loads through the
existing path. A side car ``.json`` file carries the metadata
(timestamp, project name, original-path hint) so the recovery
prompt can describe each snapshot.

Pure-Python plumbing: the timer that drives periodic writes lives
in the workspace's Qt layer; this module owns the
write/list/clean/find helpers so they stay testable without a Qt
event loop.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from Imervue.paint.document import PaintDocument
from Imervue.paint.document_io import (
    FILE_EXTENSION as NATIVE_DOCUMENT_EXTENSION,
)
from Imervue.paint.document_io import load_document, save_document
from Imervue.system.atomic_write import write_text_atomically
from Imervue.system.best_effort import best_effort

logger = logging.getLogger("Imervue")

AUTOSAVE_FILE_PREFIX = "snapshot-"
AUTOSAVE_META_SUFFIX = ".json"
AUTOSAVE_KEEP_MAX = 8       # keep at most N recent snapshots per document
AUTOSAVE_STALE_AGE_S = 86400 * 7   # 7 days; older snapshots are silently dropped
DEFAULT_INTERVAL_SEC = 120  # workspace's periodic snapshot cadence


@dataclass(frozen=True)
class AutoSaveSnapshot:
    """One on-disk snapshot — bundle path + metadata file."""

    bundle_path: Path
    meta_path: Path
    created_at: float
    project_name: str
    source_hint: str
    document_id: str = ""
    created_ns: int = 0

    @property
    def is_stale(self) -> bool:
        """True if the snapshot is older than the documented retention."""
        return (time.time() - float(self.created_at)) > AUTOSAVE_STALE_AGE_S


def default_autosave_dir() -> Path:
    """Return the platform-appropriate autosave directory.

    A hidden folder under the user's home directory. Caller can
    override via the explicit ``directory`` argument on every helper
    that takes one — the default is only used when no override is
    supplied.
    """
    return Path.home() / ".imervue_autosave"


def write_snapshot(
    document: PaintDocument,
    *,
    directory: str | Path | None = None,
    project_name: str = "Untitled",
    source_hint: str = "",
    document_id: str = "",
) -> AutoSaveSnapshot | None:
    """Write a fresh snapshot. Returns the snapshot or ``None`` on empty doc.

    Empty documents (no layers) are silently skipped — there's
    nothing to recover. The writer also rotates old snapshots in the
    document: if more than :data:`AUTOSAVE_KEEP_MAX` exist,
    the oldest are deleted to keep the directory size bounded.
    """
    if document.layer_count == 0:
        return None
    target_dir = Path(directory) if directory else default_autosave_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.time()
    created_ns = time.time_ns()
    base = f"{AUTOSAVE_FILE_PREFIX}{int(timestamp * 1000):015d}-{uuid.uuid4().hex}"
    bundle_path = target_dir / f"{base}{NATIVE_DOCUMENT_EXTENSION}"
    meta_path = target_dir / f"{base}{AUTOSAVE_META_SUFFIX}"
    save_document(document, bundle_path)
    try:
        write_text_atomically(meta_path, json.dumps({
            "created_at": timestamp,
            "project_name": project_name,
            "source_hint": source_hint,
            "document_id": document_id,
            "created_ns": created_ns,
        }))
    except OSError:
        with best_effort("remove incomplete autosave", logger):
            bundle_path.unlink(missing_ok=True)
        raise
    snapshot = AutoSaveSnapshot(
        bundle_path=bundle_path,
        meta_path=meta_path,
        created_at=timestamp,
        project_name=project_name,
        source_hint=source_hint,
        document_id=document_id,
        created_ns=created_ns,
    )
    _rotate_old_snapshots(target_dir, document_id)
    return snapshot


def list_snapshots(
    directory: str | Path | None = None,
) -> list[AutoSaveSnapshot]:
    """Return the snapshots in ``directory`` newest-first.

    Stale (>7 day-old) entries pass through; callers decide whether
    to filter them out via :attr:`AutoSaveSnapshot.is_stale`. Missing
    or unreadable metadata files are skipped silently.
    """
    target_dir = Path(directory) if directory else default_autosave_dir()
    if not target_dir.is_dir():
        return []
    out: list[AutoSaveSnapshot] = []
    for path in sorted(target_dir.glob(f"{AUTOSAVE_FILE_PREFIX}*{NATIVE_DOCUMENT_EXTENSION}")):
        meta_path = path.with_suffix(AUTOSAVE_META_SUFFIX)
        try:
            meta_raw = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(meta_raw, dict):
            continue
        try:
            created_at = float(meta_raw.get("created_at", path.stat().st_mtime))
        except (TypeError, ValueError):
            created_at = path.stat().st_mtime
        try:
            created_ns = int(meta_raw.get("created_ns", 0))
        except (TypeError, ValueError):
            created_ns = 0
        out.append(AutoSaveSnapshot(
            bundle_path=path,
            meta_path=meta_path,
            created_at=created_at,
            project_name=str(meta_raw.get("project_name", "Untitled")),
            source_hint=str(meta_raw.get("source_hint", "")),
            document_id=str(meta_raw.get("document_id", "")),
            created_ns=created_ns,
        ))
    out.sort(key=lambda s: (s.created_at, s.created_ns), reverse=True)
    return out


def pending_recovery_snapshots(
    directory: str | Path | None = None,
) -> list[AutoSaveSnapshot]:
    """Return snapshots the workspace should offer to recover.

    Currently identical to :func:`list_snapshots` except stale
    entries are filtered out. Future iterations could pair each
    snapshot with a "clean shutdown" marker; for now any non-stale
    snapshot is a recovery candidate.
    """
    return [snap for snap in list_snapshots(directory) if not snap.is_stale]


def recover_snapshot(snapshot: AutoSaveSnapshot) -> PaintDocument:
    """Load the document bundled in ``snapshot``."""
    try:
        return load_document(snapshot.bundle_path)
    except (zipfile.BadZipFile, EOFError, KeyError, TypeError) as exc:
        raise ValueError(f"damaged autosave: {snapshot.bundle_path.name}") from exc


def discard_snapshot(snapshot: AutoSaveSnapshot) -> bool:
    """Remove the bundle + metadata pair. Returns ``True`` if both
    files actually existed and were removed."""
    bundle_existed = snapshot.bundle_path.exists()
    meta_existed = snapshot.meta_path.exists()
    if bundle_existed:
        snapshot.bundle_path.unlink()
    if meta_existed:
        snapshot.meta_path.unlink()
    return bundle_existed and meta_existed


def clear_directory(directory: str | Path | None = None) -> int:
    """Remove every snapshot bundle + metadata pair in the directory.

    Returns the number of bundles removed. Useful for the
    "delete all auto-saves" command and for stale cleanup on
    workspace shutdown.
    """
    target_dir = Path(directory) if directory else default_autosave_dir()
    if not target_dir.is_dir():
        return 0
    removed = 0
    for snap in list_snapshots(target_dir):
        if discard_snapshot(snap):
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _rotate_old_snapshots(directory: Path, document_id: str = "") -> None:
    """Trim only this document's snapshots, preserving other documents."""
    snaps = [s for s in list_snapshots(directory) if s.document_id == document_id]
    overflow = snaps[AUTOSAVE_KEEP_MAX:]
    for snap in overflow:
        try:
            discard_snapshot(snap)
        except OSError:
            # Best-effort cleanup — never let a permission error during
            # rotation block the workspace.
            continue


def directory_size_bytes(directory: str | Path | None = None) -> int:
    """Sum of every file size in the autosave directory.

    Used by the workspace's "auto-save status" indicator so the user
    can see how much disk the snapshots take.
    """
    target_dir = Path(directory) if directory else default_autosave_dir()
    if not target_dir.is_dir():
        return 0
    total = 0
    for entry in target_dir.iterdir():
        try:
            total += entry.stat().st_size
        except OSError:
            continue
    return total


__all__ = [
    "AUTOSAVE_KEEP_MAX",
    "AUTOSAVE_STALE_AGE_S",
    "DEFAULT_INTERVAL_SEC",
    "AutoSaveSnapshot",
    "clear_directory",
    "default_autosave_dir",
    "directory_size_bytes",
    "discard_snapshot",
    "list_snapshots",
    "pending_recovery_snapshots",
    "recover_snapshot",
    "write_snapshot",
]
