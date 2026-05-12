"""Auto-rig pass: derive a working Cubism-style rig from layer naming
conventions on a freshly-imported :class:`PuppetDocument`.

The PSD → puppet importer gives the user drawables but no behaviour —
they still have to author deformers and keyforms before anything
moves. This module closes that gap by scanning drawable ids for the
naming patterns Cubism artists already use, then bolting on:

* **Eye blink** — when a layer pair ``*_l_open`` / ``*_l_close`` (and
  the right-side equivalent) exists, add ``opacity_keys`` driven by
  ``ParamEyeLOpen`` / ``ParamEyeROpen`` so the standard blink driver
  cross-fades the two layers automatically.

* **Mouth viseme** — when mouth variants exist (``mouth_open`` /
  ``mouth_close`` and optional ``mouth_a / _i / _u / _e / _o``), add
  ``opacity_keys`` driven by ``ParamMouthOpenY`` and ``ParamMouthForm``
  so lip-sync produces visible mouth shapes.

* **Head tilt** — when any drawable matches a "head" pattern, add a
  rotation deformer around the head's centre keyed on
  ``ParamAngleZ`` (Live2D's head-roll axis).

* **Hair swing** — when "hair" or "bang" layers exist, add a warp
  deformer + a physics rig driven by ``ParamAngleX`` so they swing as
  the head moves.

All rule predicates are pure-Python and live next to the patches so
tests can exercise the detection without going through a PSD.
"""
from __future__ import annotations

import math
import re

from puppet.deformers import (
    default_rotation_form,
    default_warp_form,
)
from puppet.document import (
    Deformer,
    Drawable,
    Parameter,
    ParameterKey,
    PhysicsParticle,
    PhysicsRig,
    PuppetDocument,
)
from puppet.standard_params import (
    PARAM_ANGLE_X,
    PARAM_ANGLE_Z,
    PARAM_EYE_L_OPEN,
    PARAM_EYE_R_OPEN,
    PARAM_HAIR_FRONT,
    PARAM_MOUTH_FORM,
    PARAM_MOUTH_OPEN_Y,
)

_HEAD_TILT_RAD: float = math.radians(15.0)
"""Maximum head-roll angle the auto-rigger keys at ``ParamAngleZ=±1``."""

_HAIR_PHYSICS_PARTICLES: int = 4
"""Default chain length for an auto-rigged hair swing. Long enough to
read as motion, short enough that the Verlet integrator stays
trivially stable at 60 FPS."""


def auto_rig(document: PuppetDocument) -> dict[str, int]:
    """Run every detection pass against ``document`` in-place. Returns
    a ``{rule: count}`` dict so callers (and tests) can introspect what
    fired."""
    counts: dict[str, int] = {
        "eyes": _rig_eyes(document),
        "mouth": _rig_mouth(document),
        "head_tilt": _rig_head_tilt(document),
        "hair_swing": _rig_hair_swing(document),
    }
    return counts


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _normalise(drawable_id: str) -> str:
    """Lower-case + collapse dashes/spaces into underscores so the
    pattern matchers can use one canonical form. Splits camelCase
    boundaries so Cubism-style ``EyeLOpen`` resolves the same as the
    snake-cased ``eye_l_open`` used in most PSDs."""
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", drawable_id)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", s)
    return re.sub(r"[\s\-]+", "_", s.lower())


def detect_eye(drawable_id: str) -> tuple[str, str] | None:
    """Return ``(side, state)`` where side is ``'l'`` or ``'r'`` and
    state is ``'open'`` or ``'close'``. ``None`` when the id isn't an
    eye layer."""
    norm = _normalise(drawable_id)
    if "eye" not in norm:
        return None
    side = _detect_side(norm)
    state = _detect_eye_state(norm)
    if side and state:
        return side, state
    return None


def _detect_side(norm: str) -> str | None:
    """Pull a left/right side out of a normalised id. Matches
    ``_l_``, ``_l$``, ``left``, and short prefix forms like ``l_eye``."""
    if re.search(r"(?:^|_)(l|left)(?:_|$)", norm):
        return "l"
    if re.search(r"(?:^|_)(r|right)(?:_|$)", norm):
        return "r"
    return None


def _detect_eye_state(norm: str) -> str | None:
    if any(t in norm for t in ("open", "opened")):
        return "open"
    if any(t in norm for t in ("close", "closed", "shut")):
        return "close"
    return None


