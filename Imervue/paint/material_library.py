"""Material library — searchable index of reusable canvas tiles.

A "material" is any small reusable image the user wants to drop onto
a layer: a screentone, a paper texture, a fabric pattern, a brush
tip, a 3D-pose silhouette. MediBang ships a large built-in library;
Imervue mirrors the same model with a folder-backed index so users
can drop their own tiles into a configured directory and get them
listed automatically.

The module is Qt-free — it owns the index data structures and the
filesystem walk. The dock UI in :mod:`Imervue.paint.dock_panels`
consumes the index to build a thumbnail grid.

Categories
----------

The user-facing categories are deliberately coarse so a freshly
populated library doesn't need a taxonomy committee:

* ``texture`` — generic surface texture (paper, canvas, noise).
* ``tone`` — manga screentone (regular dots / lines / gradient).
* ``pattern`` — repeating motif (cloth, tile, scale).
* ``brush_tip`` — single-stamp PNG used as a custom brush tip.
* ``pose`` — 3D-pose silhouette / reference figure.

Adding a category is one tuple entry plus the matching translation
keys; nothing in the index logic hard-codes the names.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

MATERIAL_CATEGORIES = (
    "texture",
    "tone",
    "pattern",
    "brush_tip",
    "pose",
)
DEFAULT_CATEGORY = "texture"

_SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
_INDEX_FILENAME = "index.json"


@dataclass(frozen=True)
class MaterialEntry:
    """One material tile in the library.

    ``path`` is the absolute on-disk location; ``category`` is one of
    :data:`MATERIAL_CATEGORIES`; ``tags`` is a free-form keyword list
    used by the search box ("seamless", "halftone", "bricks"…).

    ``provider`` is an optional zero-arg callable that returns a numpy
    HxWx4 RGBA tile. When set, the entry is "procedural" — the dock
    calls the provider to render a preview and the canvas consumer
    calls it to materialise the tile. Procedural entries do NOT
    serialise via :meth:`to_dict` (callables are not JSON-friendly);
    they live only at runtime, regenerated from code on each boot.
    """

    name: str
    path: Path
    category: str = DEFAULT_CATEGORY
    tags: tuple[str, ...] = ()
    provider: Callable[[], np.ndarray] | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": str(self.path),
            "category": self.category,
            "tags": list(self.tags),
        }

    def is_procedural(self) -> bool:
        return self.provider is not None

    def render(self) -> np.ndarray | None:
        """Materialise the procedural tile, or ``None`` for path entries.

        Path-backed entries return ``None`` so the caller knows to
        load from ``path`` instead. Provider exceptions propagate so
        the caller can fall back to the placeholder tile.
        """
        if self.provider is None:
            return None
        return self.provider()

    @classmethod
    def from_dict(cls, raw: dict, *, root: Path | None = None) -> MaterialEntry:
        path_value = raw.get("path", "")
        path = Path(path_value)
        if root is not None and not path.is_absolute():
            path = root / path
        category = raw.get("category", DEFAULT_CATEGORY)
        if category not in MATERIAL_CATEGORIES:
            category = DEFAULT_CATEGORY
        raw_tags = raw.get("tags", ())
        if not isinstance(raw_tags, (list, tuple)):
            raw_tags = ()
        return cls(
            name=str(raw.get("name") or path.stem),
            path=path,
            category=category,
            tags=tuple(str(t) for t in raw_tags),
        )


@dataclass
class MaterialIndex:
    """Mutable in-memory index of :class:`MaterialEntry` rows.

    Built either from an explicit list or by walking a directory tree
    via :meth:`from_directory`. Persisted as JSON via :meth:`save_to`
    so a slow scan doesn't have to repeat at every workspace boot.
    """

    entries: list[MaterialEntry] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def categories(self) -> tuple[str, ...]:
        """Return the categories that actually have entries, in the
        canonical order. Empty categories drop out so the UI tab strip
        only shows tabs that contain something."""
        present = {entry.category for entry in self.entries}
        return tuple(cat for cat in MATERIAL_CATEGORIES if cat in present)

    def filter(
        self,
        *,
        category: str | None = None,
        query: str = "",
    ) -> list[MaterialEntry]:
        """Return entries matching ``category`` and ``query``.

        ``query`` is matched case-insensitively against the entry's
        name and tags — any whitespace-separated token must appear in
        either field. Empty query matches everything in the requested
        category (or every entry when ``category`` is ``None``).
        """
        tokens = [t.lower() for t in query.split() if t]

        def _matches(entry: MaterialEntry) -> bool:
            if category is not None and entry.category != category:
                return False
            if not tokens:
                return True
            haystack = " ".join((entry.name, *entry.tags)).lower()
            return all(token in haystack for token in tokens)

        return [entry for entry in self.entries if _matches(entry)]

    @classmethod
    def from_directory(
        cls, root: str | Path, *, default_category: str = DEFAULT_CATEGORY,
    ) -> MaterialIndex:
        """Walk ``root`` and build an index from every supported image.

        The category is inferred from the first directory component
        beneath ``root`` if it matches a known category; otherwise the
        entry takes ``default_category``. So a layout like ::

            <root>/tone/dot_60.png
            <root>/pattern/bricks.png
            <root>/my_custom/whatever.png

        produces ``tone`` / ``pattern`` / ``texture`` (the fallback)
        respectively. A non-existent / non-directory ``root`` yields
        an empty index — the caller doesn't have to pre-validate.
        """
        if default_category not in MATERIAL_CATEGORIES:
            raise ValueError(
                f"unknown default_category {default_category!r}; "
                f"expected one of {MATERIAL_CATEGORIES}",
            )
        root_path = Path(root)
        if not root_path.is_dir():
            return cls()
        entries: list[MaterialEntry] = []
        for path in sorted(root_path.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                continue
            try:
                rel_parts = path.relative_to(root_path).parts
            except ValueError:
                rel_parts = ()
            category = default_category
            if rel_parts and rel_parts[0] in MATERIAL_CATEGORIES:
                category = rel_parts[0]
            entries.append(
                MaterialEntry(
                    name=path.stem,
                    path=path.resolve(),
                    category=category,
                    tags=(),
                ),
            )
        return cls(entries=entries)

    def save_to(self, path: str | Path) -> None:
        """Persist the index to ``path`` as JSON."""
        out = {"entries": [entry.to_dict() for entry in self.entries]}
        Path(path).write_text(json.dumps(out, indent=2), encoding="utf-8")

    @classmethod
    def load_from(
        cls, path: str | Path, *, root: Path | None = None,
    ) -> MaterialIndex:
        """Read an index previously written by :meth:`save_to`.

        ``root`` lets the caller resolve relative paths inside the
        JSON against a known base directory (useful when the library
        moves location). Malformed entries are dropped silently — a
        hand-edited file should never crash workspace boot.
        """
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        rows = raw.get("entries", ())
        if not isinstance(rows, list):
            return cls()
        out: list[MaterialEntry] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                out.append(MaterialEntry.from_dict(row, root=root))
            except (TypeError, ValueError):
                continue
        return cls(entries=out)

    @classmethod
    def merged(cls, sources: Iterable[MaterialIndex]) -> MaterialIndex:
        """Concatenate several indices, de-duplicating by absolute path.

        First-seen wins so a user library that overrides a built-in
        material takes precedence when the user library is listed
        first. Path comparison uses ``resolve()`` so a symlink and its
        target collapse into a single row.
        """
        seen: set[Path] = set()
        merged: list[MaterialEntry] = []
        for source in sources:
            for entry in source.entries:
                key = entry.path.resolve() if entry.path.exists() else entry.path
                if key in seen:
                    continue
                seen.add(key)
                merged.append(entry)
        return cls(entries=merged)


def find_index_file(root: str | Path) -> Path:
    """Return the canonical index-file path for a library root."""
    return Path(root) / _INDEX_FILENAME


_PROCEDURAL_PATH_PREFIX = "procedural://"


def default_material_index() -> MaterialIndex:
    """Return the built-in catalog of procedural materials.

    Pulled from
    :data:`Imervue.paint.material_procedural.DEFAULT_PROCEDURAL_CATALOG`,
    so adding a tone / texture only requires editing that list — the
    library and dock pick up new entries on the next boot.

    Procedural entries use a synthetic ``procedural://<name>`` path
    sentinel so equality / dedup operations still work, but the path
    must never be stat'd (it does not exist on disk).
    """
    from Imervue.paint.material_procedural import DEFAULT_PROCEDURAL_CATALOG
    entries = [
        MaterialEntry(
            name=name,
            path=Path(f"{_PROCEDURAL_PATH_PREFIX}{name}"),
            category=category,
            tags=tags,
            provider=provider,
        )
        for name, category, tags, provider in DEFAULT_PROCEDURAL_CATALOG
    ]
    return MaterialIndex(entries=entries)
