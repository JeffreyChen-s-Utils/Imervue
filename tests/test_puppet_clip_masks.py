"""Tests for the clip-mask resolver helper.

The GL stencil pass itself isn't testable without a display (it lives
under ``pragma: no cover`` like the rest of paintGL), but the
bookkeeping — "which drawables clip to which masks, and which masked
references are stale" — is pure-Python and lives in
``puppet.clip_masks``.
"""
from __future__ import annotations

import numpy as np

from puppet.clip_masks import needs_stencil_buffer, resolve_masks
from puppet.render_prep import DrawCommand


def _cmd(drawable_id: str, *, clip_mask: str | None = None) -> DrawCommand:
    return DrawCommand(
        drawable_id=drawable_id,
        texture=f"textures/{drawable_id}.png",
        vertices=np.zeros((3, 2), dtype=np.float32),
        uvs=np.zeros((3, 2), dtype=np.float32),
        indices=np.array([0, 1, 2], dtype=np.uint32),
        blend_mode="normal",
        clip_mask=clip_mask,
        visible=True,
        opacity=1.0,
    )


def test_resolve_masks_returns_empty_when_no_clip_mask_set():
    cmds = [_cmd("a"), _cmd("b")]
    assert resolve_masks(cmds) == {}


def test_resolve_masks_pairs_target_with_mask():
    cmds = [_cmd("face"), _cmd("eye_l", clip_mask="face")]
    pairs = resolve_masks(cmds)
    assert set(pairs.keys()) == {"eye_l"}
    assert pairs["eye_l"].drawable_id == "face"


def test_resolve_masks_drops_unresolved_references():
    """A clip_mask pointing at a drawable not in the draw list mustn't
    crash — the target just renders unclipped."""
    cmds = [_cmd("eye_l", clip_mask="ghost_face")]
    assert resolve_masks(cmds) == {}


def test_resolve_masks_ignores_self_reference():
    """A drawable claiming itself as its own mask would deadlock the
    stencil pass — it has to be filtered out."""
    cmds = [_cmd("circular", clip_mask="circular")]
    assert resolve_masks(cmds) == {}


def test_resolve_masks_handles_multiple_targets_sharing_mask():
    cmds = [
        _cmd("face"),
        _cmd("eye_l", clip_mask="face"),
        _cmd("eye_r", clip_mask="face"),
        _cmd("mouth", clip_mask="face"),
    ]
    pairs = resolve_masks(cmds)
    assert set(pairs.keys()) == {"eye_l", "eye_r", "mouth"}
    assert all(v.drawable_id == "face" for v in pairs.values())


def test_needs_stencil_buffer_false_on_empty():
    assert needs_stencil_buffer([]) is False


def test_needs_stencil_buffer_false_when_no_clip_mask():
    assert needs_stencil_buffer([_cmd("a"), _cmd("b")]) is False


def test_needs_stencil_buffer_true_when_any_clip_mask():
    cmds = [_cmd("a"), _cmd("b", clip_mask="a")]
    assert needs_stencil_buffer(cmds) is True
