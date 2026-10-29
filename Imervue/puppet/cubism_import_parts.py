"""Cubism ``.pose3.json`` and ``.cdi3.json`` importers: mutually exclusive
part groups and the display names of parameters, groups and parts."""
from __future__ import annotations

from pathlib import Path

from Imervue.puppet.cubism_import_common import CubismFormatError, _read_json
from Imervue.puppet.document import PoseGroup


# ---------------------------------------------------------------------------
# .pose3.json
# ---------------------------------------------------------------------------


def load_pose3(path: str | Path) -> list[PoseGroup]:
    """Parse a Cubism ``.pose3.json`` into a list of :class:`PoseGroup`.

    Cubism's ``Groups`` field is a 2-D structure: each top-level entry
    is a mutually-exclusive set, each item inside it represents one
    alternative with its primary id plus a list of secondary
    ``Link`` ids. We collapse this to one :class:`PoseGroup` per
    mutex set whose ``drawables`` includes both the primary and any
    Link ids — when the runtime picks one primary as active, every
    drawable in its row gets shown together, which approximates
    Cubism's "show this part *and* its dependencies" behaviour."""
    raw = _read_json(Path(path))
    if raw.get("Type") not in (None, "Live2D Pose"):
        raise CubismFormatError(
            f"{path} Type {raw.get('Type')!r} is not 'Live2D Pose'",
        )
    groups_raw = raw.get("Groups") or []
    out: list[PoseGroup] = []
    for idx, group in enumerate(groups_raw):
        if not isinstance(group, list):
            continue
        drawables = _pose_group_drawables(group)
        if not drawables:
            continue
        out.append(PoseGroup(id=f"pose_group_{idx}", drawables=drawables))
    return out


def _pose_group_drawables(group: list) -> list[str]:
    drawables: list[str] = []
    for item in group:
        if not isinstance(item, dict):
            continue
        primary = item.get("Id")
        if isinstance(primary, str) and primary:
            drawables.append(primary)
        for link in item.get("Link") or []:
            if isinstance(link, str) and link:
                drawables.append(link)
    return drawables


# ---------------------------------------------------------------------------
# .cdi3.json
# ---------------------------------------------------------------------------


def load_cdi3(path: str | Path) -> dict[str, str]:
    """Parse a Cubism ``.cdi3.json`` display-info file into a
    ``{id: name}`` mapping covering parameters, parameter groups,
    and parts. The :class:`PuppetDocument.display_names` field
    consumes this directly."""
    raw = _read_json(Path(path))
    out: dict[str, str] = {}
    for section in ("Parameters", "ParameterGroups", "Parts"):
        for entry in raw.get(section) or []:
            if not isinstance(entry, dict):
                continue
            id_ = entry.get("Id")
            name = entry.get("Name")
            if isinstance(id_, str) and isinstance(name, str) and name:
                out[id_] = name
    return out