def detect_mouth_variant(drawable_id: str) -> str | None:
    """Return ``'open'`` / ``'close'`` / ``'a'`` / ``'i'`` / ``'u'`` /
    ``'e'`` / ``'o'`` or ``None``. Recognises common variants like
    ``mouth_a`` / ``mouth_open_a`` / ``mouth_aa`` and matches Cubism's
    convention of vowel-tagged mouth shapes."""
    norm = _normalise(drawable_id)
    if "mouth" not in norm and "lip" not in norm:
        return None
    if any(t in norm for t in ("close", "closed", "shut")):
        return "close"
    for vowel in ("a", "i", "u", "e", "o"):
        if re.search(rf"(?:^|_)(?:mouth_)?{vowel}{vowel}?(?:_|$)", norm):
            return vowel
    if "open" in norm:
        return "open"
    return None


def detect_head(drawable_id: str) -> bool:
    norm = _normalise(drawable_id)
    if "forehead" in norm:
        return False
    return any(t in norm for t in ("head", "face"))


def detect_hair(drawable_id: str) -> bool:
    norm = _normalise(drawable_id)
    return any(t in norm for t in ("hair", "bang", "fringe"))


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------


def _rig_eyes(document: PuppetDocument) -> int:
    """Pair up ``*_open`` / ``*_close`` eye layers and key their
    opacity off ``ParamEyeLOpen`` / ``ParamEyeROpen``. Returns the
    number of layers patched."""
    patched = 0
    for drawable in document.drawables:
        hit = detect_eye(drawable.id)
        if hit is None:
            continue
        side, state = hit
        param = PARAM_EYE_L_OPEN if side == "l" else PARAM_EYE_R_OPEN
        if state == "open":
            stops = [
                {"value": 0.0, "alpha": 0.0},
                {"value": 1.0, "alpha": 1.0},
            ]
        else:
            stops = [
                {"value": 0.0, "alpha": 1.0},
                {"value": 1.0, "alpha": 0.0},
            ]
        _ensure_opacity_keys(drawable, param, stops)
        patched += 1
    return patched


def _rig_mouth(document: PuppetDocument) -> int:
    """Key mouth variants against ``ParamMouthOpenY`` (open/close) and
    ``ParamMouthForm`` (vowel shape) for cross-faded viseme lip-sync."""
    patched = 0
    for drawable in document.drawables:
        variant = detect_mouth_variant(drawable.id)
        if variant is None:
            continue
        _ensure_opacity_keys(drawable, PARAM_MOUTH_OPEN_Y, _mouth_open_curve(variant))
        form_curve = _mouth_form_curve(variant)
        if form_curve is not None:
            _ensure_opacity_keys(drawable, PARAM_MOUTH_FORM, form_curve)
        patched += 1
    return patched


def _mouth_open_curve(variant: str) -> list[dict]:
    """``ParamMouthOpenY=0`` is mouth shut, ``=1`` is fully open."""
    if variant == "close":
        return [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.0},
        ]
    return [
        {"value": 0.0, "alpha": 0.0},
        {"value": 1.0, "alpha": 1.0},
    ]


def _mouth_form_curve(variant: str) -> list[dict] | None:
    """``ParamMouthForm`` runs ``[-1, 1]``; ``-1`` is round (oh / oo),
    ``+1`` is wide (ee / ay). Vowel mouths get a triangular curve
    peaking at the matching form value so a single AIUEO blend
    yields the right shape."""
    peak_by_vowel = {
        "a": 0.5,
        "i": 1.0,
        "u": -1.0,
        "e": 0.3,
        "o": -0.5,
    }
    peak = peak_by_vowel.get(variant)
    if peak is None:
        return None
    return [
        {"value": -1.0, "alpha": 0.0 if peak >= 0 else 1.0 - abs(peak + 1.0)},
        {"value": peak, "alpha": 1.0},
        {"value": 1.0, "alpha": 1.0 - abs(peak - 1.0) if peak >= 0 else 0.0},
    ]


def _rig_head_tilt(document: PuppetDocument) -> int:
    """Add a single rotation deformer keyed on ``ParamAngleZ`` covering
    every detected head/face drawable. Skips when there's nothing
    head-like (no point in keying empty deformers)."""
    head_ids = [d.id for d in document.drawables if detect_head(d.id)]
    if not head_ids:
        return 0
    deformer_id = _unique_deformer_id(document, "head_tilt")
    anchor = _drawable_group_centre(document, head_ids)
    rotation = Deformer(
        id=deformer_id,
        type="rotation",
        parent=None,
        drawables=list(head_ids),
        form=default_rotation_form(anchor),
    )
    document.deformers.append(rotation)
    _ensure_parameter(document, PARAM_ANGLE_Z)
    _set_param_keys(
        document, PARAM_ANGLE_Z,
        {
            -1.0: {deformer_id: {"angle": -_HEAD_TILT_RAD}},
            0.0: {deformer_id: {"angle": 0.0}},
            1.0: {deformer_id: {"angle": _HEAD_TILT_RAD}},
        },
    )
    return len(head_ids)


