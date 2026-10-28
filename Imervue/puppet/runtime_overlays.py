"""Apply ordered expression overrides and exclusive pose selections."""
from __future__ import annotations

from Imervue.puppet.document import Expression, PuppetDocument


def apply_expression(
    values: dict[str, float], expression: Expression,
) -> dict[str, float]:
    """Apply ``expression``'s param overrides on top of ``values`` and
    return a new dict. Original values dict is not mutated.

    Modes per the v1 schema:
    * ``additive`` — final = base + value
    * ``multiply`` — final = base × value
    * ``overwrite`` — final = value (ignores base)
    """
    out = dict(values)
    for pp in expression.params:
        base = float(out.get(pp.id, 0.0))
        if pp.mode == "additive":
            out[pp.id] = base + float(pp.value)
        elif pp.mode == "multiply":
            out[pp.id] = base * float(pp.value)
        elif pp.mode == "overwrite":
            out[pp.id] = float(pp.value)
        else:
            out[pp.id] = base
    return out


def apply_expressions(
    values: dict[str, float], expressions: list[Expression],
) -> dict[str, float]:
    """Compose multiple expressions in list order (last writer wins on
    overlapping params)."""
    out = dict(values)
    for expr in expressions:
        out = apply_expression(out, expr)
    return out


def resolve_pose_visibility(
    document: PuppetDocument, active_per_group: dict[str, str],
) -> dict[str, bool]:
    """Build ``{drawable_id: visible}`` honouring pose-group exclusivity.

    For every group, the drawable named in ``active_per_group[group_id]``
    is visible and the rest of the group is hidden. Drawables not part
    of any group keep their authored ``visible`` flag.

    A group whose ``active_per_group`` entry is missing or invalid
    keeps its first member visible — matches the v1 schema's "exactly
    one drawable per group is shown" contract.
    """
    out = {d.id: bool(d.visible) for d in document.drawables}
    for group in document.pose_groups:
        active = active_per_group.get(group.id)
        if active not in group.drawables:
            active = group.drawables[0] if group.drawables else None
        for member in group.drawables:
            out[member] = (member == active)
    return out
