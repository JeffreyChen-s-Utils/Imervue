"""Helpers for resolving :attr:`Drawable.clip_mask` references.

The GL pass that actually writes the stencil buffer lives in
``canvas.paintGL`` (un-testable without a display). The bookkeeping —
"does this draw command have a valid mask, and which command provides
the mask geometry?" — is split out here so the runtime can validate it
and tests can assert against it without touching GL.

Live2D semantics matched here:

* A drawable can name *one* mask drawable by id. Missing ids are
  treated as "no mask" (the target draws unclipped) rather than as an
  error — the v1 schema documents ``clip_mask`` as optional, and a
  stale id should not crash the renderer.
* A mask drawable's own visibility / draw_order is independent of its
  role as a mask. The same drawable can be visible on screen *and*
  used by other drawables as a clip shape; the renderer just borrows
  its geometry for the stencil pass.
"""
from __future__ import annotations

from Imervue.puppet.render_prep import DrawCommand


def resolve_masks(
    draw_list: list[DrawCommand],
) -> dict[str, DrawCommand]:
    """Return ``{drawable_id: mask_command}`` for every command in
    ``draw_list`` whose ``clip_mask`` points at a drawable that's also
    in the list.

    Commands with no ``clip_mask`` are omitted. Commands whose
    ``clip_mask`` doesn't resolve are also omitted — callers loop over
    the returned dict, so an unresolved mask just means the target
    draws unclipped.
    """
    by_id = {cmd.drawable_id: cmd for cmd in draw_list}
    out: dict[str, DrawCommand] = {}
    for cmd in draw_list:
        if cmd.clip_mask is None:
            continue
        mask = by_id.get(cmd.clip_mask)
        if mask is None:
            continue
        if mask.drawable_id == cmd.drawable_id:
            # Self-mask is meaningless and would deadlock the stencil pass.
            continue
        out[cmd.drawable_id] = mask
    return out


def needs_stencil_buffer(draw_list: list[DrawCommand]) -> bool:
    """Cheap "should the canvas request stencil bits?" check. The
    canvas can short-circuit the stencil pass entirely on documents
    that don't use clipping."""
    return any(cmd.clip_mask is not None for cmd in draw_list)
