"""Resolve parent-first deformer application order, including cycles."""
from __future__ import annotations

from Imervue.puppet.document import Deformer


def topologically_sorted_deformers(
    deformers: list[Deformer],
) -> list[Deformer]:
    """Return ``deformers`` in an order where each deformer appears
    after its :attr:`Deformer.parent`.

    Cycles (a malformed document where two deformers list each other
    as parent) are broken by stopping the walk at the second visit —
    the first-seen order wins, the runtime stays defined.
    """
    by_id = {d.id: d for d in deformers}
    visited: set[str] = set()
    ordered: list[Deformer] = []

    def _visit(deformer: Deformer, in_progress: set[str]) -> None:
        if deformer.id in visited or deformer.id in in_progress:
            return
        in_progress.add(deformer.id)
        parent_id = deformer.parent
        if parent_id and parent_id in by_id:
            _visit(by_id[parent_id], in_progress)
        in_progress.discard(deformer.id)
        if deformer.id not in visited:
            visited.add(deformer.id)
            ordered.append(deformer)

    for deformer in deformers:
        _visit(deformer, set())
    return ordered
