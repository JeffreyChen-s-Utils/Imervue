"""
Staging Tray — cross-folder selection basket.

Persists across restarts in ``user_setting_dict["staging_tray"]``. Callers
treat the tray as an ordered, de-duplicated list of absolute paths.
"""
from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

from Imervue.user_settings.user_setting_dict import schedule_save, user_setting_dict


def _tray() -> list[str]:
    lst = user_setting_dict.get("staging_tray")
    if not isinstance(lst, list):
        lst = []
        user_setting_dict["staging_tray"] = lst
    return lst


def get_all() -> list[str]:
    """Return a copy of the current tray contents."""
    return list(_tray())


def count() -> int:
    return len(_tray())


def contains(path: str) -> bool:
    return path in _tray()


def add(path: str) -> bool:
    tray = _tray()
    if not path or path in tray:
        return False
    tray.append(path)
    schedule_save()
    return True


def add_many(paths: Iterable[str]) -> int:
    tray = _tray()
    added = 0
    for p in paths:
        if p and p not in tray:
            tray.append(p)
            added += 1
    if added:
        schedule_save()
    return added


def remove(path: str) -> bool:
    tray = _tray()
    if path not in tray:
        return False
    tray.remove(path)
    schedule_save()
    return True


def clear() -> None:
    tray = _tray()
    if tray:
        tray.clear()
        schedule_save()


def move_all(dest: str) -> tuple[int, int]:
    """Move every tray entry to ``dest``. Returns ``(moved, failed)``."""
    return _apply_file_op(dest, move=True)


def copy_all(dest: str) -> tuple[int, int]:
    """Copy every tray entry to ``dest``. Returns ``(copied, failed)``."""
    return _apply_file_op(dest, move=False)


def _apply_file_op(dest: str, *, move: bool) -> tuple[int, int]:
    dest_path = Path(dest)
    if not dest_path.is_dir():
        raise NotADirectoryError(dest)
    ok = failed = 0
    moved_paths: list[str] = []
    for src in _tray():
        target = dest_path / Path(src).name
        try:
            if move:
                shutil.move(src, str(target))
                moved_paths.append(src)
            else:
                shutil.copy2(src, str(target))
            ok += 1
        except Exception:  # noqa: BLE001
            failed += 1
    if move and moved_paths:
        tray = _tray()
        for p in moved_paths:
            if p in tray:
                tray.remove(p)
        schedule_save()
    return ok, failed
