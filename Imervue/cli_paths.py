"""CLI input selection, destination naming and traversal validation."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from Imervue.image.formats import RASTER_EXTENSIONS, RAW_EXTENSIONS
from Imervue.system.image_listing import list_images


_NO_INPUTS = "no input images found"


def iter_image_paths(inputs: Iterable[str], *, recursive: bool) -> list[Path]:
    """Expand *inputs* (files or directories) into a sorted list of image paths.

    A directory contributes its images without hidden files or, recursing,
    hidden folders (``list_images``); a file named outright is always kept.
    """
    found: list[Path] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            found.extend(Path(p) for p in list_images(str(path), RASTER_EXTENSIONS,
                                                      recursive=recursive))
        elif path.is_file():
            found.append(path)
    return sorted(set(found))


def output_path(src: Path, out_dir: str | None, suffix: str, ext: str | None) -> Path:
    """Resolve the destination path for *src* given --out / suffix / new extension.

    ``ext=None`` keeps the source's extension, except that a developed camera
    RAW is written as PNG: Pillow can't write RAW, and the bytes must match the name.
    """
    new_ext = ext if ext is not None else _kept_extension(src)
    if out_dir:
        return Path(out_dir) / f"{src.stem}{new_ext}"
    return src.with_name(f"{src.stem}{suffix}{new_ext}")


def _kept_extension(src: Path) -> str:
    return ".png" if src.suffix.lower() in RAW_EXTENSIONS else src.suffix


def _validated_out_dir(raw: str | None) -> Path | None:
    """Validate the user-supplied --out directory before any filesystem access.

    Rejects parent-traversal (``..``) segments so a crafted argument can't
    escape to an unexpected location (SonarQube python:S6547).
    """
    if not raw:
        return None
    return _checked_path(raw, message="--out must not contain '..' path segments")


def _checked_path(raw: str, *, message="path must not contain '..' segments") -> Path:
    """Return *raw* as a Path, rejecting parent-traversal segments (S6547)."""
    path = Path(raw)
    if ".." in path.parts:
        raise ValueError(message)
    return path


def _ensure_parent(out: Path) -> None:
    parent = out.parent
    if not parent.exists():
        # NOSONAR - parent derived from a validated (no '..') CLI path; writing
        # to a user-chosen location is the intended CLI behaviour.
        parent.mkdir(parents=True, exist_ok=True)  # NOSONAR
