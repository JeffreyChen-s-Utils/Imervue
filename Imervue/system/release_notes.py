"""Release-notes registry for the What's-New dialog.

A flat, version-keyed list — newest version first — drives both the
``Help > What's New`` menu entry and the auto-popup that appears on the
first launch after an upgrade.

Each entry is a small dataclass so the structure stays explicit and
contributors don't need to remember key names. ``RELEASE_HISTORY`` is
the single source of truth — keep it newest-first; the dialog never
reorders the list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version


@dataclass(frozen=True)
class ReleaseEntry:
    """One application version's user-facing changelog."""

    version: str
    bullets: list[str] = field(default_factory=list)


# Newest first. Keep bullet text user-facing — "added X" rather than
# "refactored Y to use Z". Internal cleanup belongs in the commit log.
RELEASE_HISTORY: list[ReleaseEntry] = [
    ReleaseEntry(
        version="1.0.28",
        bullets=[
            "Recycle Bin dialog — restore or permanently delete pending"
            " soft-deletions one item at a time.",
            "Stacked layer system — text / image / LUT layers with normal /"
            " multiply / screen / overlay blending.",
            "Adjustable UI scale (80–200%) and GPU tile-cache VRAM cap from"
            " File > Preferences.",
            "Recursive watchdog auto-refreshes the file tree when external"
            " tools change the folder.",
        ],
    ),
]


def current_app_version() -> str:
    """Return the installed Imervue version, or "0.0.0" when unavailable."""
    try:
        return version("Imervue")
    except PackageNotFoundError:
        return "0.0.0"


def latest_release() -> ReleaseEntry | None:
    """Return the newest release entry, or ``None`` if the registry is empty."""
    return RELEASE_HISTORY[0] if RELEASE_HISTORY else None


def releases_since(seen_version: str) -> list[ReleaseEntry]:
    """Return the entries the user has not yet acknowledged.

    Comparison is by tuple-of-int parsing — "1.0.28" > "1.0.27". Versions
    with non-numeric segments fall back to lexicographic comparison so
    pre-release tags (e.g. "1.0.29-rc1") still order roughly correctly.
    """
    seen_key = _parse_version_key(seen_version)
    out = []
    for entry in RELEASE_HISTORY:
        if _parse_version_key(entry.version) > seen_key:
            out.append(entry)
    return out


def _parse_version_key(value: str) -> tuple:
    """Return a sortable key for a version string.

    Each segment is wrapped as ``(0, int)`` for numeric parts or
    ``(1, str)`` for tagged parts so that all keys have a uniform shape
    and remain orderable. Empty input returns an empty tuple, which
    compares less than any populated key.
    """
    if not value:
        return ()
    parts = value.split(".")
    key = []
    for p in parts:
        head = p.split("-", 1)[0]
        try:
            key.append((0, int(head)))
        except ValueError:
            key.append((1, p))
    return tuple(key)
