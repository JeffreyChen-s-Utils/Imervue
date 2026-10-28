"""Accumulate visibility and opacity through the authored part hierarchy."""
from __future__ import annotations

from Imervue.puppet.document import Part, PuppetDocument


def resolve_part_state(
    document: PuppetDocument,
) -> dict[str, tuple[bool, float]]:
    """Walk the Part tree and return ``{drawable_id: (visible, opacity)}``.

    A drawable inherits the AND of every ancestor's ``visible`` flag
    and the product of every ancestor's ``opacity``. Drawables not
    listed under any Part get ``(True, 1.0)`` so a document without a
    Part tree behaves exactly like before.

    Each drawable's own ``visible`` and ``opacity`` are *not* combined
    here — those live on the drawable itself and the caller still
    consults them. ``resolve_part_state`` only contributes the
    hierarchy-level multiplier."""
    out: dict[str, tuple[bool, float]] = {
        d.id: (True, 1.0) for d in document.drawables
    }
    if not document.parts:
        return out
    by_id = {part.id: part for part in document.parts}
    parents = _find_root_parts(document.parts)
    for root in parents:
        _walk_part(root, by_id, parent_visible=True, parent_opacity=1.0, out=out)
    return out


def _find_root_parts(parts: list[Part]) -> list[Part]:
    """Roots are Parts not referenced as a child of any other Part —
    they sit at the top of the tree."""
    referenced: set[str] = set()
    for part in parts:
        referenced.update(part.children)
    return [p for p in parts if p.id not in referenced]


def _walk_part(
    part: Part,
    by_id: dict[str, Part],
    *,
    parent_visible: bool,
    parent_opacity: float,
    out: dict[str, tuple[bool, float]],
    visited: set[str] | None = None,
) -> None:
    """Depth-first traverse. ``visited`` guards against cycles (a
    malformed document where Part A lists Part B as a child and vice
    versa would otherwise stack-overflow)."""
    if visited is None:
        visited = set()
    if part.id in visited:
        return
    visited.add(part.id)
    effective_visible = parent_visible and bool(part.visible)
    effective_opacity = float(parent_opacity) * float(part.opacity)
    for drawable_id in part.drawables:
        if drawable_id not in out:
            continue
        prev_visible, prev_opacity = out[drawable_id]
        out[drawable_id] = (
            prev_visible and effective_visible,
            prev_opacity * effective_opacity,
        )
    for child_id in part.children:
        child = by_id.get(child_id)
        if child is None:
            continue
        _walk_part(
            child, by_id,
            parent_visible=effective_visible,
            parent_opacity=effective_opacity,
            out=out, visited=visited,
        )
