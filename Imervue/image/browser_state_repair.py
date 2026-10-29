"""Missing-file detection, repair matching and load-error classification."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def missing_paths(paths: Iterable[str]) -> list[str]:
    return [path for path in paths if not Path(path).exists()]


def remove_missing(paths: Iterable[str]) -> list[str]:
    return [path for path in paths if Path(path).exists()]


def auto_match_same_name(missing: Iterable[str], folder: str) -> dict[str, str]:
    """Pair missing paths with files of the same basename in *folder*."""
    root = Path(folder)
    if not root.is_dir():
        return {}
    by_name: dict[str, str] = {}
    for child in root.iterdir():
        if child.is_file():
            by_name.setdefault(child.name.lower(), str(child))
    return {
        old: by_name[Path(old).name.lower()]
        for old in missing
        if Path(old).name.lower() in by_name
    }


def relocate_root(paths: Iterable[str], old_root: str, new_root: str) -> dict[str, str]:
    """Map missing files from *old_root* to an equivalent path below *new_root*."""
    old_base = Path(old_root)
    new_base = Path(new_root)
    out: dict[str, str] = {}
    for raw in paths:
        path = Path(raw)
        try:
            rel = path.relative_to(old_base)
        except ValueError:
            rel = Path(path.name)
        candidate = new_base / rel
        if candidate.exists():
            out[raw] = str(candidate)
    return out


def is_missing_file_error(message: str) -> bool:
    """FileNotFoundError-style messages → the quiet 'Missing' tile state.

    Distinguishes a vanished file (unplugged drive, deleted / moved image)
    from a genuine decode failure so the wall shows 'Missing' instead of a
    red 'Load failed' panel and skips the pointless retry."""
    text = (message or "").lower()
    return any(
        token in text
        for token in (
            "no such file or directory",
            "cannot find the file",
            "cannot find the path",
            "file not found",
            "does not exist",
        )
    )


def is_transient_load_error(message: str) -> bool:
    text = (message or "").lower()
    return any(
        token in text
        for token in (
            "being used",
            "locked",
            "permission",
            "temporarily",
            "resource busy",
            "busy",
            "access is denied",
            "cannot access",
        )
    )

