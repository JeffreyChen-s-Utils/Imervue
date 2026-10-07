"""Reserve and rollback plugin-directory replacements without deleting a working install."""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from uuid import uuid4

from Imervue.image.output_policy import path_key

logger = logging.getLogger("Imervue.plugin.installation")
_lock = RLock()
_active: set[str] = set()


@contextmanager
def installation_stage(final: Path):
    """One installer per destination in this process; unique stage is cleaned on every exit."""
    with resource_reservation(path_key(final)):
        stage = Path(tempfile.mkdtemp(prefix=".imervue-plugin-", dir=final.parent))
        try:
            yield stage
        finally:
            if stage.exists():
                shutil.rmtree(stage)


@contextmanager
def resource_reservation(key: str):
    """Exclude concurrent installs of one plugin or one interpreter's package environment."""
    with _lock:
        if key in _active:
            raise FileExistsError(f"Installation already in progress: {key}")
        _active.add(key)
    try:
        yield
    finally:
        with _lock:
            _active.discard(key)


def commit_installation(stage: Path, final: Path, *, before_commit=None) -> None:
    """Preserve models/assets; rollback the old directory if the final replacement fails."""
    for name in ("models", "assets"):
        original = final / name
        if original.is_dir():
            shutil.copytree(original, stage / name, dirs_exist_ok=True)
    if before_commit is not None:
        before_commit()
    backup = final.with_name(f".imervue-backup-{uuid4().hex}")
    had_previous = final.exists()
    if had_previous:
        os.replace(final, backup)
    try:
        os.replace(stage, final)
    except OSError:
        if had_previous:
            os.replace(backup, final)
        raise
    if had_previous:
        try:
            shutil.rmtree(backup)
        except OSError:
            logger.warning("Committed plugin but could not remove backup %s", backup, exc_info=True)
