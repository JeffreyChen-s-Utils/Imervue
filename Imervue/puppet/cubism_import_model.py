"""Entry readers for a Cubism ``.model3.json``: referenced motions and
expressions resolved against the model directory, parameter groups and
hit areas. :func:`puppet.cubism_import.load_model3` assembles them."""
from __future__ import annotations

from pathlib import Path

from Imervue.puppet.cubism_import_motion import load_exp3, load_motion3
from Imervue.puppet.document import Expression, HitArea, Motion


def _load_motion_entry(
    base: Path, group_name: str, entry: object,
) -> Motion | None:
    """Resolve and load a single ``Motions[group][i]`` entry. Returns
    ``None`` for malformed / missing-File entries."""
    if not isinstance(entry, dict):
        return None
    file_ref = entry.get("File")
    if not file_ref:
        return None
    motion_path = base / file_ref
    # Real Cubism rigs ship multiple motions per group sharing the
    # group name as a prefix in the file name (idle_01.motion3.json
    # etc.); surfacing the file stem keeps that intent without
    # collapsing all of them under "Idle_0" / "Idle_1".
    real_name = Path(file_ref).stem.removesuffix(".motion3")
    motion = load_motion3(motion_path, name=f"{group_name}/{real_name}")
    motion.group = str(group_name)
    # FadeInTime / FadeOutTime on the model3 reference override the
    # motion3's own values when present — matches Cubism's rule.
    fade_in = entry.get("FadeInTime")
    fade_out = entry.get("FadeOutTime")
    if isinstance(fade_in, int | float):
        motion.fade_in_duration = float(fade_in)
    if isinstance(fade_out, int | float):
        motion.fade_out_duration = float(fade_out)
    sound_ref = entry.get("Sound")
    if isinstance(sound_ref, str) and sound_ref:
        motion.sound_path = str(base / sound_ref)
    return motion


def _load_referenced_motions(base: Path, motions_raw: dict) -> list[Motion]:
    out: list[Motion] = []
    for group_name, entries in motions_raw.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            motion = _load_motion_entry(base, group_name, entry)
            if motion is not None:
                out.append(motion)
    return out


def _load_referenced_expressions(base: Path, exprs_raw: list) -> list[Expression]:
    out: list[Expression] = []
    for entry in exprs_raw:
        if not isinstance(entry, dict):
            continue
        file_ref = entry.get("File")
        if not file_ref:
            continue
        name = entry.get("Name") or Path(file_ref).stem.removesuffix(".exp3")
        out.append(load_exp3(base / file_ref, name=str(name)))
    return out


def _parse_groups(groups_raw: list) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for group in groups_raw:
        if not isinstance(group, dict):
            continue
        if group.get("Target") != "Parameter":
            continue
        name = group.get("Name")
        ids = group.get("Ids")
        if isinstance(name, str) and isinstance(ids, list):
            out[name] = [str(i) for i in ids]
    return out


def _parse_hit_areas(hit_raw: list) -> list[HitArea]:
    """Cubism ``HitAreas`` point at drawable ids that only exist inside
    the original ``.moc3``. We store the id anyway so the workspace
    can match them against rig drawables sharing the same name (often
    the case when the user names their PSD layers after the Cubism
    rig's part ids)."""
    out: list[HitArea] = []
    for entry in hit_raw:
        if not isinstance(entry, dict):
            continue
        drawable_id = entry.get("Id")
        name = entry.get("Name") or drawable_id
        if not isinstance(drawable_id, str):
            continue
        out.append(HitArea(id=str(name), drawables=[str(drawable_id)]))
    return out
