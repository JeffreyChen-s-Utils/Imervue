"""Output and failed-folder paths for the in-process safety_review workers.

Where each censored image is written (in place, flat with a non-clobbering
``*_censored`` name, or mirrored under the scanned root), where a failed
original is copied, and the ``censor_failed.log`` manifest that lists why.
Re-exported by :mod:`safety_review._workers`.
"""
from __future__ import annotations

import os
from pathlib import Path


def _non_overwrite_destination(src: str, output_dir: str) -> str:
    """Build a non-clobbering ``*_censored`` destination path for *src*."""
    stem = Path(src).stem
    suffix = Path(src).suffix or ".png"
    dst = str(Path(output_dir) / f"{stem}_censored{suffix}")
    counter = 1
    while os.path.exists(dst):
        dst = str(Path(output_dir) / f"{stem}_censored_{counter}{suffix}")
        counter += 1
    return dst


def _relative_parent(src: str, source_root: str) -> str:
    """Relative subfolder of *src* under *source_root*.

    Returns ``""`` when *src* sits directly inside the root, when no root is
    given, or when *src* lies outside it (different drive / above the root),
    in which case the caller flattens instead of mirroring.
    """
    if not source_root:
        return ""
    try:
        rel = os.path.relpath(str(Path(src).parent), source_root)
    except ValueError:
        return ""  # different drive on Windows — cannot mirror
    if rel == os.curdir or rel.startswith(os.pardir):
        return ""
    return rel


def _mirrored_destination(src: str, output_dir: str, source_root: str) -> str:
    """Non-clobbering destination that mirrors *src*'s position under
    *source_root* into *output_dir*.

    A recursive scan keeps its subfolder tree instead of flattening every
    match into one directory (which would collide same-named images from
    different subfolders). Falls back to a flat destination when *src* is not
    under *source_root*.
    """
    rel_parent = _relative_parent(src, source_root)
    target_dir = Path(output_dir) / rel_parent if rel_parent else Path(output_dir)
    stem = Path(src).stem
    suffix = Path(src).suffix or ".png"
    dst = target_dir / f"{stem}_censored{suffix}"
    counter = 1
    while dst.exists():
        dst = target_dir / f"{stem}_censored_{counter}{suffix}"
        counter += 1
    return str(dst)


def _resolve_destination(src: str, output_dir: str | None, overwrite: bool,
                         source_root: str | None) -> str:
    """Pick the output path for *src*: in-place when overwriting, mirrored
    under *source_root* when set (recursive scan), else flat in *output_dir*."""
    if overwrite:
        return src
    if source_root:
        return _mirrored_destination(src, output_dir, source_root)
    return _non_overwrite_destination(src, output_dir)


def _failed_destination(src: str, failed_dir: str, scan_root: str | None) -> str:
    """Mirrored path for a failed image under *failed_dir*, keeping its name.

    Uses the same relative-parent logic as the output mirror so a failed
    image lands under the failed folder at the same subfolder position it had
    in the scanned tree.
    """
    rel = _relative_parent(src, scan_root or "")
    target_dir = Path(failed_dir) / rel if rel else Path(failed_dir)
    return str(target_dir / Path(src).name)


def _copy_failed(src: str, failed_dir: str, scan_root: str | None) -> None:
    """Copy a failed original into the mirrored failed folder (best-effort)."""
    import shutil
    dst = _failed_destination(src, failed_dir, scan_root)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _write_failed_manifest(failed_dir: str, failures: list[tuple[str, str]]) -> None:
    """Write a ``censor_failed.log`` listing each failed file and its reason,
    so the user can see *why* each image could not be processed."""
    manifest = Path(failed_dir) / "censor_failed.log"
    with open(manifest, "w", encoding="utf-8") as fh:
        for name, reason in failures:
            fh.write(f"{name}: {reason}\n")
