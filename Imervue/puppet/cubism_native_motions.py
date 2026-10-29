"""Motion collection for the native Cubism conversion.

Loads the motions a ``.model3.json`` references (group, fades, sound)
and sweeps ``motions/`` for the ones the manifest forgot. Split out of
:mod:`puppet.cubism_native_convert`, which re-exports every name.
"""
from __future__ import annotations

import logging
from pathlib import Path

from Imervue.puppet.cubism_import import CubismBundle, load_motion3
from Imervue.puppet.document import Motion

# Same logger as the converter, so its records keep their source name.
logger = logging.getLogger("Imervue.plugin.puppet.cubism_native_convert")


def _load_referenced_motion(
    base_dir: Path, group_name: str, entry: dict,
) -> tuple[Motion, Path] | None:
    """Resolve and load one entry from the manifest's ``Motions``
    map. Returns ``(motion, resolved_path)`` so the caller can both
    collect the motion and track which files were already consumed.
    Returns ``None`` for missing files or malformed entries."""
    file_ref = entry.get("File")
    if not isinstance(file_ref, str) or not file_ref:
        return None
    path = base_dir / file_ref
    if not path.is_file():
        logger.info("motion %s missing — skipping", path)
        return None
    stem = Path(file_ref).stem.removesuffix(".motion3")
    motion = load_motion3(path, name=f"{group_name}/{stem}")
    motion.group = str(group_name)
    fade_in = entry.get("FadeInTime")
    fade_out = entry.get("FadeOutTime")
    if isinstance(fade_in, int | float):
        motion.fade_in_duration = float(fade_in)
    if isinstance(fade_out, int | float):
        motion.fade_out_duration = float(fade_out)
    sound_ref = entry.get("Sound")
    if isinstance(sound_ref, str) and sound_ref:
        motion.sound_path = str(base_dir / sound_ref)
    return motion, path.resolve()


def _collect_manifest_motions(
    bundle: CubismBundle, file_refs: dict, base_dir: Path,
) -> set[Path]:
    """Walk ``FileReferences.Motions`` and append every entry that
    resolves. Returns the set of resolved paths so the orphan-sweep
    can skip duplicates."""
    seen: set[Path] = set()
    for group_name, entries in (file_refs.get("Motions") or {}).items():
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            loaded = _load_referenced_motion(base_dir, group_name, entry)
            if loaded is None:
                continue
            motion, resolved = loaded
            bundle.motions.append(motion)
            seen.add(resolved)
    return seen


def _collect_orphan_motions(
    bundle: CubismBundle, base_dir: Path, already_seen: set[Path],
) -> None:
    """Real-world Cubism bundles often ship motions the manifest
    forgot — sweep ``motions/`` and pick up anything not already
    consumed. Default the group to ``Idle`` with a half-second
    cross-fade."""
    extra_root = base_dir / "motions"
    if not extra_root.is_dir():
        return
    for path in sorted(extra_root.glob("*.motion3.json")):
        if path.resolve() in already_seen:
            continue
        stem = path.stem.removesuffix(".motion3")
        motion = load_motion3(path, name=stem)
        motion.group = "Idle"
        motion.fade_in_duration = 0.5
        motion.fade_out_duration = 0.5
        bundle.motions.append(motion)
