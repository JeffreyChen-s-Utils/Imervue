"""Auto-symmetrize across the X axis.

Mirrors drawables and rotation deformers across a vertical axis so a
rigger can author the left half of a puppet, then one-click produce
the right-side equivalent. Pure-Python — Qt workflow lives in
``workspace.py``.

Scope:

* :func:`mirror_drawable` — clones a :class:`Drawable` with all vertex
  X coordinates reflected about ``axis_x``. Triangle winding is
  reversed because mirroring flips orientation and an un-flipped wind
  would render back-facing.
* :func:`mirror_rotation_deformer` — clones a rotation deformer with
  the anchor X mirrored and the angle negated.
* :func:`mirror_id` — heuristic to derive the partner id (``foo_l``
  → ``foo_r``, ``left_eye`` → ``right_eye``, ``hand_left`` →
  ``hand_right``).
* :func:`auto_mirror_pair` — composite operation: pick a source
  drawable, build its mirrored partner, register it in the document.

Warp deformers and bone weights are out of scope: their grid /
weights structure makes a clean mirror complicated (you also have to
mirror the targets' vertices, which already got mirrored by us).
Future extension once an authoring workflow needs them.
"""
from __future__ import annotations

import copy
import re
from collections.abc import Iterable

from Imervue.puppet.document import Deformer, Drawable, PuppetDocument


def mirror_drawable(
    drawable: Drawable, axis_x: float, *, new_id: str | None = None,
    new_texture: str | None = None,
) -> Drawable:
    """Return a deep copy of ``drawable`` reflected about ``axis_x``.

    * Vertex X coordinates become ``2 * axis_x - x``.
    * UVs are kept as-is — the texture itself isn't mirrored, just
      the geometry; rigs usually want the same eye pixels on both
      sides.
    * Triangle indices are wound in reverse order per triangle so the
      mirror doesn't flip the front face.
    * ``id`` defaults to :func:`mirror_id` of the source; ``texture``
      defaults to a sibling path with the mirrored id substituted.
    """
    mirrored_vertices = [
        (2.0 * axis_x - float(x), float(y))
        for x, y in drawable.vertices
    ]
    mirrored_indices: list[int] = []
    for i in range(0, len(drawable.indices), 3):
        triangle = drawable.indices[i:i + 3]
        if len(triangle) == 3:
            mirrored_indices.extend([triangle[0], triangle[2], triangle[1]])
    out = copy.deepcopy(drawable)
    out.id = new_id or mirror_id(drawable.id)
    out.texture = new_texture or out.texture
    out.vertices = mirrored_vertices
    out.indices = mirrored_indices
    return out


def mirror_rotation_deformer(
    deformer: Deformer, axis_x: float, *, new_id: str | None = None,
    drawables: Iterable[str] | None = None,
) -> Deformer:
    """Return a mirrored copy of a rotation deformer. Raises
    :class:`ValueError` for non-rotation types — warp / bone variants
    have geometry the caller must mirror first."""
    if deformer.type != "rotation":
        raise ValueError(
            f"mirror_rotation_deformer expects type='rotation', got {deformer.type!r}",
        )
    out = copy.deepcopy(deformer)
    out.id = new_id or mirror_id(deformer.id)
    if drawables is not None:
        out.drawables = list(drawables)
    anchor = out.form.get("anchor", [axis_x, 0.0])
    if isinstance(anchor, (list, tuple)) and len(anchor) == 2:
        out.form["anchor"] = [2.0 * axis_x - float(anchor[0]), float(anchor[1])]
    if "angle" in out.form:
        out.form["angle"] = -float(out.form["angle"])
    return out


def mirror_id(source_id: str) -> str:
    """Derive the partner id by flipping a left/right token.

    Recognises common suffixes (``_l`` ↔ ``_r``, ``_left`` ↔
    ``_right``) and prefixes (``l_``, ``left_``). Falls back to
    suffixing ``"_mirrored"`` when no token matches so the caller
    still gets a unique id."""
    rules: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"^(.*)_l$", re.I), r"\1_r"),
        (re.compile(r"^(.*)_r$", re.I), r"\1_l"),
        (re.compile(r"^(.*)_left$", re.I), r"\1_right"),
        (re.compile(r"^(.*)_right$", re.I), r"\1_left"),
        (re.compile(r"^l_(.*)$", re.I), r"r_\1"),
        (re.compile(r"^r_(.*)$", re.I), r"l_\1"),
        (re.compile(r"^left_(.*)$", re.I), r"right_\1"),
        (re.compile(r"^right_(.*)$", re.I), r"left_\1"),
    ]
    for pattern, repl in rules:
        if pattern.match(source_id):
            return pattern.sub(repl, source_id)
    return f"{source_id}_mirrored"


def auto_mirror_pair(
    document: PuppetDocument,
    source_drawable_id: str,
    *,
    axis_x: float | None = None,
    new_id: str | None = None,
) -> Drawable | None:
    """Locate ``source_drawable_id`` in ``document``, build its mirror,
    register the mirror as a new drawable, and return it.

    ``axis_x`` defaults to the canvas's horizontal centre. Returns
    ``None`` when the source isn't found or the derived mirror id
    already exists (the caller can recover by passing an explicit
    ``new_id``)."""
    source = document.drawable(source_drawable_id)
    if source is None:
        return None
    centre = axis_x if axis_x is not None else document.size[0] / 2.0
    candidate_id = new_id or mirror_id(source_drawable_id)
    if any(d.id == candidate_id for d in document.drawables):
        return None
    mirrored = mirror_drawable(source, centre, new_id=candidate_id)
    document.drawables.append(mirrored)
    return mirrored
