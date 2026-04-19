"""
RAW + JPEG stack grouping.

Photographers often shoot RAW+JPEG, producing two files per capture that
share a filename stem (``IMG_0001.CR2`` + ``IMG_0001.jpg``). Stacking
collapses them into a single tile: the JPEG is shown (decodes instantly),
and the RAW stays accessible as a sibling. This keeps the grid uncluttered
while preserving access to the master.
"""
from __future__ import annotations

from pathlib import Path

# RAW extensions we know about. Lowercase, with leading dot.
RAW_EXTENSIONS = frozenset({
    ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2",
    ".dng", ".raf", ".orf", ".rw2", ".pef", ".raw", ".x3f",
    ".erf", ".mef", ".mrw", ".kdc", ".dcr",
})

# Preview-style extensions that pair with RAW. Order matters — higher-index
# extensions win when multiple previews exist for the same stem.
PREVIEW_PRIORITY = (".jpg", ".jpeg", ".heic", ".heif", ".webp", ".tif", ".tiff", ".png")


def _stem_key(path: str) -> tuple[str, str]:
    """Return (parent, lowercase stem) identifying the stack bucket."""
    p = Path(path)
    return (str(p.parent), p.stem.lower())


def is_raw(path: str) -> bool:
    return Path(path).suffix.lower() in RAW_EXTENSIONS


def _preview_rank(path: str) -> tuple[int, str]:
    """Rank order for picking the best preview; higher index wins."""
    ext = Path(path).suffix.lower()
    idx = PREVIEW_PRIORITY.index(ext) if ext in PREVIEW_PRIORITY else -1
    return (idx, path)


def _choose_stack_preview(members: list[str]) -> str | None:
    """Return the chosen preview if ``members`` form a genuine RAW+preview stack."""
    if len(members) < 2:
        return None
    raws = [m for m in members if is_raw(m)]
    previews = [m for m in members if not is_raw(m)]
    if not raws or not previews:
        return None
    previews.sort(key=_preview_rank)
    return previews[-1]


def collapse_stacks(paths: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Group RAW+preview pairs sharing the same stem within a folder.

    Returns ``(collapsed_paths, stacks)`` where:
      - ``collapsed_paths`` preserves original ordering; for each stack, the
        preview file replaces all its siblings in-place at the first
        occurrence, and later siblings are dropped.
      - ``stacks`` maps the visible (preview) path to the full member list
        (preview first, then RAW originals) for later expansion in the UI.
    """
    buckets: dict[tuple[str, str], list[str]] = {}
    for p in paths:
        buckets.setdefault(_stem_key(p), []).append(p)

    stacks: dict[str, list[str]] = {}
    visible_for_key: dict[tuple[str, str], str] = {}
    for key, members in buckets.items():
        chosen = _choose_stack_preview(members)
        if chosen is None:
            continue
        stacks[chosen] = [chosen] + [m for m in members if m != chosen]
        visible_for_key[key] = chosen

    out: list[str] = []
    seen_keys: set[tuple[str, str]] = set()
    for p in paths:
        key = _stem_key(p)
        if key not in visible_for_key:
            out.append(p)
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        out.append(visible_for_key[key])
    return out, stacks