def _rig_hair_swing(document: PuppetDocument) -> int:
    """Bundle hair / bang / fringe drawables under a single warp
    deformer and bolt a 4-particle physics chain onto it so head
    motion makes the hair swing."""
    hair_ids = [d.id for d in document.drawables if detect_hair(d.id)]
    if not hair_ids:
        return 0
    bounds = _drawable_group_bounds(document, hair_ids)
    if bounds is None:
        return 0
    deformer_id = _unique_deformer_id(document, "hair_swing")
    warp = Deformer(
        id=deformer_id,
        type="warp",
        parent=None,
        drawables=list(hair_ids),
        form=default_warp_form(bounds, rows=4, cols=4),
    )
    document.deformers.append(warp)
    _ensure_parameter(document, PARAM_ANGLE_X)
    _ensure_parameter(document, PARAM_HAIR_FRONT)
    rig_id = _unique_physics_id(document, "hair_chain")
    document.physics_rigs.append(
        PhysicsRig(
            id=rig_id,
            input_param=PARAM_ANGLE_X,
            output_param=PARAM_HAIR_FRONT,
            chain=[PhysicsParticle() for _ in range(_HAIR_PHYSICS_PARTICLES)],
        ),
    )
    return len(hair_ids)


# ---------------------------------------------------------------------------
# Mutators
# ---------------------------------------------------------------------------


def _ensure_opacity_keys(
    drawable: Drawable, parameter: str, stops: list[dict],
) -> None:
    if drawable.opacity_keys is None:
        drawable.opacity_keys = []
    # Replace an existing curve for the same parameter rather than
    # stacking duplicates — re-running the auto-rigger on the same
    # document should be idempotent.
    drawable.opacity_keys = [
        entry for entry in drawable.opacity_keys
        if entry.get("parameter") != parameter
    ]
    drawable.opacity_keys.append({
        "parameter": parameter,
        "stops": [dict(s) for s in stops],
    })


def _ensure_parameter(document: PuppetDocument, param_id: str) -> None:
    if document.parameter(param_id) is not None:
        return
    # Fall back to the Cubism-standard range for these well-known ids.
    document.parameters.append(
        Parameter(id=param_id, min=-1.0, max=1.0, default=0.0),
    )


def _set_param_keys(
    document: PuppetDocument,
    param_id: str,
    values_to_forms: dict[float, dict[str, dict]],
) -> None:
    parameter = document.parameter(param_id)
    if parameter is None:
        return
    for value, forms in values_to_forms.items():
        replaced = False
        for key in parameter.keys:
            if abs(key.value - value) < 1e-6:
                key.forms.update({k: dict(v) for k, v in forms.items()})
                replaced = True
                break
        if not replaced:
            parameter.keys.append(
                ParameterKey(
                    value=float(value),
                    forms={k: dict(v) for k, v in forms.items()},
                ),
            )
    parameter.keys.sort(key=lambda k: k.value)


def _unique_deformer_id(document: PuppetDocument, prefix: str) -> str:
    existing = {d.id for d in document.deformers}
    if prefix not in existing:
        return prefix
    i = 2
    while f"{prefix}_{i}" in existing:
        i += 1
    return f"{prefix}_{i}"


def _unique_physics_id(document: PuppetDocument, prefix: str) -> str:
    existing = {r.id for r in document.physics_rigs}
    if prefix not in existing:
        return prefix
    i = 2
    while f"{prefix}_{i}" in existing:
        i += 1
    return f"{prefix}_{i}"


def _drawable_group_centre(
    document: PuppetDocument, ids: list[str],
) -> tuple[float, float]:
    bounds = _drawable_group_bounds(document, ids)
    if bounds is None:
        return (document.size[0] / 2.0, document.size[1] / 2.0)
    x0, y0, x1, y1 = bounds
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _drawable_group_bounds(
    document: PuppetDocument, ids: list[str],
) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for drawable_id in ids:
        drawable = document.drawable(drawable_id)
        if drawable is None or not drawable.vertices:
            continue
        for x, y in drawable.vertices:
            xs.append(float(x))
            ys.append(float(y))
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys))
