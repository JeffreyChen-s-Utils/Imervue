"""Pure helpers behind the Tags & Albums dialog and its right-click submenus.

No Qt: list-row labels, the stripped answer of a name prompt, the files a
"Show in Viewer" may load, the member paths that still exist, and the
summary the **Clean Up…** question shows. File checks are passed in, so the
tests drive them with plain predicates. The translation keys and fallbacks the
dialog and the submenus share live here so each literal appears once.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from Imervue.user_settings.tag_validator import CleanupPlan

TAG_CREATE = "tag_create"
TAG_CREATE_PROMPT = "tag_create_prompt"
ALBUM_CREATE = "album_create"
ALBUM_CREATE_PROMPT = "album_create_prompt"
RENAME_FALLBACK = "Rename"
TAG_CREATE_FALLBACK = "New Tag"
ALBUM_CREATE_FALLBACK = "New Album"
TAG_NAME_FALLBACK = "Tag name:"
ALBUM_NAME_FALLBACK = "Album name:"


def _path_is_file(path: str) -> bool:
    return Path(path).is_file()


def _path_exists(path: str) -> bool:
    return Path(path).exists()


def entered_name(text: str, ok: bool) -> str | None:
    """The stripped answer of a name prompt, or None when cancelled or blank."""
    if not ok:
        return None
    return text.strip() or None


def collection_rows(collection: Mapping[str, list[str]]) -> list[tuple[str, str]]:
    """``(label, name)`` per entry in name order; the label shows the image count."""
    return [(f"{name}  ({len(paths)})", name) for name, paths in sorted(collection.items())]


def viewable_images(
    paths: Iterable[str], is_file: Callable[[str], bool] = _path_is_file,
) -> list[str]:
    """The paths that are still files, in their original order."""
    return [path for path in paths if is_file(path)]


def existing_member_paths(
    *collections: Mapping[str, list[str]], exists: Callable[[str], bool] = _path_exists,
) -> set[str]:
    """Every member path of *collections* that still exists on disk."""
    paths = {p for coll in collections for members in coll.values() for p in members}
    return {p for p in paths if exists(p)}


def cleanup_summary(plans: Iterable[CleanupPlan]) -> tuple[int, list[str]]:
    """Total entries of missing files and one ``"source → target"`` line per merge."""
    plans = list(plans)
    merges = [f"{src} → {dst}" for plan in plans for src, dst in plan.merges]
    return sum(plan.orphans for plan in plans), merges
